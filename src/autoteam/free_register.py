"""Free 账号注册编排 - 创建、删除、刷新。

复用 Team 直接注册流程和 Codex OAuth 流程，但不参与 Team 轮转。
"""

import logging
import time
import uuid
from pathlib import Path

from autoteam.cloudmail import CloudMailClient
from autoteam.codex_auth import login_codex_via_browser, save_auth_file
from autoteam.config import get_cloudmail_free_domain
from autoteam.cpa_sync import delete_from_cpa, upload_to_cpa
from autoteam.free_accounts import add_free_account, delete_free_account, find_free_account, update_free_account

logger = logging.getLogger(__name__)


def _import_register_direct_once():
    from autoteam.manager import _register_direct_once

    return _register_direct_once


def _register_direct_once(*args, **kwargs):
    return _import_register_direct_once()(*args, **kwargs)


def make_free_mail_client():
    """根据 runtime_config.MAIL_PROVIDER 选择邮箱客户端。"""
    from autoteam.runtime_config import get_mail_provider

    if get_mail_provider() == "outlook":
        from autoteam.outlook_mail import OutlookMailClient

        return OutlookMailClient()

    domain = get_cloudmail_free_domain()
    if not domain:
        raise RuntimeError("CLOUDMAIL_FREE_DOMAIN not configured")
    client = CloudMailClient(domain=domain)
    client.login()
    return client


def _rollback_cloudmail(mail_client, account_id):
    try:
        mail_client.delete_account(account_id)
    except Exception:
        logger.exception("[Free] 回滚 CloudMail 邮箱失败: %s", account_id)


def create_one_free_account(mail_client):
    """执行一次 Free 账号创建。返回 {status, email?, reason?}。"""
    account_id = None
    email = None

    try:
        account_id, email = mail_client.create_temp_email()
        password = f"Tmp_{uuid.uuid4().hex[:12]}!"

        ok = _register_direct_once(
            mail_client,
            email,
            password,
            cloudmail_account_id=account_id,
            use_runtime_proxy=True,
        )
        if not ok:
            _rollback_cloudmail(mail_client, account_id)
            return {"status": "failed", "email": email, "reason": "register_failed_3x"}

        bundle = login_codex_via_browser(email, password, mail_client=mail_client, use_runtime_proxy=True)
        if not bundle:
            _rollback_cloudmail(mail_client, account_id)
            return {"status": "failed", "email": email, "reason": "codex_oauth_failed"}

        if bundle.get("plan_type") != "free":
            logger.warning(
                "[Free] 注册产物 plan_type=%s 而非 free，可能域名配错。回滚: %s",
                bundle.get("plan_type"),
                email,
            )
            _rollback_cloudmail(mail_client, account_id)
            return {"status": "failed", "email": email, "reason": "plan_type_mismatch"}

        auth_path = save_auth_file(bundle)
        add_free_account(
            email=email,
            password=password,
            cloudmail_account_id=account_id,
            auth_file=str(auth_path),
            plan_type="free",
        )

        from autoteam.runtime_config import get_mail_provider

        if get_mail_provider() == "outlook":
            from autoteam.outlook_pool import mark_used as _outlook_mark_used

            _outlook_mark_used(email, registered_chatgpt_email=email)

        try:
            upload_to_cpa(auth_path)
        except Exception as exc:
            logger.warning("[Free] CPA 上传失败但保留本地: %s (%s)", email, exc)

        logger.info("[Free] 注册成功: %s", email)
        return {"status": "ok", "email": email}

    except Exception as exc:
        logger.error("[Free] 创建异常: %s (email=%s)", exc, email)
        if account_id is not None:
            _rollback_cloudmail(mail_client, account_id)
        return {"status": "failed", "email": email, "reason": f"unexpected:{exc}"}


def create_free_accounts_batch(count):
    """批量创建 Free 账号；遇到单次失败不阻塞后续。"""
    if not (1 <= count <= 50):
        raise ValueError("count must be in 1..50")

    mail_client = make_free_mail_client()
    succeeded = []
    failed = []
    for index in range(count):
        logger.info("[Free] 批量进度 %d/%d", index + 1, count)
        result = create_one_free_account(mail_client)
        if result["status"] == "ok":
            succeeded.append(result["email"])
        else:
            failed.append({"email": result.get("email"), "reason": result.get("reason")})

    return {"count": count, "succeeded": succeeded, "failed": failed}


def delete_free_account_full(email):
    """幂等删除：CPA → 本地 auth 文件 → CloudMail 邮箱 → free_accounts 记录。"""
    acc = find_free_account(email)
    if not acc:
        return {"status": "not_found", "email": email}

    auth_path_str = acc.get("auth_file")
    if auth_path_str:
        auth_path = Path(auth_path_str)
        try:
            delete_from_cpa(auth_path.name)
        except Exception as exc:
            logger.warning("[Free] CPA 删除失败 (忽略): %s (%s)", auth_path.name, exc)
        try:
            auth_path.unlink(missing_ok=True)
        except Exception as exc:
            logger.warning("[Free] auth 文件删除失败 (忽略): %s (%s)", auth_path, exc)

    cloudmail_account_id = acc.get("cloudmail_account_id")
    if cloudmail_account_id is not None:
        try:
            mail_client = make_free_mail_client()
            mail_client.delete_account(cloudmail_account_id)
        except Exception as exc:
            logger.warning("[Free] CloudMail 删除失败 (忽略): %s (%s)", cloudmail_account_id, exc)

    delete_free_account(email)
    return {"status": "ok", "email": email}


def refresh_codex(email):
    """重跑 Codex OAuth → 覆盖 auth → 重传 CPA → 更新记录。"""
    acc = find_free_account(email)
    if not acc:
        return {"status": "not_found", "email": email}

    mail_client = make_free_mail_client()
    bundle = login_codex_via_browser(
        acc["email"],
        acc["password"],
        mail_client=mail_client,
        use_runtime_proxy=True,
    )
    if not bundle:
        update_free_account(email, last_error="codex_oauth_failed")
        return {"status": "failed", "email": email, "reason": "codex_oauth_failed"}

    if bundle.get("plan_type") != "free":
        update_free_account(email, last_error="plan_type_mismatch")
        return {"status": "failed", "email": email, "reason": "plan_type_mismatch"}

    new_path = save_auth_file(bundle)
    try:
        upload_to_cpa(new_path)
    except Exception as exc:
        logger.warning("[Free] 刷新后 CPA 上传失败 (保留本地): %s (%s)", email, exc)

    update_free_account(
        email,
        auth_file=str(new_path),
        last_refreshed_at=time.time(),
        last_error=None,
    )
    return {"status": "ok", "email": email, "auth_file": str(new_path)}

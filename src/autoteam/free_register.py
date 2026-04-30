"""Free 账号注册编排 - 创建、删除、刷新。

复用 Team 直接注册流程和 Codex OAuth 流程，但不参与 Team 轮转。
"""

import logging
import uuid

from autoteam.cloudmail import CloudMailClient
from autoteam.codex_auth import login_codex_via_browser, save_auth_file
from autoteam.config import CLOUDMAIL_FREE_DOMAIN
from autoteam.cpa_sync import upload_to_cpa
from autoteam.free_accounts import add_free_account

logger = logging.getLogger(__name__)


def _import_register_direct_once():
    from autoteam.manager import _register_direct_once

    return _register_direct_once


def _register_direct_once(*args, **kwargs):
    return _import_register_direct_once()(*args, **kwargs)


def make_free_mail_client():
    """创建带 Free 域名的 CloudMail 客户端；未配置时抛 RuntimeError。"""
    if not CLOUDMAIL_FREE_DOMAIN:
        raise RuntimeError("CLOUDMAIL_FREE_DOMAIN not configured")
    client = CloudMailClient(domain=CLOUDMAIL_FREE_DOMAIN)
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

        ok = _register_direct_once(mail_client, email, password, cloudmail_account_id=account_id)
        if not ok:
            _rollback_cloudmail(mail_client, account_id)
            return {"status": "failed", "email": email, "reason": "register_failed_3x"}

        bundle = login_codex_via_browser(email, password, mail_client=mail_client)
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

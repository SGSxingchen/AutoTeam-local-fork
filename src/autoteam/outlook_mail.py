"""与 CloudMailClient 鸭子兼容的 Outlook 客户端。"""

from __future__ import annotations

import logging

from autoteam import outlook_pool
from autoteam.mail_utils import extract_invite_link as _extract_invite_link
from autoteam.mail_utils import extract_verification_code as _extract_verification_code
from autoteam.outlook_imap import OutlookIMAP
from autoteam.outlook_oauth import (
    OutlookOAuthError,
    OutlookTokenRevokedError,
    get_access_token,
    invalidate_cache,
)

logger = logging.getLogger(__name__)


class OutlookMailClient:
    """调用接口与 CloudMailClient 对齐。"""

    def login(self):
        # noop:Outlook 没有全局会话
        return None

    def create_temp_email(self, prefix=None):
        """从池里 claim 一个,返回 (email_as_account_id, email)。prefix 忽略。"""
        record = outlook_pool.claim_one()
        if record is None:
            raise RuntimeError("Outlook 池里没有可用账户")
        logger.info("[Outlook] claim 邮箱: %s", record["email"])
        return record["email"], record["email"]

    def list_accounts(self, size=200):
        """供 UI 兼容用;返回池快照。"""
        return outlook_pool.load_pool()[:size]

    def search_emails_by_recipient(self, to_email, size=10, account_id=None):
        record = outlook_pool.find(to_email)
        if record is None:
            logger.warning("[Outlook] 池中找不到邮箱: %s", to_email)
            return []
        if record.get("status") not in ("in_use", "used"):
            logger.warning("[Outlook] 邮箱 %s 状态 %s,跳过 IMAP 查询", to_email, record.get("status"))
            return []

        try:
            access_token = get_access_token(record)
        except OutlookTokenRevokedError:
            return []
        except OutlookOAuthError as exc:
            logger.warning("[Outlook] OAuth 临时失败 %s: %s", to_email, exc)
            return []

        try:
            with OutlookIMAP(record["email"], access_token) as imap:
                return imap.search_emails(limit=size)
        except Exception as exc:
            logger.warning("[Outlook] IMAP 查询失败 %s: %s,清缓存重试一次", to_email, exc)
            invalidate_cache(to_email)
            try:
                access_token = get_access_token(record)
                with OutlookIMAP(record["email"], access_token) as imap:
                    return imap.search_emails(limit=size)
            except Exception as exc2:
                logger.error("[Outlook] IMAP 二次失败 %s: %s", to_email, exc2)
                outlook_pool.mark_error(to_email, f"imap_failed: {exc2}")
                return []

    def list_emails(self, account_id, size=10):
        return self.search_emails_by_recipient(account_id, size=size)

    def get_latest_emails(self, account_id, email_id=0, all_receive=0):
        return self.search_emails_by_recipient(account_id, size=10)

    def delete_account(self, account_id):
        """回滚语义:把邮箱标 error。"""
        outlook_pool.mark_error(account_id, "rolled_back_during_register")
        return {"code": 200}

    def delete_emails_for(self, to_email):
        # IMAP 不主动清邮件
        return 0

    def extract_verification_code(self, email_data):
        return _extract_verification_code(email_data)

    def extract_invite_link(self, email_data):
        link = _extract_invite_link(email_data)
        if link:
            logger.info("[Outlook] 提取到邀请链接: %s...", link[:80])
        return link

    def wait_for_email(self, to_email, timeout=None, sender_keyword=None):
        """轮询等邮件到达。复用 CloudMail 的接口约定。"""
        import time

        from autoteam.config import EMAIL_POLL_INTERVAL, EMAIL_POLL_TIMEOUT

        timeout = timeout or EMAIL_POLL_TIMEOUT
        logger.info("[Outlook] 等待邮件到达 %s... (超时 %ds)", to_email, timeout)
        start = time.time()
        while time.time() - start < timeout:
            emails = self.search_emails_by_recipient(to_email, size=10)
            for em in emails:
                sender = (em.get("sendEmail") or "").lower()
                if sender_keyword and sender_keyword.lower() not in sender:
                    continue
                logger.info("[Outlook] 收到邮件: %s (from: %s)", em.get("subject"), sender)
                return em
            elapsed = int(time.time() - start)
            print(f"\r[Outlook] 等待中... ({elapsed}s)", end="", flush=True)
            time.sleep(EMAIL_POLL_INTERVAL)
        print()
        raise TimeoutError("等待邮件超时")

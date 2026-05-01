"""Outlook IMAP XOAUTH2 短连接客户端。"""

from __future__ import annotations

import email
import imaplib
import logging
from email.header import decode_header, make_header

logger = logging.getLogger(__name__)

IMAP_HOST = "outlook.office365.com"
IMAP_PORT = 993


class OutlookIMAP:
    """单账户短连接 IMAP。with 块内复用一次 TCP 连接。"""

    def __init__(self, account_email: str, access_token: str):
        self.account_email = account_email
        self.access_token = access_token
        self._conn: imaplib.IMAP4_SSL | None = None

    def __enter__(self):
        self._conn = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
        auth_string = f"user={self.account_email}\x01auth=Bearer {self.access_token}\x01\x01"
        self._conn.authenticate("XOAUTH2", lambda _: auth_string.encode())
        return self

    def __exit__(self, *exc):
        if self._conn is not None:
            try:
                self._conn.logout()
            except Exception:
                pass
            self._conn = None

    @staticmethod
    def _decode_header(value) -> str:
        if value is None:
            return ""
        try:
            return str(make_header(decode_header(value)))
        except Exception:
            return str(value)

    @staticmethod
    def _extract_body(msg) -> tuple[str, str]:
        """返回 (text, html)。"""
        text_parts: list[str] = []
        html_parts: list[str] = []
        if msg.is_multipart():
            for part in msg.walk():
                if part.is_multipart():
                    continue
                ctype = part.get_content_type()
                disp = (part.get("Content-Disposition") or "").lower()
                if "attachment" in disp:
                    continue
                charset = part.get_content_charset() or "utf-8"
                try:
                    payload = part.get_payload(decode=True)
                    if payload is None:
                        continue
                    decoded = payload.decode(charset, errors="replace")
                except Exception:
                    continue
                if ctype == "text/plain":
                    text_parts.append(decoded)
                elif ctype == "text/html":
                    html_parts.append(decoded)
        else:
            charset = msg.get_content_charset() or "utf-8"
            try:
                payload = msg.get_payload(decode=True)
                if payload:
                    decoded = payload.decode(charset, errors="replace")
                    if msg.get_content_type() == "text/html":
                        html_parts.append(decoded)
                    else:
                        text_parts.append(decoded)
            except Exception:
                pass
        return ("\n".join(text_parts).strip(), "\n".join(html_parts).strip())

    def search_emails(self, sender_keyword: str | None = None, limit: int = 10) -> list[dict]:
        """返回 CloudMail 兼容字段名的最近邮件,新→旧排序。"""
        assert self._conn is not None, "use within `with` block"
        self._conn.select("INBOX")

        criteria = ["ALL"]
        if sender_keyword:
            criteria = ["FROM", f'"{sender_keyword}"']
        status, data = self._conn.search(None, *criteria)
        if status != "OK" or not data or not data[0]:
            return []

        uids = data[0].split()
        uids = uids[-limit:][::-1]  # 取最新 N 条,反转为 newest-first

        results: list[dict] = []
        for uid in uids:
            status, fetched = self._conn.fetch(uid, "(RFC822)")
            if status != "OK" or not fetched:
                continue
            try:
                raw = fetched[0][1]
                msg = email.message_from_bytes(raw)
            except Exception:
                continue

            subject = self._decode_header(msg.get("Subject"))
            from_addr = self._decode_header(msg.get("From"))
            text_body, html_body = self._extract_body(msg)

            results.append(
                {
                    "emailId": uid.decode() if isinstance(uid, bytes) else str(uid),
                    "subject": subject,
                    "sendEmail": from_addr,
                    "text": text_body,
                    "content": html_body,
                    "accountId": self.account_email,
                }
            )

        return results

"""Outlook OAuth: refresh_token → access_token,带内存缓存。"""

from __future__ import annotations

import logging
import threading
import time

import requests

from autoteam.outlook_pool import mark_error, update_refresh_token

logger = logging.getLogger(__name__)

TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
SCOPE = "https://outlook.office.com/IMAP.AccessAsUser.All offline_access"
EARLY_REFRESH_SECONDS = 60

_cache: dict[str, tuple[str, int]] = {}
_cache_lock = threading.Lock()


class OutlookOAuthError(Exception):
    """OAuth 网络/服务异常,不改 pool 状态。"""


class OutlookTokenRevokedError(Exception):
    """refresh_token 已被吊销 (invalid_grant),已 mark_error。"""


def _mask(token: str) -> str:
    if not token or len(token) < 16:
        return "***"
    return f"{token[:8]}...{token[-8:]}"


def get_access_token(record: dict) -> str:
    """从 refresh_token 换 access_token,1h 缓存。"""
    email = record["email"]
    now = int(time.time())

    with _cache_lock:
        cached = _cache.get(email)
        if cached and cached[1] - EARLY_REFRESH_SECONDS > now:
            return cached[0]

    body = {
        "client_id": record["client_id"],
        "grant_type": "refresh_token",
        "refresh_token": record["refresh_token"],
        "scope": SCOPE,
    }

    try:
        resp = requests.post(TOKEN_URL, data=body, timeout=30)
    except requests.RequestException as exc:
        raise OutlookOAuthError(f"token endpoint unreachable: {exc}") from exc

    try:
        payload = resp.json()
    except ValueError as exc:
        raise OutlookOAuthError(f"non-JSON response (HTTP {resp.status_code})") from exc

    if resp.status_code != 200:
        err = payload.get("error", "")
        desc = payload.get("error_description", "")
        if err == "invalid_grant":
            mark_error(email, f"refresh_token_revoked: {desc[:200]}")
            logger.warning("[Outlook OAuth] %s refresh_token 已吊销: %s", email, desc[:120])
            raise OutlookTokenRevokedError(desc or "invalid_grant")
        raise OutlookOAuthError(f"HTTP {resp.status_code} {err}: {desc[:200]}")

    access_token = payload["access_token"]
    expires_in = int(payload.get("expires_in", 3600))
    expiry = now + expires_in

    new_refresh = payload.get("refresh_token")
    if new_refresh and new_refresh != record["refresh_token"]:
        update_refresh_token(email, new_refresh)
        logger.info("[Outlook OAuth] %s refresh_token 已轮换 (%s)", email, _mask(new_refresh))

    with _cache_lock:
        _cache[email] = (access_token, expiry)

    logger.debug("[Outlook OAuth] %s access_token 获取成功,expires_in=%ds", email, expires_in)
    return access_token


def invalidate_cache(email: str) -> None:
    """IMAP 鉴权失败时清缓存,强制下次重新换。"""
    with _cache_lock:
        _cache.pop(email, None)

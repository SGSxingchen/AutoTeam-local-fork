# Outlook 邮箱池接入 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Free 账号注册流程里引入 Outlook/Hotmail 邮箱池作为可选邮箱来源,Web UI 提供池管理,Settings 提供 provider 切换开关。

**Architecture:** 鸭子类型 —— `OutlookMailClient` 与现有 `CloudMailClient` 暴露相同方法签名,在 `free_register.make_free_mail_client()` 单点切换。`outlook_pool.json` 持久化批量账户,refresh_token 通过 Microsoft `/token` 端点换 access_token,IMAP 用 XOAUTH2 短连接抓邮件。Team 邀请流程不动。

**Tech Stack:** Python 3.13 / FastAPI / `imaplib` (stdlib) / `requests` / `fcntl` (stdlib) / Vue 3 / Tailwind。

**Spec:** `docs/superpowers/specs/2026-05-01-outlook-imap-design.md`

---

## File Structure

**新增文件**:
- `src/autoteam/mail_utils.py` — 从 cloudmail.py 抽出的纯函数(`extract_verification_code` / `extract_invite_link` / `html_to_visible_text`)
- `src/autoteam/outlook_pool.py` — 池 CRUD + 解析器 + 文件锁
- `src/autoteam/outlook_oauth.py` — refresh_token → access_token,内存缓存
- `src/autoteam/outlook_imap.py` — XOAUTH2 短连接 + 邮件抓取
- `src/autoteam/outlook_mail.py` — `OutlookMailClient` 鸭子类型
- `web/src/components/MailPoolPage.vue` — 邮箱池页面

**修改文件**:
- `src/autoteam/cloudmail.py` — 改用 mail_utils 的纯函数(行为不变)
- `src/autoteam/runtime_config.py` — `RUNTIME_CONFIG_KEYS` 增加 `MAIL_PROVIDER`
- `src/autoteam/free_register.py` — `make_free_mail_client` 加 provider 分支;成功分支调 `mark_used`
- `src/autoteam/api.py` — 6 个 Outlook 池端点
- `web/src/api.js` — 6 个端点的 fetch 包装
- `web/src/App.vue` — 新增邮箱池路由
- `web/src/components/Sidebar.vue` — 新增邮箱池入口
- `web/src/components/Settings.vue` — 新增「Free 注册」分区,含 provider 开关

---

## Task 1: 抽 `mail_utils.py` (重构,行为不变)

**Files:**
- Create: `src/autoteam/mail_utils.py`
- Modify: `src/autoteam/cloudmail.py:103-142, 296-323` (抽方法、改 import)

**Why this first:** OutlookMailClient 和 CloudMailClient 都需要同一套验证码/邀请链接抽取逻辑,先抽公共纯函数避免重复实现。

- [ ] **Step 1: 创建 `src/autoteam/mail_utils.py`**

```python
"""邮件正文解析的纯函数,CloudMail / Outlook 两端共用。"""

import html as _html_mod
import re

_VERIFICATION_CODE_PATTERNS = (
    r"(?:temporary\s+(?:openai|chatgpt)\s+login\s+code(?:\s+is)?|verification\s+code(?:\s+is)?|login\s+code(?:\s+is)?|code(?:\s+is)?|验证码(?:为|是)?)\D{0,24}(\d{6})",
    r"\b(\d{6})\b",
)


def html_to_visible_text(value):
    """剥 HTML 标签,保留可见文本。"""
    content = str(value or "")
    if not content:
        return ""

    content = re.sub(r"(?is)<(script|style)\b.*?>.*?</\1>", " ", content)
    content = re.sub(r"(?is)<!--.*?-->", " ", content)
    content = re.sub(r"(?i)<br\\s*/?>", "\n", content)
    content = re.sub(r"(?i)</(?:p|div|tr|table|h[1-6]|li|td|section|article)>", "\n", content)
    content = re.sub(r"(?s)<[^>]+>", " ", content)
    content = _html_mod.unescape(content)
    content = re.sub(r"[\t\r\f\v ]+", " ", content)
    content = re.sub(r"\n\s+", "\n", content)
    content = re.sub(r"\n{2,}", "\n", content)
    return content.strip()


def extract_verification_code(email_data):
    """从邮件 dict 中提取 6 位验证码。"""
    sources = []

    plain_text = str(email_data.get("text") or "").strip()
    if plain_text:
        sources.append(plain_text)

    html_text = html_to_visible_text(email_data.get("content"))
    if html_text and html_text not in sources:
        sources.append(html_text)

    for source in sources:
        for pattern in _VERIFICATION_CODE_PATTERNS:
            match = re.search(pattern, source, re.IGNORECASE)
            if match:
                return match.group(1)

    return None


def extract_invite_link(email_data):
    """从 OpenAI 邀请邮件中提取邀请链接。"""
    html = email_data.get("content", "")
    text = email_data.get("text", "")

    links = re.findall(r'href="(https://chatgpt\.com/auth/login\?[^"]*)"', html)
    if links:
        return links[0]

    links = re.findall(r'(https://chatgpt\.com/auth/login\?[^\s<>"\']+)', text)
    if links:
        return links[0]

    link_pattern = r'https?://[^\s<>"\']+(?:invite|accept|join|workspace)[^\s<>"\']*'
    match = re.search(link_pattern, html or text, re.IGNORECASE)
    if match:
        return match.group(0)

    return None
```

- [ ] **Step 2: 修改 `cloudmail.py`,删掉对应方法,改用 `mail_utils`**

替换 `cloudmail.py` 顶部 import 区,加一行:

```python
from autoteam.mail_utils import extract_invite_link as _extract_invite_link
from autoteam.mail_utils import extract_verification_code as _extract_verification_code
```

删除 `cloudmail.py` 里的下列代码块:
- 第 22-25 行 `_VERIFICATION_CODE_PATTERNS = (...)` (整个常量)
- 第 107-122 行 `_html_to_visible_text` 静态方法
- 第 124-142 行 `extract_verification_code` 方法体内容
- 第 296-323 行 `extract_invite_link` 方法体内容

替换 `extract_verification_code` 实现为:

```python
def extract_verification_code(self, email_data):
    return _extract_verification_code(email_data)
```

替换 `extract_invite_link` 实现为:

```python
def extract_invite_link(self, email_data):
    link = _extract_invite_link(email_data)
    if link:
        logger.info("[CloudMail] 提取到邀请链接: %s...", link[:80])
    return link
```

- [ ] **Step 3: ruff 检查**

Run: `ruff check src/autoteam/cloudmail.py src/autoteam/mail_utils.py`
Expected: 无报错。

Run: `ruff format src/autoteam/cloudmail.py src/autoteam/mail_utils.py`

- [ ] **Step 4: 冒烟验证(行为不变)**

启动 API 服务,触发一次现有 CloudMail Free 注册,确认正常完成:

Run: `uv run autoteam api &` (后台启动)
然后通过 Web UI 触发一次 Free 注册,观察日志中验证码提取仍然正常。如果当前没空跑 Free 注册,至少在 Python REPL 跑:

```bash
uv run python -c "
from autoteam.mail_utils import extract_verification_code
print(extract_verification_code({'text': 'Your code is 123456'}))
"
```
Expected: 输出 `123456`。

- [ ] **Step 5: Commit**

```bash
git add src/autoteam/mail_utils.py src/autoteam/cloudmail.py
git commit -m "refactor(mail): extract email parsing helpers to mail_utils

Pure functions for verification code and invite link extraction now live
in mail_utils.py, ready to be reused by the upcoming Outlook provider.
CloudMailClient delegates to them; behavior unchanged.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: `outlook_pool.py` —— 池 CRUD + 解析器 + 文件锁

**Files:**
- Create: `src/autoteam/outlook_pool.py`

- [ ] **Step 1: 创建 `src/autoteam/outlook_pool.py`**

```python
"""Outlook 邮箱池持久化与并发安全的 CRUD。"""

from __future__ import annotations

import fcntl
import json
import logging
import re
import time
from contextlib import contextmanager
from pathlib import Path

from autoteam.accounts import load_accounts
from autoteam.free_accounts import load_free_accounts

PROJECT_ROOT = Path(__file__).parent.parent.parent
POOL_FILE = PROJECT_ROOT / "outlook_pool.json"
LOCK_FILE = PROJECT_ROOT / ".outlook_pool.lock"
DEFAULT_CLIENT_ID = "9e5f94bc-e8a4-4e73-b8be-63364c29d753"
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)

logger = logging.getLogger(__name__)


def _normalize_email(value):
    return (value or "").strip().lower()


@contextmanager
def _file_lock():
    """文件锁,跨进程互斥保护 pool 文件读改写。"""
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd = open(LOCK_FILE, "a+")
    try:
        fcntl.flock(fd.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd.fileno(), fcntl.LOCK_UN)
        fd.close()


def load_pool() -> list[dict]:
    if not POOL_FILE.exists():
        return []
    text = POOL_FILE.read_text(encoding="utf-8").strip()
    if not text:
        return []
    return json.loads(text)


def save_pool(rows: list[dict]) -> None:
    POOL_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = POOL_FILE.with_name(f".{POOL_FILE.name}.tmp")
    tmp.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(POOL_FILE)


def find(email: str) -> dict | None:
    target = _normalize_email(email)
    for r in load_pool():
        if _normalize_email(r.get("email")) == target:
            return r
    return None


def stats() -> dict:
    rows = load_pool()
    out = {"total": len(rows), "available": 0, "in_use": 0, "used": 0, "error": 0}
    for r in rows:
        s = r.get("status")
        if s in out:
            out[s] += 1
    return out


def _parse_line(line: str, line_no: int) -> tuple[dict | None, str | None]:
    """解析单行,返回 (record, error)。两者必有其一。"""
    parts = line.split("----")
    if len(parts) == 4:
        email, password, client_id, refresh_token = parts
        aux_email = None
    elif len(parts) == 5:
        email, password, aux_email, client_id, refresh_token = parts
    else:
        return None, f"段数 {len(parts)} 不在 4/5 之列"

    email = _normalize_email(email)
    if "@" not in email:
        return None, "email 缺少 @"
    if not UUID_RE.match(client_id.strip()):
        return None, "client_id 不是 UUID 格式"
    if len(refresh_token.strip()) < 100:
        return None, "refresh_token 长度过短(疑似占位)"

    return {
        "email": email,
        "password": password.strip(),
        "client_id": client_id.strip(),
        "refresh_token": refresh_token.strip(),
        "aux_email": (aux_email or "").strip() or None,
        "status": "available",
        "added_at": int(time.time()),
        "claimed_at": None,
        "used_at": None,
        "registered_chatgpt_email": None,
        "last_error": None,
    }, None


def import_from_text(text: str) -> dict:
    """解析多行文本,返回 {imported, skipped, errors: [{line, reason}]}。"""
    imported = 0
    skipped = 0
    errors: list[dict] = []

    with _file_lock():
        rows = load_pool()
        existing_emails = {_normalize_email(r.get("email")) for r in rows}
        free_emails = {_normalize_email(a.get("email")) for a in load_free_accounts()}
        team_emails = {_normalize_email(a.get("email")) for a in load_accounts()}
        all_known = existing_emails | free_emails | team_emails

        for idx, raw in enumerate(text.splitlines(), start=1):
            line = raw.strip()
            if not line:
                continue
            record, err = _parse_line(line, idx)
            if err:
                errors.append({"line": idx, "reason": err})
                continue
            if record["email"] in all_known:
                skipped += 1
                continue
            rows.append(record)
            all_known.add(record["email"])
            imported += 1

        if imported:
            save_pool(rows)

    return {"imported": imported, "skipped": skipped, "errors": errors}


def claim_one() -> dict | None:
    """按 added_at 升序找首个 status=available,标 in_use,持久化,返回。"""
    with _file_lock():
        rows = load_pool()
        candidates = sorted(
            (r for r in rows if r.get("status") == "available"),
            key=lambda r: r.get("added_at") or 0,
        )
        if not candidates:
            return None
        target = candidates[0]
        target_email = target["email"]
        for r in rows:
            if _normalize_email(r.get("email")) == target_email:
                r["status"] = "in_use"
                r["claimed_at"] = int(time.time())
                save_pool(rows)
                return dict(r)
    return None


def _update(email: str, **fields) -> bool:
    target = _normalize_email(email)
    with _file_lock():
        rows = load_pool()
        changed = False
        for r in rows:
            if _normalize_email(r.get("email")) == target:
                r.update(fields)
                changed = True
                break
        if changed:
            save_pool(rows)
    return changed


def mark_used(email: str, registered_chatgpt_email: str) -> bool:
    return _update(
        email,
        status="used",
        used_at=int(time.time()),
        registered_chatgpt_email=registered_chatgpt_email,
        last_error=None,
    )


def mark_error(email: str, reason: str) -> bool:
    return _update(email, status="error", last_error=reason)


def reset(email: str) -> bool:
    """error / in_use → available;used 状态拒绝重置。"""
    target = _normalize_email(email)
    with _file_lock():
        rows = load_pool()
        for r in rows:
            if _normalize_email(r.get("email")) == target:
                if r.get("status") == "used":
                    return False
                r["status"] = "available"
                r["last_error"] = None
                r["claimed_at"] = None
                save_pool(rows)
                return True
    return False


def release(email: str) -> bool:
    """in_use → available 的兜底,异常路径里清理。"""
    target = _normalize_email(email)
    with _file_lock():
        rows = load_pool()
        for r in rows:
            if _normalize_email(r.get("email")) == target and r.get("status") == "in_use":
                r["status"] = "available"
                r["claimed_at"] = None
                save_pool(rows)
                return True
    return False


def delete(email: str) -> bool:
    target = _normalize_email(email)
    with _file_lock():
        rows = load_pool()
        new_rows = [r for r in rows if _normalize_email(r.get("email")) != target]
        if len(new_rows) == len(rows):
            return False
        save_pool(new_rows)
    return True


def update_refresh_token(email: str, new_refresh_token: str) -> bool:
    return _update(email, refresh_token=new_refresh_token)


if __name__ == "__main__":
    # 解析器烟雾测试
    sample = """qpzst27553129@hotmail.com----voxuh78829745----9e5f94bc-e8a4-4e73-b8be-63364c29d753----M.C528_BL2.0.U.-CjkIki!ng6XUb56eS*FX5FsKqjHAylRBpkzmFtlcp9LDt9SZMPULFgP*!wKxNXOxFNXtZQJtRHz7FILcjyRY8BVNkx9sWmCt6ei3*AtJkSU*aURD61!BKtL77yFP2kalF4unajoet7u4p4VrgCPo0TvuA2w7fCrxkuuRm16XEMp5EsvAq0PQShTPINTarr17dsntIOD0lSHKQx*m8jMTaPEFqcEw5Nd912F3wKkwZos1htacO3yQCQQH17SsUzphPF7FPEbVfHH4FGHo5Nh*0amA9ZovpjCJ!BW5BCjz2RjleVv9oUpYsdw7wLxhRuUgayxGrgW9mEWKawgIgQO6W7kn!p7EPRMoJPjxpdgNwwqAVHgLHOSSHG3XNVRwMXkSy6e1umcKAEZTaju6uuIGtzyZIzIHEElYxc7JirvgWNMQly71b6p9mdLXrOTIFfa*fZSN565BzHlnxDeJcuahEyI$
bad----too----few
abc@example.com----pwd----not-a-uuid----also-too-short
"""
    rec, err = _parse_line(sample.splitlines()[0], 1)
    assert rec is not None and err is None, (rec, err)
    assert rec["email"] == "qpzst27553129@hotmail.com"
    assert rec["client_id"] == "9e5f94bc-e8a4-4e73-b8be-63364c29d753"
    print("[smoke] 4-field parse OK")

    rec2, err2 = _parse_line(sample.splitlines()[1], 2)
    assert rec2 is None and "段数" in err2
    print("[smoke] short line rejected:", err2)

    rec3, err3 = _parse_line(sample.splitlines()[2], 3)
    assert rec3 is None and err3 is not None
    print("[smoke] bad uuid rejected:", err3)

    print("[smoke] all parser checks passed")
```

- [ ] **Step 2: 跑解析器烟雾测试**

Run: `uv run python -m autoteam.outlook_pool`
Expected:
```
[smoke] 4-field parse OK
[smoke] short line rejected: 段数 3 不在 4/5 之列
[smoke] bad uuid rejected: client_id 不是 UUID 格式
[smoke] all parser checks passed
```

- [ ] **Step 3: 跑 ruff**

Run: `ruff check --fix src/autoteam/outlook_pool.py && ruff format src/autoteam/outlook_pool.py`
Expected: 无报错。

- [ ] **Step 4: Commit**

```bash
git add src/autoteam/outlook_pool.py
git commit -m "feat(outlook): pool persistence with file lock and parser

Adds outlook_pool module: import-from-text parser supporting 4/5-segment
formats, FIFO claim_one, status transitions, and an fcntl-based file lock
to keep concurrent web imports and background claims consistent.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: `outlook_oauth.py` —— refresh_token → access_token

**Files:**
- Create: `src/autoteam/outlook_oauth.py`

- [ ] **Step 1: 创建 `src/autoteam/outlook_oauth.py`**

```python
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
```

- [ ] **Step 2: ruff 检查**

Run: `ruff check --fix src/autoteam/outlook_oauth.py && ruff format src/autoteam/outlook_oauth.py`
Expected: 无报错。

- [ ] **Step 3: Commit**

```bash
git add src/autoteam/outlook_oauth.py
git commit -m "feat(outlook): refresh_token to access_token exchange with cache

Calls Microsoft /token endpoint, caches access_token for ~1h, handles
invalid_grant by marking the pool record as error, and persists rotated
refresh_tokens back to the pool.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: `outlook_imap.py` —— XOAUTH2 + 邮件抓取

**Files:**
- Create: `src/autoteam/outlook_imap.py`

- [ ] **Step 1: 创建 `src/autoteam/outlook_imap.py`**

```python
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

            results.append({
                "emailId": uid.decode() if isinstance(uid, bytes) else str(uid),
                "subject": subject,
                "sendEmail": from_addr,
                "text": text_body,
                "content": html_body,
                "accountId": self.account_email,
            })

        return results
```

- [ ] **Step 2: ruff 检查**

Run: `ruff check --fix src/autoteam/outlook_imap.py && ruff format src/autoteam/outlook_imap.py`
Expected: 无报错。

- [ ] **Step 3: Commit**

```bash
git add src/autoteam/outlook_imap.py
git commit -m "feat(outlook): IMAP XOAUTH2 short-connection client

Connects to outlook.office365.com:993 with XOAUTH2 SASL, reads INBOX,
parses RFC822 to dicts whose field names match CloudMail (subject,
sendEmail, text, content, emailId) so downstream parsers stay shared.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: `outlook_mail.py` —— 鸭子类型 OutlookMailClient

**Files:**
- Create: `src/autoteam/outlook_mail.py`

- [ ] **Step 1: 创建 `src/autoteam/outlook_mail.py`**

```python
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
```

- [ ] **Step 2: ruff 检查**

Run: `ruff check --fix src/autoteam/outlook_mail.py && ruff format src/autoteam/outlook_mail.py`
Expected: 无报错。

- [ ] **Step 3: Commit**

```bash
git add src/autoteam/outlook_mail.py
git commit -m "feat(outlook): OutlookMailClient duck-typed adapter

Exposes the same method signatures as CloudMailClient
(login/create_temp_email/search_emails_by_recipient/wait_for_email/
extract_verification_code/extract_invite_link/delete_account/...) so
free_register can swap implementations without touching the call sites.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: `runtime_config.py` —— 注册 `MAIL_PROVIDER`

**Files:**
- Modify: `src/autoteam/runtime_config.py:15-19, 24-28`

- [ ] **Step 1: 修改 `RUNTIME_CONFIG_KEYS` 增加新键**

把:
```python
RUNTIME_CONFIG_KEYS = (
    "CLOUDMAIL_FREE_DOMAIN",
    "PLAYWRIGHT_PROXY_URL",
    "PLAYWRIGHT_PROXY_BYPASS",
)
```
改成:
```python
RUNTIME_CONFIG_KEYS = (
    "CLOUDMAIL_FREE_DOMAIN",
    "PLAYWRIGHT_PROXY_URL",
    "PLAYWRIGHT_PROXY_BYPASS",
    "MAIL_PROVIDER",
)
```

- [ ] **Step 2: 在 `_normalize_runtime_value` 里处理 `MAIL_PROVIDER`**

把:
```python
def _normalize_runtime_value(key: str, value) -> str:
    text = str(value or "").strip()
    if key == "CLOUDMAIL_FREE_DOMAIN" and text and not text.startswith("@"):
        text = f"@{text}"
    return text
```
改成:
```python
def _normalize_runtime_value(key: str, value) -> str:
    text = str(value or "").strip()
    if key == "CLOUDMAIL_FREE_DOMAIN" and text and not text.startswith("@"):
        text = f"@{text}"
    if key == "MAIL_PROVIDER":
        text = text.lower()
        if text not in ("cloudmail", "outlook", ""):
            text = "cloudmail"
    return text
```

- [ ] **Step 3: 在文件末尾追加 helper**

```python
def get_mail_provider() -> str:
    """返回 'cloudmail' 或 'outlook',默认 'cloudmail'。"""
    value = get_runtime_value("MAIL_PROVIDER", default="cloudmail")
    return value or "cloudmail"
```

- [ ] **Step 4: ruff + 冒烟**

Run: `ruff check --fix src/autoteam/runtime_config.py && ruff format src/autoteam/runtime_config.py`

Run:
```bash
uv run python -c "
from autoteam.runtime_config import get_mail_provider, write_runtime_config
print('default:', get_mail_provider())
write_runtime_config({'MAIL_PROVIDER': 'outlook'})
print('after set outlook:', get_mail_provider())
write_runtime_config({'MAIL_PROVIDER': 'cloudmail'})
print('reset:', get_mail_provider())
"
```
Expected: 输出依次为 `default: cloudmail` / `after set outlook: outlook` / `reset: cloudmail`。

- [ ] **Step 5: Commit**

```bash
git add src/autoteam/runtime_config.py
git commit -m "feat(config): add MAIL_PROVIDER runtime key

Adds a 'cloudmail' | 'outlook' switch readable via get_mail_provider().
Hot-swappable via runtime_config.json without restart.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: `free_register.py` —— Provider 分支 + mark_used

**Files:**
- Modify: `src/autoteam/free_register.py:30-37, 47-96`

- [ ] **Step 1: 替换 `make_free_mail_client`**

把:
```python
def make_free_mail_client():
    """创建带 Free 域名的 CloudMail 客户端;未配置时抛 RuntimeError。"""
    domain = get_cloudmail_free_domain()
    if not domain:
        raise RuntimeError("CLOUDMAIL_FREE_DOMAIN not configured")
    client = CloudMailClient(domain=domain)
    client.login()
    return client
```
改成:
```python
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
```

- [ ] **Step 2: 在 `create_one_free_account` 注册成功分支调用 `mark_used`**

定位到 `create_one_free_account` 函数里这一段:
```python
auth_path = save_auth_file(bundle)
add_free_account(
    email=email,
    password=password,
    cloudmail_account_id=account_id,
    auth_file=str(auth_path),
    plan_type="free",
)
```
紧接着追加:
```python
        from autoteam.runtime_config import get_mail_provider
        if get_mail_provider() == "outlook":
            from autoteam.outlook_pool import mark_used as _outlook_mark_used
            _outlook_mark_used(email, registered_chatgpt_email=email)
```

- [ ] **Step 3: ruff**

Run: `ruff check --fix src/autoteam/free_register.py && ruff format src/autoteam/free_register.py`
Expected: 无报错。

- [ ] **Step 4: Commit**

```bash
git add src/autoteam/free_register.py
git commit -m "feat(free): switch mail client by MAIL_PROVIDER setting

make_free_mail_client now returns OutlookMailClient when MAIL_PROVIDER
is 'outlook'; otherwise the existing CloudMail path is unchanged. On
successful registration, the Outlook pool record is marked used so it
will not be claimed again.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: API 端点 —— 6 个 Outlook 池接口

**Files:**
- Modify: `src/autoteam/api.py` (在文件末尾的"挂载静态文件"之前追加)

- [ ] **Step 1: 在 api.py 顶部 imports 区追加**

```python
from autoteam import outlook_pool
from autoteam.outlook_imap import OutlookIMAP
from autoteam.outlook_oauth import (
    OutlookOAuthError,
    OutlookTokenRevokedError,
    get_access_token,
)
```

并在 pydantic models 区域(参考现有 `class XxxRequest(BaseModel)` 的位置)新增:

```python
class OutlookImportRequest(BaseModel):
    text: str
```

- [ ] **Step 2: 在路由区追加 6 个端点**

挑选位置:在现有 `/api/free/...` 路由组的紧后(grep `@app.post.*free` 找到),追加:

```python
@app.get("/api/outlook/pool")
async def list_outlook_pool(
    status: str | None = None,
    q: str | None = None,
    page: int = 1,
    size: int = 50,
    _=Depends(verify_api_key),
):
    rows = outlook_pool.load_pool()
    if status:
        rows = [r for r in rows if r.get("status") == status]
    if q:
        ql = q.lower()
        rows = [r for r in rows if ql in (r.get("email") or "").lower()]
    total = len(rows)
    rows.sort(key=lambda r: r.get("added_at") or 0, reverse=True)
    start = max(0, (page - 1) * size)
    page_rows = rows[start : start + size]

    sanitized = []
    for r in page_rows:
        item = dict(r)
        rt = item.get("refresh_token") or ""
        item["refresh_token_preview"] = (
            f"{rt[:8]}...{rt[-8:]}" if len(rt) > 16 else "***"
        )
        item.pop("refresh_token", None)
        item.pop("password", None)
        sanitized.append(item)
    return {"rows": sanitized, "total": total, "stats": outlook_pool.stats()}


@app.post("/api/outlook/pool/import")
async def import_outlook_pool(payload: OutlookImportRequest, _=Depends(verify_api_key)):
    return outlook_pool.import_from_text(payload.text)


@app.post("/api/outlook/pool/test/{email}")
async def test_outlook_account(email: str, _=Depends(verify_api_key)):
    record = outlook_pool.find(email)
    if record is None:
        raise HTTPException(status_code=404, detail="account not found")
    try:
        token = get_access_token(record)
        with OutlookIMAP(record["email"], token) as imap:
            imap.search_emails(limit=1)
        return {"ok": True}
    except OutlookTokenRevokedError as exc:
        return {"ok": False, "error": f"token_revoked: {exc}"}
    except OutlookOAuthError as exc:
        return {"ok": False, "error": f"oauth_error: {exc}"}
    except Exception as exc:
        return {"ok": False, "error": f"imap_error: {exc}"}


@app.post("/api/outlook/pool/reset/{email}")
async def reset_outlook_account(email: str, _=Depends(verify_api_key)):
    ok = outlook_pool.reset(email)
    if not ok:
        raise HTTPException(status_code=400, detail="cannot reset (already used or not found)")
    return {"ok": True}


@app.delete("/api/outlook/pool/{email}")
async def delete_outlook_account(email: str, _=Depends(verify_api_key)):
    ok = outlook_pool.delete(email)
    if not ok:
        raise HTTPException(status_code=404, detail="account not found")
    return {"ok": True}


@app.get("/api/outlook/pool/stats")
async def outlook_pool_stats(_=Depends(verify_api_key)):
    return outlook_pool.stats()
```

注:`Depends(verify_api_key)` 的具体名字见 api.py 现有用法,如该项目实际命名是 `verify_token` 或类似,改成对应名字。先 `grep -n 'Depends(' src/autoteam/api.py | head -5` 确认。

- [ ] **Step 3: ruff + 启动检查**

Run: `ruff check --fix src/autoteam/api.py && ruff format src/autoteam/api.py`

Run: `uv run autoteam api &` (后台启动),然后:
```bash
curl -sS -H "Authorization: Bearer $(grep API_KEY .env | cut -d= -f2)" \
  http://127.0.0.1:8787/api/outlook/pool/stats
```
Expected: 返回 `{"total":0,"available":0,"in_use":0,"used":0,"error":0}`(池为空时)。

杀掉后台进程:`kill %1` 或 `pkill -f 'autoteam api'`

- [ ] **Step 4: Commit**

```bash
git add src/autoteam/api.py
git commit -m "feat(api): outlook pool endpoints

Adds 6 endpoints: GET /api/outlook/pool, POST .../import,
POST .../test/{email}, POST .../reset/{email}, DELETE .../{email},
GET .../stats. List response masks refresh_token and omits password.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: 前端 API 包装 + 路由 + 侧边栏

**Files:**
- Modify: `web/src/api.js`
- Modify: `web/src/App.vue` (新增路由 `/mail-pool`)
- Modify: `web/src/components/Sidebar.vue`

- [ ] **Step 1: 在 `web/src/api.js` 的 `export const api = { ... }` 内追加方法**

在合适位置(比如 listFreeAccounts 之后)追加:
```javascript
  listOutlookPool: (params = {}) => {
    const qs = new URLSearchParams()
    if (params.status) qs.set('status', params.status)
    if (params.q) qs.set('q', params.q)
    if (params.page) qs.set('page', params.page)
    if (params.size) qs.set('size', params.size)
    const tail = qs.toString() ? `?${qs}` : ''
    return request('GET', `/outlook/pool${tail}`)
  },
  importOutlookPool: (text) => request('POST', '/outlook/pool/import', { text }),
  testOutlookAccount: (email) => request('POST', `/outlook/pool/test/${encodeURIComponent(email)}`),
  resetOutlookAccount: (email) => request('POST', `/outlook/pool/reset/${encodeURIComponent(email)}`),
  deleteOutlookAccount: (email) => request('DELETE', `/outlook/pool/${encodeURIComponent(email)}`),
  outlookPoolStats: () => request('GET', '/outlook/pool/stats'),
```

- [ ] **Step 2: 在 `web/src/App.vue` 增加邮箱池视图分支**

定位 App.vue 的视图切换逻辑(`v-if="page === 'free'"` 风格的条件),按既有 `FreePage` 的方式追加:
- import: `import MailPoolPage from './components/MailPoolPage.vue'`
- 模板里新增: `<MailPoolPage v-else-if="page === 'mail-pool'" />`

具体改法:在现有 `<FreePage v-else-if="page === 'free'" />` 紧后追加:
```vue
<MailPoolPage v-else-if="page === 'mail-pool'" />
```

并在 `<script setup>` 区 imports 处加:
```javascript
import MailPoolPage from './components/MailPoolPage.vue'
```

- [ ] **Step 3: 在 `Sidebar.vue` 的菜单数组里加一项**

定位 Sidebar.vue 的菜单数据(通常是 `const items = [...]` 或 template 里的循环),按现有项的格式新增一项:
```javascript
{ key: 'mail-pool', label: '邮箱池', icon: 'mail' }
```
icon 名按现有项目里使用的图标库决定;若图标体系是 emoji,用 ✉️。

- [ ] **Step 4: 浏览器烟雾验证**

Run: `cd web && npm run dev`,在浏览器打开 dev URL,登录后:
- 侧边栏出现"邮箱池"项
- 点击进入会报组件不存在(下个 Task 会建)

- [ ] **Step 5: Commit**

```bash
git add web/src/api.js web/src/App.vue web/src/components/Sidebar.vue
git commit -m "feat(web): wire outlook pool API client + sidebar entry

Adds JS API helpers for the 6 backend endpoints and a 'mail-pool' route
target. The actual page component arrives in the next commit.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 10: `MailPoolPage.vue`

**Files:**
- Create: `web/src/components/MailPoolPage.vue`

- [ ] **Step 1: 创建 `web/src/components/MailPoolPage.vue`**

参考现有 `FreePage.vue` 和 `PoolPage.vue` 的样式风格(Tailwind dark theme, app-card / app-chip 类)。完整骨架:

```vue
<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api.js'

const stats = ref({ total: 0, available: 0, in_use: 0, used: 0, error: 0 })
const rows = ref([])
const total = ref(0)
const filter = ref('all')
const search = ref('')
const page = ref(1)
const pageSize = 50
const importText = ref('')
const importing = ref(false)
const importResult = ref(null)
const loading = ref(false)
const showImport = ref(false)

async function refresh() {
  loading.value = true
  try {
    const params = { page: page.value, size: pageSize }
    if (filter.value !== 'all') params.status = filter.value
    if (search.value.trim()) params.q = search.value.trim()
    const data = await api.listOutlookPool(params)
    rows.value = data.rows || []
    total.value = data.total || 0
    stats.value = data.stats || stats.value
  } finally {
    loading.value = false
  }
}

async function doImport() {
  if (!importText.value.trim()) return
  importing.value = true
  try {
    importResult.value = await api.importOutlookPool(importText.value)
    importText.value = ''
    await refresh()
  } catch (exc) {
    importResult.value = { error: exc.message }
  } finally {
    importing.value = false
  }
}

async function testOne(email) {
  const result = await api.testOutlookAccount(email)
  alert(result.ok ? `${email} 连接成功` : `${email} 失败: ${result.error}`)
}

async function resetOne(email) {
  if (!confirm(`重置 ${email} 为可用?`)) return
  await api.resetOutlookAccount(email)
  await refresh()
}

async function deleteOne(email) {
  if (!confirm(`删除 ${email}?该操作不可逆`)) return
  await api.deleteOutlookAccount(email)
  await refresh()
}

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))

const statusBadge = (s) => ({
  available: { text: '可用', cls: 'bg-emerald-500/20 text-emerald-300' },
  in_use: { text: '使用中', cls: 'bg-sky-500/20 text-sky-300' },
  used: { text: '已用', cls: 'bg-slate-500/20 text-slate-300' },
  error: { text: '异常', cls: 'bg-rose-500/20 text-rose-300' },
}[s] || { text: s, cls: 'bg-slate-500/20 text-slate-300' })

onMounted(refresh)
</script>

<template>
  <div class="p-6 space-y-6">
    <h1 class="text-2xl font-bold text-white">邮箱池 / Outlook</h1>

    <div class="grid grid-cols-5 gap-3">
      <div class="app-card p-4">
        <div class="text-xs text-slate-400">总数</div>
        <div class="text-2xl font-bold text-white">{{ stats.total }}</div>
      </div>
      <div class="app-card p-4">
        <div class="text-xs text-emerald-300">可用</div>
        <div class="text-2xl font-bold text-emerald-300">{{ stats.available }}</div>
      </div>
      <div class="app-card p-4">
        <div class="text-xs text-sky-300">使用中</div>
        <div class="text-2xl font-bold text-sky-300">{{ stats.in_use }}</div>
      </div>
      <div class="app-card p-4">
        <div class="text-xs text-slate-400">已用</div>
        <div class="text-2xl font-bold text-slate-300">{{ stats.used }}</div>
      </div>
      <div class="app-card p-4">
        <div class="text-xs text-rose-300">异常</div>
        <div class="text-2xl font-bold text-rose-300">{{ stats.error }}</div>
      </div>
    </div>

    <div class="app-card p-4">
      <button class="text-sm text-cyan-300 mb-2" @click="showImport = !showImport">
        {{ showImport ? '收起' : '展开' }} 批量导入
      </button>
      <div v-if="showImport" class="space-y-2">
        <textarea
          v-model="importText"
          rows="10"
          class="w-full rounded-lg bg-slate-900/50 p-3 text-sm font-mono text-slate-200"
          placeholder="email----password----client_id----refresh_token&#10;每行一个,4 段或 5 段格式"
        />
        <div class="flex gap-2">
          <button
            class="rounded-lg bg-cyan-500/20 px-4 py-2 text-cyan-200"
            :disabled="importing"
            @click="doImport"
          >
            {{ importing ? '导入中...' : '导入' }}
          </button>
          <button class="rounded-lg bg-slate-500/20 px-4 py-2" @click="importText = ''">
            清空
          </button>
        </div>
        <div v-if="importResult" class="text-sm text-slate-300">
          <template v-if="importResult.error">
            <span class="text-rose-300">导入失败: {{ importResult.error }}</span>
          </template>
          <template v-else>
            成功 {{ importResult.imported }} / 跳过 {{ importResult.skipped }}
            / 解析失败 {{ importResult.errors?.length || 0 }}
            <ul v-if="importResult.errors?.length" class="mt-2 list-disc pl-6 text-rose-300">
              <li v-for="e in importResult.errors" :key="e.line">第 {{ e.line }} 行: {{ e.reason }}</li>
            </ul>
          </template>
        </div>
      </div>
    </div>

    <div class="app-card p-4 space-y-3">
      <div class="flex flex-wrap items-center gap-2">
        <button
          v-for="f in [['all', '全部'], ['available', '可用'], ['in_use', '使用中'], ['used', '已用'], ['error', '异常']]"
          :key="f[0]"
          class="rounded-lg px-3 py-1 text-sm"
          :class="filter === f[0] ? 'bg-cyan-500/30 text-cyan-200' : 'bg-slate-700/30 text-slate-300'"
          @click="filter = f[0]; page = 1; refresh()"
        >
          {{ f[1] }}
        </button>
        <input
          v-model="search"
          type="text"
          placeholder="按邮箱搜索"
          class="ml-auto rounded-lg bg-slate-900/50 px-3 py-1 text-sm text-slate-200"
          @keyup.enter="page = 1; refresh()"
        />
      </div>

      <table class="w-full text-sm">
        <thead class="text-left text-slate-400">
          <tr>
            <th class="py-2">邮箱</th>
            <th>状态</th>
            <th>添加</th>
            <th>已注册账号</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in rows" :key="r.email" class="border-t border-slate-700/30 text-slate-200">
            <td class="py-2 font-mono">{{ r.email }}</td>
            <td>
              <span class="rounded px-2 py-0.5 text-xs" :class="statusBadge(r.status).cls">
                {{ statusBadge(r.status).text }}
              </span>
              <span v-if="r.last_error" class="ml-1 text-xs text-rose-400" :title="r.last_error">⚠</span>
            </td>
            <td class="text-xs text-slate-400">
              {{ r.added_at ? new Date(r.added_at * 1000).toLocaleString() : '-' }}
            </td>
            <td class="text-xs text-slate-300">{{ r.registered_chatgpt_email || '-' }}</td>
            <td class="space-x-2">
              <button v-if="r.status !== 'used'" class="text-xs text-cyan-300" @click="testOne(r.email)">测试</button>
              <button
                v-if="r.status === 'error' || r.status === 'in_use'"
                class="text-xs text-amber-300"
                @click="resetOne(r.email)"
              >
                重置
              </button>
              <button class="text-xs text-rose-300" @click="deleteOne(r.email)">删除</button>
            </td>
          </tr>
          <tr v-if="!rows.length && !loading">
            <td colspan="5" class="py-6 text-center text-slate-500">池为空,请先批量导入。</td>
          </tr>
        </tbody>
      </table>

      <div class="flex items-center justify-between text-sm text-slate-400">
        <div>共 {{ total }} 条</div>
        <div class="space-x-2">
          <button :disabled="page <= 1" @click="page--; refresh()">‹</button>
          <span>{{ page }} / {{ totalPages }}</span>
          <button :disabled="page >= totalPages" @click="page++; refresh()">›</button>
        </div>
      </div>
    </div>
  </div>
</template>
```

- [ ] **Step 2: 重新加载 dev server,浏览器验证**

Run: `cd web && npm run dev`(若未在跑)

浏览器进 `/`,登录,点侧边栏"邮箱池":
- 顶部统计 5 张卡片显示 0
- 「批量导入」可展开,粘贴一行假数据后点导入,弹解析失败提示
- 列表显示「池为空」

- [ ] **Step 3: Commit**

```bash
git add web/src/components/MailPoolPage.vue
git commit -m "feat(web): add MailPoolPage with import, list, filter, single-row ops

Five-card stats header, collapsible bulk-import textarea, filter chips
plus search, paginated table, per-row test/reset/delete buttons.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 11: Settings 页 —— Free 注册分区 + provider 开关

**Files:**
- Modify: `web/src/components/Settings.vue`

- [ ] **Step 1: 阅读现有 Settings.vue 结构**

先 `grep -n 'CLOUDMAIL_FREE_DOMAIN\|runtime' web/src/components/Settings.vue` 找到现有运行时配置区(那里改 CLOUDMAIL_FREE_DOMAIN)。Free 分区按那个区段的样式追加。

- [ ] **Step 2: 在 Settings.vue 数据 / 表单里加 `mail_provider` 字段**

定位到现有用 `runtime_config` 双向绑定的 ref/reactive 对象(类似 `const runtime = ref({ CLOUDMAIL_FREE_DOMAIN: '' })`),把它扩展为:
```javascript
const runtime = ref({ CLOUDMAIL_FREE_DOMAIN: '', MAIL_PROVIDER: 'cloudmail', PLAYWRIGHT_PROXY_URL: '', PLAYWRIGHT_PROXY_BYPASS: '' })
```
保留原有字段。

加载逻辑沿用现有 `api.getRuntimeConfig()`(若名字不同,以实际为准),保存沿用现有 `api.saveRuntimeConfig(runtime.value)`。

- [ ] **Step 3: 添加 UI 区段(在 CloudMail 域名输入框附近)**

在现有 CloudMail 域名输入框上面或下面追加:
```vue
<section class="app-card p-5 space-y-3">
  <h3 class="text-base font-semibold text-white">Free 注册</h3>
  <div class="space-y-2">
    <label class="text-sm text-slate-300">邮箱提供商</label>
    <div class="flex gap-3">
      <label class="flex items-center gap-2">
        <input type="radio" value="cloudmail" v-model="runtime.MAIL_PROVIDER" />
        <span>CloudMail</span>
      </label>
      <label class="flex items-center gap-2">
        <input type="radio" value="outlook" v-model="runtime.MAIL_PROVIDER" />
        <span>Outlook</span>
        <a class="text-xs text-cyan-300 underline" href="#" @click.prevent="$emit('navigate', 'mail-pool')">
          (池可用 {{ outlookStats.available }} 个)
        </a>
      </label>
    </div>
    <p
      v-if="runtime.MAIL_PROVIDER === 'outlook' && outlookStats.available === 0"
      class="text-sm text-rose-300"
    >
      ⚠ Outlook 池为空,请先在「邮箱池」页导入。
    </p>
  </div>
</section>
```

并在 `<script setup>` 加:
```javascript
import { onMounted, ref } from 'vue'
const outlookStats = ref({ total: 0, available: 0, in_use: 0, used: 0, error: 0 })
async function loadOutlookStats() {
  try { outlookStats.value = await api.outlookPoolStats() } catch {}
}
onMounted(loadOutlookStats)
```

(若 Settings.vue 已 import `onMounted` 等,合并即可。)

- [ ] **Step 4: 处理 navigate 事件**

Settings.vue 通过 `$emit('navigate', 'mail-pool')` 让 App.vue 切页。在 App.vue 的 Settings 引用处加 `@navigate="page = $event"`:
```vue
<SettingsPage v-else-if="page === 'settings'" @navigate="page = $event" />
```
(若 component 名不同请替换。)

- [ ] **Step 5: 浏览器烟雾验证**

刷新页面,进 Settings,Free 注册分区出现 radio 按钮 + 池可用数链接。点 Outlook 后切换,保存。后端检查:
```bash
cat runtime_config.json
```
Expected: 包含 `"MAIL_PROVIDER": "outlook"`。

切回 cloudmail 保存,文件里 `MAIL_PROVIDER` 变 `cloudmail`。

- [ ] **Step 6: Commit**

```bash
git add web/src/components/Settings.vue web/src/App.vue
git commit -m "feat(web): mail provider switch in Settings

Adds 'Free 注册' section with CloudMail/Outlook radio. Shows live
'pool available' count linking to the pool page; warns if Outlook is
selected with an empty pool.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 12: 端到端冒烟验证 + 文档收尾

**Files:**
- 仅运行操作,无代码改动(除非验证发现 bug 需要回头修)

- [ ] **Step 1: 准备真实测试账户**

要求至少 1 个真实可用的 Outlook 账户(已知 refresh_token 未失效)。把那一行 `email----password----client_id----refresh_token` 准备好。

- [ ] **Step 2: 启动服务并导入**

Run: `uv run autoteam api`

用浏览器或 curl:
```bash
curl -sS -X POST -H "Authorization: Bearer $API_KEY" -H "Content-Type: application/json" \
  -d '{"text":"<your-line-here>"}' \
  http://127.0.0.1:8787/api/outlook/pool/import
```
Expected: `{"imported":1,"skipped":0,"errors":[]}`。

`outlook_pool.json` 应出现新文件,内含一条记录,status=available。

- [ ] **Step 3: 测试连接**

```bash
curl -sS -X POST -H "Authorization: Bearer $API_KEY" \
  http://127.0.0.1:8787/api/outlook/pool/test/<email>
```
Expected: `{"ok":true}`。如失败,看 `error` 字段诊断。

- [ ] **Step 4: 切到 Outlook 触发一次 Free 注册**

在 Web UI Settings 切到 Outlook,保存。

进 FreePage,点击"创建 1 个 Free 账号"。后端日志中应观察到:
- `[Outlook] claim 邮箱: <your-email>`
- `[Outlook OAuth] <email> access_token 获取成功`
- `[Outlook] 收到邮件: ...` (验证码)
- 注册流程后续日志同 CloudMail 路径

成功后:
- `outlook_pool.json` 中该条 status 变 `used`
- `free_accounts.json` 新增一条
- `auths/codex-...json` 新增文件

- [ ] **Step 5: error path 验证**

人为构造一个故意写错的 refresh_token(比如截断后 30 个字符)导入。注意:解析器会因长度过短拒绝。换法:让长度 ≥ 100 但内容是垃圾。导入成功后触发 Free 注册:
- 任务应失败,reason 包含 `refresh_token_revoked` 或 `oauth_error`
- 池中该账户状态变 `error`,`last_error` 字段填充

切回 CloudMail,池空时切 Outlook:Settings 页应显示「池已空」红字提示。

- [ ] **Step 6: 写一份简要的迁移说明**

在 `docs/configuration.md` 里追加 1 个小节(如果项目惯例需要),否则跳过。

- [ ] **Step 7: 最终 commit(若 Step 6 改了文档)**

```bash
git add docs/
git commit -m "docs: note MAIL_PROVIDER runtime switch

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review 备忘

- 每个 Task 末尾都有 commit;不要把多个 Task 合并 commit
- ruff 失败 / 浏览器运行失败 → 先修该 Task,**不要**跳到下一个
- spec §11 提到的"Dashboard Outlook 池卡片"作为后置项,本 plan 不包含
- 任何 method 重命名都要回头改所有调用处
- 若发现 spec 里某条要求在本 plan 里没对应任务,补上

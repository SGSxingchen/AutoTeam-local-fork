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
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        logger.exception("outlook_pool.json corrupt; treating as empty")
        return []
    return data if isinstance(data, list) else []


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


def _parse_line(line: str) -> tuple[dict | None, str | None]:
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
            record, err = _parse_line(line)
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
        target["status"] = "in_use"
        target["claimed_at"] = int(time.time())
        save_pool(rows)
        return dict(target)


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
    rec, err = _parse_line(sample.splitlines()[0])
    assert rec is not None and err is None, (rec, err)
    assert rec["email"] == "qpzst27553129@hotmail.com"
    assert rec["client_id"] == "9e5f94bc-e8a4-4e73-b8be-63364c29d753"
    print("[smoke] 4-field parse OK")

    rec2, err2 = _parse_line(sample.splitlines()[1])
    assert rec2 is None and "段数" in err2
    print("[smoke] short line rejected:", err2)

    rec3, err3 = _parse_line(sample.splitlines()[2])
    assert rec3 is None and err3 is not None
    print("[smoke] bad uuid rejected:", err3)

    print("[smoke] all parser checks passed")

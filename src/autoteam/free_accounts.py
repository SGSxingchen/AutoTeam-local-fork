"""Free 账号池 - 与 Team accounts.json 完全分离的持久化存储。"""

import json
import time
from pathlib import Path

from autoteam.accounts import load_accounts
from autoteam.textio import read_text, write_text

PROJECT_ROOT = Path(__file__).parent.parent.parent
FREE_ACCOUNTS_FILE = PROJECT_ROOT / "free_accounts.json"


def _normalized_email(value):
    return (value or "").strip().lower()


def load_free_accounts():
    if not FREE_ACCOUNTS_FILE.exists():
        return []
    text = read_text(FREE_ACCOUNTS_FILE).strip()
    if not text:
        return []
    return json.loads(text)


def save_free_accounts(rows):
    write_text(FREE_ACCOUNTS_FILE, json.dumps(rows, indent=2, ensure_ascii=False))


def find_free_account(email):
    target = _normalized_email(email)
    for acc in load_free_accounts():
        if _normalized_email(acc.get("email")) == target:
            return acc
    return None


def _email_in_team_accounts(email):
    target = _normalized_email(email)
    return any(_normalized_email(acc.get("email")) == target for acc in load_accounts())


def add_free_account(email, password, cloudmail_account_id, auth_file, plan_type):
    """新增 Free 账号；email 必须既不在 free_accounts.json 也不在 accounts.json。"""
    if find_free_account(email):
        raise ValueError(f"email {email!r} already in free accounts")
    if _email_in_team_accounts(email):
        raise ValueError(f"email {email!r} already in team accounts")

    rows = load_free_accounts()
    rows.append(
        {
            "email": email,
            "password": password,
            "cloudmail_account_id": cloudmail_account_id,
            "auth_file": auth_file,
            "plan_type": plan_type,
            "created_at": time.time(),
            "last_refreshed_at": None,
            "last_error": None,
        }
    )
    save_free_accounts(rows)


def update_free_account(email, **fields):
    target = _normalized_email(email)
    rows = load_free_accounts()
    for acc in rows:
        if _normalized_email(acc.get("email")) == target:
            acc.update(fields)
            save_free_accounts(rows)
            return acc
    return None


def delete_free_account(email):
    target = _normalized_email(email)
    rows = load_free_accounts()
    new_rows = [acc for acc in rows if _normalized_email(acc.get("email")) != target]
    if len(new_rows) == len(rows):
        return False
    save_free_accounts(new_rows)
    return True

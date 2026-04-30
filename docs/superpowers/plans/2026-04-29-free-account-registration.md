# Free Account Registration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add automated batch registration of ChatGPT Free accounts as a parallel track to the existing Team registration, with separate domain config, separate persistence, Codex OAuth, CPA sync, and Web/CLI management — without touching any rotation logic.

**Architecture:** Free accounts live in a new `free_accounts.json`; a new `free_register.py` orchestrates registration by reusing `_register_direct_once` (manager.py) and `login_codex_via_browser` (codex_auth.py). `sync_to_cpa()` is extended to include both Team-active and all Free auth files. New `/api/free/*` endpoints + a Vue page mirror the existing `PoolPage` flow, and `autoteam add-free [N]` mirrors `autoteam add`.

**Tech Stack:** Python 3.10+ / FastAPI / Playwright / Vue 3 / pytest with `tmp_path` + `monkeypatch`. No new third-party dependencies.

---

## Spec Reference

This plan implements `docs/superpowers/specs/2026-04-29-free-account-registration-design.md`. If conflicts arise between plan and spec, follow the spec.

## File Map

**Backend (new):**
- `src/autoteam/free_accounts.py` — CRUD over `free_accounts.json`
- `src/autoteam/free_register.py` — registration orchestration (single, batch, delete, refresh)

**Backend (modified):**
- `src/autoteam/cloudmail.py` — accept optional `domain` in `__init__`
- `src/autoteam/config.py` — add `CLOUDMAIL_FREE_DOMAIN`
- `src/autoteam/cpa_sync.py` — merge free auth files into upload set
- `src/autoteam/manager.py` — add `cmd_add_free` + CLI subcommand
- `src/autoteam/api.py` — add 4 `/api/free/*` endpoints
- `.env.example` — new env var

**Frontend (new):**
- `web/src/components/FreePage.vue`

**Frontend (modified):**
- `web/src/api.js` — 4 client methods
- `web/src/components/Sidebar.vue` — nav entry
- `web/src/App.vue` — route

**Tests (new):**
- `tests/unit/test_free_accounts.py`
- `tests/unit/test_free_register.py`
- `tests/unit/test_cpa_sync_free_merge.py`
- `tests/unit/test_cloudmail_domain_override.py`

---

## Task 1: Config — `CLOUDMAIL_FREE_DOMAIN` env var

**Files:**
- Modify: `src/autoteam/config.py:35` (after `CLOUDMAIL_DOMAIN`)
- Modify: `.env.example:5` (after `CLOUDMAIL_DOMAIN=`)

- [ ] **Step 1: Add the constant in config.py**

In `src/autoteam/config.py`, immediately after the line:
```python
CLOUDMAIL_DOMAIN = os.environ.get("CLOUDMAIL_DOMAIN", "")
```
add:
```python
# Free 注册专用域名（必须与 CLOUDMAIL_DOMAIN 不同；空字符串 = Free 功能不可用）
CLOUDMAIL_FREE_DOMAIN = os.environ.get("CLOUDMAIL_FREE_DOMAIN", "")
```

- [ ] **Step 2: Document in .env.example**

In `.env.example`, after the `CLOUDMAIL_DOMAIN=` line, add:
```
# Free 账号注册的独立域名（必须与 CLOUDMAIL_DOMAIN 不同，否则会被自动加入 Team）
# 留空则禁用 Free 注册功能
CLOUDMAIL_FREE_DOMAIN=
```

- [ ] **Step 3: Verify import works**

Run:
```bash
uv run python -c "from autoteam.config import CLOUDMAIL_FREE_DOMAIN; print(repr(CLOUDMAIL_FREE_DOMAIN))"
```
Expected: prints `''` (or whatever was in `.env`).

- [ ] **Step 4: Commit**

```bash
git add src/autoteam/config.py .env.example
git commit -m "feat(config): 新增 CLOUDMAIL_FREE_DOMAIN 环境变量"
```

---

## Task 2: CloudMailClient — accept optional `domain` override

**Files:**
- Modify: `src/autoteam/cloudmail.py:29-79`
- Test: `tests/unit/test_cloudmail_domain_override.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_cloudmail_domain_override.py`:

```python
from unittest.mock import patch

from autoteam.cloudmail import CloudMailClient


def test_default_domain_used_when_no_override(monkeypatch):
    monkeypatch.setattr("autoteam.cloudmail.CLOUDMAIL_DOMAIN", "@team.example.com")

    client = CloudMailClient()
    client.token = "fake-token"

    captured = {}

    def fake_post(path, data=None):
        captured["email"] = data["email"]
        return {"code": 200, "data": {"accountId": 1}}

    with patch.object(client, "_post", side_effect=fake_post):
        client.create_temp_email(prefix="abc")

    assert captured["email"] == "abc@team.example.com"


def test_explicit_domain_overrides_default(monkeypatch):
    monkeypatch.setattr("autoteam.cloudmail.CLOUDMAIL_DOMAIN", "@team.example.com")

    client = CloudMailClient(domain="@free.example.com")
    client.token = "fake-token"

    captured = {}

    def fake_post(path, data=None):
        captured["email"] = data["email"]
        return {"code": 200, "data": {"accountId": 2}}

    with patch.object(client, "_post", side_effect=fake_post):
        client.create_temp_email(prefix="abc")

    assert captured["email"] == "abc@free.example.com"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_cloudmail_domain_override.py -v`
Expected: FAIL — `__init__` does not yet accept `domain`.

- [ ] **Step 3: Implement domain override**

In `src/autoteam/cloudmail.py`, modify `__init__` and `create_temp_email`:

```python
class CloudMailClient:
    def __init__(self, domain=None):
        self.base_url = CLOUDMAIL_BASE_URL
        self.token = None
        self.session = requests.Session()
        # 显式传入 domain 覆盖默认 CLOUDMAIL_DOMAIN（用于 Free 注册的独立域名）
        self._domain = domain if domain is not None else CLOUDMAIL_DOMAIN

    # ... (other methods unchanged)

    def create_temp_email(self, prefix=None):
        """创建临时邮箱地址，返回 (accountId, email)"""
        if prefix is None:
            prefix = f"tmp-{uuid.uuid4().hex[:8]}"
        email = f"{prefix}{self._domain}"

        resp = self._post("/account/add", {"email": email})
        if resp["code"] != 200:
            raise Exception(f"创建邮箱失败: {resp.get('message')}")

        account_id = resp["data"]["accountId"]
        logger.info("[CloudMail] 临时邮箱已创建: %s (accountId=%s)", email, account_id)
        return account_id, email
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_cloudmail_domain_override.py tests/unit/test_cloudmail.py -v`
Expected: all PASS. Existing `test_cloudmail.py` should still pass since default behavior is preserved.

- [ ] **Step 5: Commit**

```bash
git add src/autoteam/cloudmail.py tests/unit/test_cloudmail_domain_override.py
git commit -m "feat(cloudmail): CloudMailClient 支持构造时覆盖 domain"
```

---

## Task 3: `free_accounts.py` — CRUD module

**Files:**
- Create: `src/autoteam/free_accounts.py`
- Create: `tests/unit/test_free_accounts.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_free_accounts.py`:

```python
import pytest

from autoteam import accounts, free_accounts


def _patch_files(tmp_path, monkeypatch):
    monkeypatch.setattr(accounts, "ACCOUNTS_FILE", tmp_path / "accounts.json")
    monkeypatch.setattr(accounts, "get_admin_email", lambda: "")
    monkeypatch.setattr(free_accounts, "FREE_ACCOUNTS_FILE", tmp_path / "free_accounts.json")


def test_load_returns_empty_when_file_missing(tmp_path, monkeypatch):
    _patch_files(tmp_path, monkeypatch)
    assert free_accounts.load_free_accounts() == []


def test_add_persists_record(tmp_path, monkeypatch):
    _patch_files(tmp_path, monkeypatch)

    free_accounts.add_free_account(
        email="user@free.example.com",
        password="pw",
        cloudmail_account_id=42,
        auth_file="/abs/auth.json",
        plan_type="free",
    )

    rows = free_accounts.load_free_accounts()
    assert len(rows) == 1
    row = rows[0]
    assert row["email"] == "user@free.example.com"
    assert row["password"] == "pw"
    assert row["cloudmail_account_id"] == 42
    assert row["auth_file"] == "/abs/auth.json"
    assert row["plan_type"] == "free"
    assert row["created_at"] > 0
    assert row["last_refreshed_at"] is None
    assert row["last_error"] is None


def test_find_returns_record_or_none(tmp_path, monkeypatch):
    _patch_files(tmp_path, monkeypatch)
    free_accounts.add_free_account("a@free.example.com", "pw", None, None, "free")

    assert free_accounts.find_free_account("a@free.example.com")["email"] == "a@free.example.com"
    assert free_accounts.find_free_account("missing@free.example.com") is None


def test_update_modifies_fields(tmp_path, monkeypatch):
    _patch_files(tmp_path, monkeypatch)
    free_accounts.add_free_account("a@free.example.com", "pw", None, None, "free")

    updated = free_accounts.update_free_account(
        "a@free.example.com",
        last_refreshed_at=1730000000.0,
        last_error="bad",
    )
    assert updated["last_refreshed_at"] == 1730000000.0
    assert updated["last_error"] == "bad"

    rows = free_accounts.load_free_accounts()
    assert rows[0]["last_error"] == "bad"


def test_update_returns_none_when_missing(tmp_path, monkeypatch):
    _patch_files(tmp_path, monkeypatch)
    assert free_accounts.update_free_account("missing@x.com", last_error="x") is None


def test_delete_removes_record(tmp_path, monkeypatch):
    _patch_files(tmp_path, monkeypatch)
    free_accounts.add_free_account("a@free.example.com", "pw", None, None, "free")

    assert free_accounts.delete_free_account("a@free.example.com") is True
    assert free_accounts.load_free_accounts() == []


def test_delete_returns_false_when_missing(tmp_path, monkeypatch):
    _patch_files(tmp_path, monkeypatch)
    assert free_accounts.delete_free_account("missing@x.com") is False


def test_add_rejects_duplicate_in_free_table(tmp_path, monkeypatch):
    _patch_files(tmp_path, monkeypatch)
    free_accounts.add_free_account("a@free.example.com", "pw", None, None, "free")

    with pytest.raises(ValueError, match="already in free accounts"):
        free_accounts.add_free_account("a@free.example.com", "pw2", None, None, "free")


def test_add_rejects_email_present_in_team_accounts(tmp_path, monkeypatch):
    _patch_files(tmp_path, monkeypatch)
    accounts.add_account("shared@x.com", "pw", cloudmail_account_id=1)

    with pytest.raises(ValueError, match="already in team accounts"):
        free_accounts.add_free_account("shared@x.com", "pw", None, None, "free")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_free_accounts.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'autoteam.free_accounts'`.

- [ ] **Step 3: Implement the module**

Create `src/autoteam/free_accounts.py`:

```python
"""Free 账号池 - 与 Team accounts.json 完全分离的持久化存储。"""

import json
import time
from pathlib import Path

from autoteam.accounts import find_account, load_accounts
from autoteam.textio import read_text, write_text

PROJECT_ROOT = Path(__file__).parent.parent.parent
FREE_ACCOUNTS_FILE = PROJECT_ROOT / "free_accounts.json"


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
    for acc in load_free_accounts():
        if acc["email"] == email:
            return acc
    return None


def add_free_account(email, password, cloudmail_account_id, auth_file, plan_type):
    """新增 Free 账号；email 必须既不在 free_accounts.json 也不在 accounts.json。"""
    if find_free_account(email):
        raise ValueError(f"email {email!r} already in free accounts")
    if find_account(load_accounts(), email):
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
    rows = load_free_accounts()
    for acc in rows:
        if acc["email"] == email:
            acc.update(fields)
            save_free_accounts(rows)
            return acc
    return None


def delete_free_account(email):
    rows = load_free_accounts()
    new_rows = [a for a in rows if a["email"] != email]
    if len(new_rows) == len(rows):
        return False
    save_free_accounts(new_rows)
    return True
```

- [ ] **Step 4: Run tests to verify all pass**

Run: `uv run pytest tests/unit/test_free_accounts.py -v`
Expected: all 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/autoteam/free_accounts.py tests/unit/test_free_accounts.py
git commit -m "feat(free): free_accounts 持久化模块（CRUD + 唯一性校验）"
```

---

## Task 4: `cpa_sync.py` — merge free auth files into upload set

**Files:**
- Modify: `src/autoteam/cpa_sync.py:518-580` (the `sync_to_cpa` function body)
- Create: `tests/unit/test_cpa_sync_free_merge.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_cpa_sync_free_merge.py`:

```python
"""验证 sync_to_cpa 正确合并 Team active + 全部 Free auth 文件。"""

from unittest.mock import patch

from autoteam import accounts, cpa_sync, free_accounts


def test_sync_to_cpa_uploads_team_active_and_all_free(tmp_path, monkeypatch):
    auth_dir = tmp_path / "auths"
    auth_dir.mkdir()

    # Team auth file (active)
    team_auth = auth_dir / "codex-team@x.com-team-aaa.json"
    team_auth.write_text("{}")
    # Team auth file (exhausted — should NOT upload)
    team_exhausted_auth = auth_dir / "codex-exh@x.com-team-bbb.json"
    team_exhausted_auth.write_text("{}")
    # Free auth file
    free_auth = auth_dir / "codex-free@y.com-free-ccc.json"
    free_auth.write_text("{}")

    monkeypatch.setattr(cpa_sync, "AUTH_DIR", auth_dir)
    monkeypatch.setattr(accounts, "ACCOUNTS_FILE", tmp_path / "accounts.json")
    monkeypatch.setattr(accounts, "get_admin_email", lambda: "")
    monkeypatch.setattr(free_accounts, "FREE_ACCOUNTS_FILE", tmp_path / "free_accounts.json")

    accounts.save_accounts(
        [
            {
                "email": "team@x.com",
                "status": accounts.STATUS_ACTIVE,
                "auth_file": str(team_auth),
            },
            {
                "email": "exh@x.com",
                "status": accounts.STATUS_EXHAUSTED,
                "auth_file": str(team_exhausted_auth),
            },
        ]
    )
    free_accounts.save_free_accounts(
        [
            {
                "email": "free@y.com",
                "auth_file": str(free_auth),
                "plan_type": "free",
                "created_at": 0,
                "last_refreshed_at": None,
                "last_error": None,
                "cloudmail_account_id": None,
                "password": "pw",
            }
        ]
    )

    uploads = []

    def fake_upload(path):
        uploads.append(str(path))
        return True

    deletions = []

    def fake_delete(name):
        deletions.append(name)
        return True

    with patch.object(cpa_sync, "list_cpa_files", return_value=[]), \
         patch.object(cpa_sync, "upload_to_cpa", side_effect=fake_upload), \
         patch.object(cpa_sync, "delete_from_cpa", side_effect=fake_delete):
        cpa_sync.sync_to_cpa()

    uploaded_names = sorted(p.rsplit("/", 1)[-1] for p in uploads)
    assert uploaded_names == [
        "codex-free@y.com-free-ccc.json",
        "codex-team@x.com-team-aaa.json",
    ]
    assert deletions == []


def test_sync_to_cpa_does_not_delete_free_auth_present_in_cpa(tmp_path, monkeypatch):
    """CPA 上有 Free 文件、本地也有该 Free 记录 → 不应删除。"""
    auth_dir = tmp_path / "auths"
    auth_dir.mkdir()
    free_auth = auth_dir / "codex-free@y.com-free-ccc.json"
    free_auth.write_text("{}")

    monkeypatch.setattr(cpa_sync, "AUTH_DIR", auth_dir)
    monkeypatch.setattr(accounts, "ACCOUNTS_FILE", tmp_path / "accounts.json")
    monkeypatch.setattr(accounts, "get_admin_email", lambda: "")
    monkeypatch.setattr(free_accounts, "FREE_ACCOUNTS_FILE", tmp_path / "free_accounts.json")
    accounts.save_accounts([])
    free_accounts.save_free_accounts(
        [
            {
                "email": "free@y.com",
                "auth_file": str(free_auth),
                "plan_type": "free",
                "created_at": 0,
                "last_refreshed_at": None,
                "last_error": None,
                "cloudmail_account_id": None,
                "password": "pw",
            }
        ]
    )

    cpa_listing = [{"name": free_auth.name, "email": "free@y.com"}]
    deletions = []

    with patch.object(cpa_sync, "list_cpa_files", return_value=cpa_listing), \
         patch.object(cpa_sync, "upload_to_cpa", return_value=True), \
         patch.object(cpa_sync, "delete_from_cpa", side_effect=lambda n: deletions.append(n) or True):
        cpa_sync.sync_to_cpa()

    assert deletions == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_cpa_sync_free_merge.py -v`
Expected: FAIL — current `sync_to_cpa` does not look at `free_accounts`.

- [ ] **Step 3: Implement the merge**

Modify `src/autoteam/cpa_sync.py:518` (`sync_to_cpa` function). Locate the block:

```python
    accounts = load_accounts()
    local_emails = {a["email"].lower() for a in accounts}
```

and the block:

```python
    # active 账号的认证文件
    active_files = {}
    for acc in accounts:
        if acc["status"] == STATUS_ACTIVE and acc.get("auth_file"):
            path = Path(acc["auth_file"])
            if path.exists():
                active_files[path.name] = path
```

Replace the function body's account-loading + active-files-collection with:

```python
def sync_to_cpa():
    """
    同步本地认证文件到 CPA：
    - Team active + 全部 Free → 应当存在于 CPA（上传/覆盖）
    - 本地管理的邮箱在 CPA 中但不在上述集合 → 删除
    """
    from autoteam.accounts import STATUS_ACTIVE, load_accounts, save_accounts
    from autoteam.free_accounts import load_free_accounts

    accounts = load_accounts()
    free_rows = load_free_accounts()

    local_emails = {a["email"].lower() for a in accounts}
    local_emails.update(f["email"].lower() for f in free_rows)

    local_duplicates_deleted, accounts_path_repaired = _cleanup_local_duplicates(accounts)
    if accounts_path_repaired:
        save_accounts(accounts)

    # 修复 team 断裂的 auth_file 路径
    changed = False
    for acc in accounts:
        auth_path = acc.get("auth_file")
        if auth_path and not Path(auth_path).exists():
            matches = list(AUTH_DIR.glob(f"codex-{acc['email']}-*.json"))
            if matches:
                acc["auth_file"] = str(matches[0].resolve())
                changed = True
    if changed:
        save_accounts(accounts)

    active_files = {}
    # Team: 仅 active
    for acc in accounts:
        if acc["status"] == STATUS_ACTIVE and acc.get("auth_file"):
            path = Path(acc["auth_file"])
            if path.exists():
                active_files[path.name] = path
    # Free: 全部
    for facc in free_rows:
        auth_path = facc.get("auth_file")
        if auth_path:
            path = Path(auth_path)
            if path.exists():
                active_files[path.name] = path

    # CPA 认证文件
    cpa_files = list_cpa_files()
    cpa_names = {f["name"]: f for f in cpa_files}

    logger.info("[CPA] 应同步认证文件: %d, CPA 认证文件: %d", len(active_files), len(cpa_files))

    # 上传：所有应同步文件（覆盖同名文件，确保 token 最新）
    uploaded = 0
    for name, path in active_files.items():
        logger.info("[CPA] 上传: %s", name)
        if upload_to_cpa(path):
            uploaded += 1

    # 删除：CPA 中有但不在应同步集合的（仅限本地管理的账号）
    deleted = 0
    for name, cpa_file in cpa_names.items():
        email = cpa_file.get("email", "").lower()
        if email in local_emails and name not in active_files:
            logger.info("[CPA] 删除非 active 文件: %s (%s)", name, email)
            if delete_from_cpa(name):
                deleted += 1

    logger.info("[CPA] 同步完成: 上传 %d, 删除 %d, 本地去重 %d", uploaded, deleted, local_duplicates_deleted)

    # 最终状态
    final_cpa = list_cpa_files()
    final_local_managed = [f for f in final_cpa if f.get("email", "").lower() in local_emails]
    logger.info("[CPA] CPA 中本地管理: %d, 应同步: %d", len(final_local_managed), len(active_files))
```

- [ ] **Step 4: Run tests to verify**

Run: `uv run pytest tests/unit/test_cpa_sync_free_merge.py -v`
Expected: both tests PASS.

- [ ] **Step 5: Run full test suite to catch regressions**

Run: `uv run pytest tests/ -v`
Expected: all PASS (no existing test should regress).

- [ ] **Step 6: Commit**

```bash
git add src/autoteam/cpa_sync.py tests/unit/test_cpa_sync_free_merge.py
git commit -m "feat(cpa): sync_to_cpa 合并 Team active + 全部 Free 认证"
```

---

## Task 5: `free_register.py` — single-account creation

**Files:**
- Create: `src/autoteam/free_register.py`
- Create: `tests/unit/test_free_register.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_free_register.py`:

```python
from unittest.mock import MagicMock

from autoteam import accounts, free_accounts, free_register


def _patch_state(tmp_path, monkeypatch):
    monkeypatch.setattr(accounts, "ACCOUNTS_FILE", tmp_path / "accounts.json")
    monkeypatch.setattr(accounts, "get_admin_email", lambda: "")
    monkeypatch.setattr(free_accounts, "FREE_ACCOUNTS_FILE", tmp_path / "free_accounts.json")
    monkeypatch.setattr(free_register, "CLOUDMAIL_FREE_DOMAIN", "@free.example.com")


def test_create_free_account_success(tmp_path, monkeypatch):
    _patch_state(tmp_path, monkeypatch)

    mail_client = MagicMock()
    mail_client.create_temp_email.return_value = (777, "abc@free.example.com")
    mail_client.delete_account.return_value = True

    monkeypatch.setattr(free_register, "_register_direct_once", lambda *a, **k: True)
    monkeypatch.setattr(
        free_register,
        "login_codex_via_browser",
        lambda email, password, mail_client=None: {
            "access_token": "at",
            "refresh_token": "rt",
            "id_token": "it",
            "account_id": "aid",
            "email": email,
            "plan_type": "free",
        },
    )
    monkeypatch.setattr(free_register, "save_auth_file", lambda bundle: tmp_path / f"codex-{bundle['email']}-free-x.json")
    monkeypatch.setattr(free_register, "upload_to_cpa", lambda path: True)

    result = free_register.create_one_free_account(mail_client)

    assert result["status"] == "ok"
    assert result["email"] == "abc@free.example.com"
    assert mail_client.delete_account.call_count == 0
    rows = free_accounts.load_free_accounts()
    assert len(rows) == 1
    assert rows[0]["email"] == "abc@free.example.com"
    assert rows[0]["plan_type"] == "free"


def test_create_free_account_register_failure_rolls_back(tmp_path, monkeypatch):
    _patch_state(tmp_path, monkeypatch)

    mail_client = MagicMock()
    mail_client.create_temp_email.return_value = (777, "abc@free.example.com")

    monkeypatch.setattr(free_register, "_register_direct_once", lambda *a, **k: False)

    result = free_register.create_one_free_account(mail_client)

    assert result["status"] == "failed"
    assert result["reason"] == "register_failed_3x"
    mail_client.delete_account.assert_called_once_with(777)
    assert free_accounts.load_free_accounts() == []


def test_create_free_account_codex_failure_rolls_back(tmp_path, monkeypatch):
    _patch_state(tmp_path, monkeypatch)

    mail_client = MagicMock()
    mail_client.create_temp_email.return_value = (777, "abc@free.example.com")

    monkeypatch.setattr(free_register, "_register_direct_once", lambda *a, **k: True)
    monkeypatch.setattr(free_register, "login_codex_via_browser", lambda *a, **k: None)

    result = free_register.create_one_free_account(mail_client)

    assert result["status"] == "failed"
    assert result["reason"] == "codex_oauth_failed"
    mail_client.delete_account.assert_called_once_with(777)
    assert free_accounts.load_free_accounts() == []


def test_create_free_account_plan_mismatch_rolls_back(tmp_path, monkeypatch):
    _patch_state(tmp_path, monkeypatch)

    mail_client = MagicMock()
    mail_client.create_temp_email.return_value = (777, "abc@free.example.com")

    monkeypatch.setattr(free_register, "_register_direct_once", lambda *a, **k: True)
    monkeypatch.setattr(
        free_register,
        "login_codex_via_browser",
        lambda *a, **k: {"plan_type": "team", "email": "abc@free.example.com"},
    )

    result = free_register.create_one_free_account(mail_client)

    assert result["status"] == "failed"
    assert result["reason"] == "plan_type_mismatch"
    mail_client.delete_account.assert_called_once_with(777)
    assert free_accounts.load_free_accounts() == []


def test_create_free_account_cpa_upload_failure_keeps_record(tmp_path, monkeypatch):
    """CPA 上传失败不应回滚本地记录（下次 sync 会补上）。"""
    _patch_state(tmp_path, monkeypatch)

    mail_client = MagicMock()
    mail_client.create_temp_email.return_value = (777, "abc@free.example.com")

    monkeypatch.setattr(free_register, "_register_direct_once", lambda *a, **k: True)
    monkeypatch.setattr(
        free_register,
        "login_codex_via_browser",
        lambda *a, **k: {
            "access_token": "at", "refresh_token": "rt", "id_token": "it",
            "account_id": "aid", "email": "abc@free.example.com", "plan_type": "free",
        },
    )
    monkeypatch.setattr(free_register, "save_auth_file", lambda bundle: tmp_path / "codex-x.json")

    def boom(path):
        raise RuntimeError("CPA down")
    monkeypatch.setattr(free_register, "upload_to_cpa", boom)

    result = free_register.create_one_free_account(mail_client)

    assert result["status"] == "ok"
    assert len(free_accounts.load_free_accounts()) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_free_register.py -v`
Expected: FAIL — `free_register` module doesn't exist.

- [ ] **Step 3: Implement `free_register.py` (single-account path)**

Create `src/autoteam/free_register.py`:

```python
"""Free 账号注册编排 - 单条创建、批量创建、删除、刷新。

复用 manager._register_direct_once（浏览器注册流程）和
codex_auth.login_codex_via_browser（Codex OAuth 流程），不参与轮转。
"""

import logging
import time
import uuid

from autoteam.cloudmail import CloudMailClient
from autoteam.codex_auth import login_codex_via_browser, save_auth_file
from autoteam.config import CLOUDMAIL_FREE_DOMAIN
from autoteam.cpa_sync import upload_to_cpa
from autoteam.free_accounts import add_free_account

logger = logging.getLogger(__name__)


def _import_register_direct_once():
    # 避免顶层循环 import：manager.py 反过来也会 import 本模块
    from autoteam.manager import _register_direct_once
    return _register_direct_once


# 测试时 monkeypatch 用的别名（让 monkeypatch.setattr(free_register, "_register_direct_once", ...) 可工作）
def _register_direct_once(*args, **kwargs):
    return _import_register_direct_once()(*args, **kwargs)


def create_one_free_account(mail_client):
    """执行一次 Free 账号创建。返回 {status, email?, reason?}。"""
    account_id = None
    email = None
    try:
        account_id, email = mail_client.create_temp_email()
        password = f"Tmp_{uuid.uuid4().hex[:12]}!"

        ok = _register_direct_once(mail_client, email, password, cloudmail_account_id=account_id)
        if not ok:
            mail_client.delete_account(account_id)
            return {"status": "failed", "email": email, "reason": "register_failed_3x"}

        bundle = login_codex_via_browser(email, password, mail_client=mail_client)
        if not bundle:
            mail_client.delete_account(account_id)
            return {"status": "failed", "email": email, "reason": "codex_oauth_failed"}

        if bundle.get("plan_type") != "free":
            logger.warning(
                "[Free] 注册产物 plan_type=%s 而非 free，可能域名配错。回滚: %s",
                bundle.get("plan_type"), email,
            )
            mail_client.delete_account(account_id)
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
            try:
                mail_client.delete_account(account_id)
            except Exception:
                pass
        return {"status": "failed", "email": email, "reason": f"unexpected:{exc}"}


def make_free_mail_client():
    """创建带 Free 域名的 CloudMail 客户端；未配置时抛 RuntimeError。"""
    if not CLOUDMAIL_FREE_DOMAIN:
        raise RuntimeError("CLOUDMAIL_FREE_DOMAIN not configured")
    client = CloudMailClient(domain=CLOUDMAIL_FREE_DOMAIN)
    client.login()
    return client
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_free_register.py -v`
Expected: 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/autoteam/free_register.py tests/unit/test_free_register.py
git commit -m "feat(free): free_register 单条创建（含失败回滚）"
```

---

## Task 6: `free_register.py` — batch creation

**Files:**
- Modify: `src/autoteam/free_register.py`
- Modify: `tests/unit/test_free_register.py`

- [ ] **Step 1: Add the failing batch test**

Append to `tests/unit/test_free_register.py`:

```python
def test_batch_creation_aggregates_results(tmp_path, monkeypatch):
    _patch_state(tmp_path, monkeypatch)

    # 1st email: success; 2nd: register fails; 3rd: success
    mail_client = MagicMock()
    mail_client.create_temp_email.side_effect = [
        (1, "a@free.example.com"),
        (2, "b@free.example.com"),
        (3, "c@free.example.com"),
    ]
    monkeypatch.setattr(free_register, "make_free_mail_client", lambda: mail_client)

    register_results = iter([True, False, True])
    monkeypatch.setattr(
        free_register,
        "_register_direct_once",
        lambda *a, **k: next(register_results),
    )
    monkeypatch.setattr(
        free_register,
        "login_codex_via_browser",
        lambda email, password, mail_client=None: {
            "access_token": "at", "refresh_token": "rt", "id_token": "it",
            "account_id": "aid", "email": email, "plan_type": "free",
        },
    )
    monkeypatch.setattr(free_register, "save_auth_file", lambda bundle: tmp_path / f"codex-{bundle['email']}.json")
    monkeypatch.setattr(free_register, "upload_to_cpa", lambda path: True)

    result = free_register.create_free_accounts_batch(3)

    assert result["count"] == 3
    assert result["succeeded"] == ["a@free.example.com", "c@free.example.com"]
    assert [f["email"] for f in result["failed"]] == ["b@free.example.com"]
    assert result["failed"][0]["reason"] == "register_failed_3x"
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/unit/test_free_register.py::test_batch_creation_aggregates_results -v`
Expected: FAIL — `create_free_accounts_batch` not yet defined.

- [ ] **Step 3: Implement batch**

Append to `src/autoteam/free_register.py`:

```python
def create_free_accounts_batch(count):
    """批量创建 Free 账号；遇到单次失败不阻塞后续。"""
    if not (1 <= count <= 50):
        raise ValueError("count must be in 1..50")

    mail_client = make_free_mail_client()
    succeeded = []
    failed = []
    try:
        for i in range(count):
            logger.info("[Free] 批量进度 %d/%d", i + 1, count)
            res = create_one_free_account(mail_client)
            if res["status"] == "ok":
                succeeded.append(res["email"])
            else:
                failed.append({"email": res.get("email"), "reason": res.get("reason")})
    finally:
        # CloudMailClient 没有 close，靠 GC；保留 try/finally 以便将来扩展
        pass

    return {"count": count, "succeeded": succeeded, "failed": failed}
```

- [ ] **Step 4: Run all free_register tests**

Run: `uv run pytest tests/unit/test_free_register.py -v`
Expected: 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/autoteam/free_register.py tests/unit/test_free_register.py
git commit -m "feat(free): free_register 批量创建"
```

---

## Task 7: `free_register.py` — delete with cleanup

**Files:**
- Modify: `src/autoteam/free_register.py`
- Modify: `tests/unit/test_free_register.py`

- [ ] **Step 1: Add the failing test**

Append to `tests/unit/test_free_register.py`:

```python
def test_delete_full_cleans_cpa_auth_cloudmail_and_record(tmp_path, monkeypatch):
    _patch_state(tmp_path, monkeypatch)

    auth_file = tmp_path / "codex-a@free.example.com-free-x.json"
    auth_file.write_text("{}")
    free_accounts.save_free_accounts(
        [
            {
                "email": "a@free.example.com",
                "password": "pw",
                "cloudmail_account_id": 99,
                "auth_file": str(auth_file),
                "plan_type": "free",
                "created_at": 0,
                "last_refreshed_at": None,
                "last_error": None,
            }
        ]
    )

    deletions = []
    monkeypatch.setattr(free_register, "delete_from_cpa", lambda name: deletions.append(name) or True)
    mail_client = MagicMock()
    monkeypatch.setattr(free_register, "make_free_mail_client", lambda: mail_client)

    result = free_register.delete_free_account_full("a@free.example.com")

    assert result["status"] == "ok"
    assert deletions == [auth_file.name]
    assert not auth_file.exists()
    mail_client.delete_account.assert_called_once_with(99)
    assert free_accounts.load_free_accounts() == []


def test_delete_full_404_when_missing(tmp_path, monkeypatch):
    _patch_state(tmp_path, monkeypatch)

    result = free_register.delete_free_account_full("missing@x.com")
    assert result["status"] == "not_found"


def test_delete_full_idempotent_when_subresources_already_gone(tmp_path, monkeypatch):
    """auth 文件已不在 / CPA 上无该文件 / CloudMail 删除报错 → 仍然成功。"""
    _patch_state(tmp_path, monkeypatch)

    free_accounts.save_free_accounts(
        [
            {
                "email": "a@free.example.com",
                "password": "pw",
                "cloudmail_account_id": 99,
                "auth_file": str(tmp_path / "missing.json"),  # 文件不存在
                "plan_type": "free",
                "created_at": 0,
                "last_refreshed_at": None,
                "last_error": None,
            }
        ]
    )

    monkeypatch.setattr(free_register, "delete_from_cpa", lambda name: False)
    mail_client = MagicMock()
    mail_client.delete_account.side_effect = RuntimeError("already gone")
    monkeypatch.setattr(free_register, "make_free_mail_client", lambda: mail_client)

    result = free_register.delete_free_account_full("a@free.example.com")

    assert result["status"] == "ok"
    assert free_accounts.load_free_accounts() == []
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/unit/test_free_register.py::test_delete_full_cleans_cpa_auth_cloudmail_and_record -v`
Expected: FAIL — function not defined.

- [ ] **Step 3: Implement delete**

Append to `src/autoteam/free_register.py`:

```python
from pathlib import Path

from autoteam.cpa_sync import delete_from_cpa
from autoteam.free_accounts import delete_free_account, find_free_account


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
```

> Note: keep the `from pathlib import Path` and the two new imports at the top of the file with the other imports (move them rather than leaving an inline import). Doing it inline here just to make the diff easier to read in this plan — when applying, **place imports at the top of the file**.

- [ ] **Step 4: Run all free_register tests**

Run: `uv run pytest tests/unit/test_free_register.py -v`
Expected: 9 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/autoteam/free_register.py tests/unit/test_free_register.py
git commit -m "feat(free): free_register 全量删除（CPA+auth+CloudMail+记录，幂等）"
```

---

## Task 8: `free_register.py` — refresh Codex token

**Files:**
- Modify: `src/autoteam/free_register.py`
- Modify: `tests/unit/test_free_register.py`

- [ ] **Step 1: Add the failing test**

Append to `tests/unit/test_free_register.py`:

```python
def test_refresh_codex_success_updates_record_and_uploads(tmp_path, monkeypatch):
    _patch_state(tmp_path, monkeypatch)

    free_accounts.save_free_accounts(
        [
            {
                "email": "a@free.example.com",
                "password": "pw",
                "cloudmail_account_id": 1,
                "auth_file": str(tmp_path / "old.json"),
                "plan_type": "free",
                "created_at": 0,
                "last_refreshed_at": None,
                "last_error": "stale",
            }
        ]
    )

    new_path = tmp_path / "new.json"
    new_path.write_text("{}")

    monkeypatch.setattr(free_register, "make_free_mail_client", lambda: MagicMock())
    monkeypatch.setattr(
        free_register,
        "login_codex_via_browser",
        lambda email, password, mail_client=None: {
            "access_token": "at", "refresh_token": "rt", "id_token": "it",
            "account_id": "aid", "email": email, "plan_type": "free",
        },
    )
    monkeypatch.setattr(free_register, "save_auth_file", lambda bundle: new_path)
    uploaded = []
    monkeypatch.setattr(free_register, "upload_to_cpa", lambda path: uploaded.append(str(path)) or True)

    result = free_register.refresh_codex("a@free.example.com")

    assert result["status"] == "ok"
    assert uploaded == [str(new_path)]
    row = free_accounts.find_free_account("a@free.example.com")
    assert row["auth_file"] == str(new_path)
    assert row["last_error"] is None
    assert row["last_refreshed_at"] is not None


def test_refresh_codex_failure_writes_last_error_and_keeps_old_auth(tmp_path, monkeypatch):
    _patch_state(tmp_path, monkeypatch)

    free_accounts.save_free_accounts(
        [
            {
                "email": "a@free.example.com",
                "password": "pw",
                "cloudmail_account_id": 1,
                "auth_file": str(tmp_path / "old.json"),
                "plan_type": "free",
                "created_at": 0,
                "last_refreshed_at": None,
                "last_error": None,
            }
        ]
    )

    monkeypatch.setattr(free_register, "make_free_mail_client", lambda: MagicMock())
    monkeypatch.setattr(free_register, "login_codex_via_browser", lambda *a, **k: None)

    result = free_register.refresh_codex("a@free.example.com")

    assert result["status"] == "failed"
    assert result["reason"] == "codex_oauth_failed"
    row = free_accounts.find_free_account("a@free.example.com")
    assert row["last_error"] == "codex_oauth_failed"
    assert row["auth_file"] == str(tmp_path / "old.json")  # 旧的没被清


def test_refresh_codex_404_when_missing(tmp_path, monkeypatch):
    _patch_state(tmp_path, monkeypatch)
    result = free_register.refresh_codex("missing@x.com")
    assert result["status"] == "not_found"
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/unit/test_free_register.py::test_refresh_codex_success_updates_record_and_uploads -v`
Expected: FAIL — function not defined.

- [ ] **Step 3: Implement refresh**

Append to `src/autoteam/free_register.py`:

```python
from autoteam.free_accounts import update_free_account


def refresh_codex(email):
    """重跑 Codex OAuth → 覆盖 auth → 重传 CPA → 更新记录。"""
    acc = find_free_account(email)
    if not acc:
        return {"status": "not_found", "email": email}

    mail_client = make_free_mail_client()
    bundle = login_codex_via_browser(acc["email"], acc["password"], mail_client=mail_client)
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
```

> Move the `update_free_account` import to the top of the file alongside other imports.

- [ ] **Step 4: Run all free_register tests**

Run: `uv run pytest tests/unit/test_free_register.py -v`
Expected: 12 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/autoteam/free_register.py tests/unit/test_free_register.py
git commit -m "feat(free): free_register 刷新 Codex token"
```

---

## Task 9: API endpoints — `/api/free/*`

**Files:**
- Modify: `src/autoteam/api.py` (insert new endpoints + Pydantic model near other free endpoints)
- Create: `tests/unit/test_api_free.py`

> **Architecture note:** Use the existing `_start_task` helper so background tasks queue serially through the Playwright lock. `GET` is synchronous; `POST` (create), `DELETE`, and `POST refresh` all enqueue tasks.

- [ ] **Step 1: Write the failing test (FastAPI TestClient)**

Create `tests/unit/test_api_free.py`:

```python
"""GET /api/free/accounts 与未配置降级行为。后台任务行为通过 free_register 单测覆盖。"""

from fastapi.testclient import TestClient

from autoteam import accounts, api as api_module, free_accounts


def _patch_state(tmp_path, monkeypatch):
    monkeypatch.setattr(accounts, "ACCOUNTS_FILE", tmp_path / "accounts.json")
    monkeypatch.setattr(accounts, "get_admin_email", lambda: "")
    monkeypatch.setattr(free_accounts, "FREE_ACCOUNTS_FILE", tmp_path / "free_accounts.json")
    monkeypatch.setattr(api_module, "API_KEY", "")  # 跳过鉴权


def test_get_free_accounts_empty(tmp_path, monkeypatch):
    _patch_state(tmp_path, monkeypatch)
    monkeypatch.setattr(api_module, "CLOUDMAIL_FREE_DOMAIN", "@free.example.com")

    client = TestClient(api_module.app)
    r = client.get("/api/free/accounts")
    assert r.status_code == 200
    assert r.json() == {"enabled": True, "accounts": []}


def test_get_free_accounts_returns_sanitized(tmp_path, monkeypatch):
    _patch_state(tmp_path, monkeypatch)
    monkeypatch.setattr(api_module, "CLOUDMAIL_FREE_DOMAIN", "@free.example.com")

    auth_file = tmp_path / "codex-a@free.example.com-free-x.json"
    auth_file.write_text("{}")
    free_accounts.save_free_accounts(
        [
            {
                "email": "a@free.example.com",
                "password": "secret-must-not-leak",
                "cloudmail_account_id": 1,
                "auth_file": str(auth_file),
                "plan_type": "free",
                "created_at": 1700000000.0,
                "last_refreshed_at": None,
                "last_error": None,
            }
        ]
    )

    client = TestClient(api_module.app)
    r = client.get("/api/free/accounts")
    assert r.status_code == 200
    body = r.json()
    assert body["enabled"] is True
    assert len(body["accounts"]) == 1
    item = body["accounts"][0]
    assert item["email"] == "a@free.example.com"
    assert item["plan_type"] == "free"
    assert item["auth_file_exists"] is True
    assert "password" not in item


def test_get_free_accounts_missing_auth_file(tmp_path, monkeypatch):
    _patch_state(tmp_path, monkeypatch)
    monkeypatch.setattr(api_module, "CLOUDMAIL_FREE_DOMAIN", "@free.example.com")

    free_accounts.save_free_accounts(
        [
            {
                "email": "a@free.example.com",
                "password": "pw",
                "cloudmail_account_id": 1,
                "auth_file": str(tmp_path / "gone.json"),
                "plan_type": "free",
                "created_at": 0,
                "last_refreshed_at": None,
                "last_error": None,
            }
        ]
    )

    client = TestClient(api_module.app)
    r = client.get("/api/free/accounts")
    assert r.json()["accounts"][0]["auth_file_exists"] is False


def test_disabled_when_domain_not_configured(tmp_path, monkeypatch):
    _patch_state(tmp_path, monkeypatch)
    monkeypatch.setattr(api_module, "CLOUDMAIL_FREE_DOMAIN", "")

    client = TestClient(api_module.app)

    r = client.get("/api/free/accounts")
    assert r.status_code == 200
    assert r.json() == {"enabled": False, "reason": "CLOUDMAIL_FREE_DOMAIN not set", "accounts": []}

    r = client.post("/api/free/accounts", json={"count": 1})
    assert r.status_code == 503

    r = client.delete("/api/free/accounts/a@free.example.com")
    assert r.status_code == 503

    r = client.post("/api/free/accounts/a@free.example.com/refresh")
    assert r.status_code == 503


def test_post_count_validation(tmp_path, monkeypatch):
    _patch_state(tmp_path, monkeypatch)
    monkeypatch.setattr(api_module, "CLOUDMAIL_FREE_DOMAIN", "@free.example.com")

    client = TestClient(api_module.app)
    r = client.post("/api/free/accounts", json={"count": 0})
    assert r.status_code == 400

    r = client.post("/api/free/accounts", json={"count": 51})
    assert r.status_code == 400
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/unit/test_api_free.py -v`
Expected: FAIL — endpoints not yet defined.

- [ ] **Step 3: Add the endpoints**

In `src/autoteam/api.py`, locate the existing `class CleanupParams(BaseModel):` block (around line 461) and add a new param model nearby:

```python
class FreeCreateParams(BaseModel):
    count: int = 1
```

Add a top-level import near the other config imports (around line 1675-1683 there's a block of `from autoteam.config import ...` — add to it):

```python
from autoteam.config import CLOUDMAIL_FREE_DOMAIN
```

Place the new endpoints next to the existing free-form task endpoints (just before `@app.get("/api/tasks")` at line 1653). Insert:

```python
# ---------------------------------------------------------------------------
# Free 账号管理
# ---------------------------------------------------------------------------


def _free_disabled_response():
    raise HTTPException(status_code=503, detail={
        "enabled": False,
        "reason": "CLOUDMAIL_FREE_DOMAIN not set",
    })


@app.get("/api/free/accounts")
def get_free_accounts():
    from autoteam.free_accounts import load_free_accounts

    if not CLOUDMAIL_FREE_DOMAIN:
        return {"enabled": False, "reason": "CLOUDMAIL_FREE_DOMAIN not set", "accounts": []}

    rows = load_free_accounts()
    sanitized = []
    for row in rows:
        auth_file = row.get("auth_file") or ""
        sanitized.append({
            "email": row["email"],
            "plan_type": row.get("plan_type"),
            "created_at": row.get("created_at"),
            "last_refreshed_at": row.get("last_refreshed_at"),
            "last_error": row.get("last_error"),
            "auth_file_exists": bool(auth_file) and Path(auth_file).exists(),
        })
    return {"enabled": True, "accounts": sanitized}


@app.post("/api/free/accounts", status_code=202)
def post_free_accounts(params: FreeCreateParams):
    if not CLOUDMAIL_FREE_DOMAIN:
        _free_disabled_response()

    if not (1 <= params.count <= 50):
        raise HTTPException(status_code=400, detail="count must be in 1..50")

    from autoteam.free_register import create_free_accounts_batch

    task = _start_task("free.create", create_free_accounts_batch, {"count": params.count}, params.count)
    return task


@app.delete("/api/free/accounts/{email}", status_code=202)
def delete_free_account_endpoint(email: str):
    if not CLOUDMAIL_FREE_DOMAIN:
        _free_disabled_response()

    from autoteam.free_register import delete_free_account_full

    task = _start_task("free.delete", delete_free_account_full, {"email": email}, email)
    return task


@app.post("/api/free/accounts/{email}/refresh", status_code=202)
def post_free_account_refresh(email: str):
    if not CLOUDMAIL_FREE_DOMAIN:
        _free_disabled_response()

    from autoteam.free_register import refresh_codex

    task = _start_task("free.refresh", refresh_codex, {"email": email}, email)
    return task
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/unit/test_api_free.py -v`
Expected: 5 tests PASS.

- [ ] **Step 5: Run full unit-test suite for regressions**

Run: `uv run pytest tests/ -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add src/autoteam/api.py tests/unit/test_api_free.py
git commit -m "feat(api): /api/free/* 端点（列表、批量创建、删除、刷新）"
```

---

## Task 10: CLI — `autoteam add-free [N]`

**Files:**
- Modify: `src/autoteam/manager.py:1859` (insert `cmd_add_free` near `cmd_add` / `cmd_manual_add`)
- Modify: `src/autoteam/manager.py:2418` (CLI subparser registration)
- Modify: `src/autoteam/manager.py:2470` (route)
- Create: `tests/unit/test_cmd_add_free.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_cmd_add_free.py`:

```python
import pytest

from autoteam import manager


def test_cmd_add_free_invalid_domain_exits(monkeypatch, capsys):
    monkeypatch.setattr(manager, "CLOUDMAIL_FREE_DOMAIN", "")

    with pytest.raises(SystemExit) as exc:
        manager.cmd_add_free(1)
    assert exc.value.code == 1


def test_cmd_add_free_invalid_count_exits(monkeypatch):
    monkeypatch.setattr(manager, "CLOUDMAIL_FREE_DOMAIN", "@x.com")

    with pytest.raises(SystemExit) as exc:
        manager.cmd_add_free(0)
    assert exc.value.code == 1

    with pytest.raises(SystemExit) as exc:
        manager.cmd_add_free(51)
    assert exc.value.code == 1


def test_cmd_add_free_calls_batch_and_sync(monkeypatch):
    monkeypatch.setattr(manager, "CLOUDMAIL_FREE_DOMAIN", "@x.com")

    calls = {}

    def fake_batch(n):
        calls["batch"] = n
        return {"count": n, "succeeded": ["a@x.com"], "failed": []}

    def fake_sync():
        calls["synced"] = True

    monkeypatch.setattr("autoteam.free_register.create_free_accounts_batch", fake_batch)
    monkeypatch.setattr("autoteam.cpa_sync.sync_to_cpa", fake_sync)

    manager.cmd_add_free(2)
    assert calls == {"batch": 2, "synced": True}
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/unit/test_cmd_add_free.py -v`
Expected: FAIL — `cmd_add_free` not defined.

- [ ] **Step 3: Implement the command**

In `src/autoteam/manager.py`, near the top alongside other config imports, add:

```python
from autoteam.config import CLOUDMAIL_FREE_DOMAIN
```

Right after `cmd_manual_add` (around line 1891), insert:

```python
def cmd_add_free(count):
    """批量注册 Free 账号（使用 CLOUDMAIL_FREE_DOMAIN 域名）。"""
    if not CLOUDMAIL_FREE_DOMAIN:
        logger.error("[Free] 未配置 CLOUDMAIL_FREE_DOMAIN，无法启用 Free 注册")
        sys.exit(1)
    if not (1 <= count <= 50):
        logger.error("[Free] count 需在 1..50 范围内，收到 %s", count)
        sys.exit(1)

    from autoteam.cpa_sync import sync_to_cpa
    from autoteam.free_register import create_free_accounts_batch

    result = create_free_accounts_batch(count)
    sync_to_cpa()
    logger.info(
        "[Free] 完成: 成功 %d, 失败 %d (%s)",
        len(result["succeeded"]),
        len(result["failed"]),
        ", ".join(f"{f['email']}:{f['reason']}" for f in result["failed"]) or "无失败",
    )
```

In the `main()` function, register the subparser. Find the line near `sub.add_parser("manual-add", ...)` (around line 2419) and add right after:

```python
    add_free_p = sub.add_parser("add-free", help="批量注册 Free 账号（独立域名，不参与轮转）")
    add_free_p.add_argument("count", type=int, nargs="?", default=1, help="数量（默认 1，最大 50）")
```

In the dispatch chain (around line 2470, after `elif args.command == "manual-add":`), add:

```python
    elif args.command == "add-free":
        cmd_add_free(args.count)
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/unit/test_cmd_add_free.py -v`
Expected: 3 tests PASS.

- [ ] **Step 5: Smoke-test CLI argument parsing**

Run: `uv run autoteam add-free --help`
Expected: prints help text including `count` positional arg.

- [ ] **Step 6: Commit**

```bash
git add src/autoteam/manager.py tests/unit/test_cmd_add_free.py
git commit -m "feat(cli): autoteam add-free [N] 子命令"
```

---

## Task 11: Frontend `api.js` — 4 client methods

**Files:**
- Modify: `web/src/api.js`

- [ ] **Step 1: Add the four methods**

In `web/src/api.js`, inside the `export const api = {` object (between `getCpaFiles` and `startAdminLogin` is a good spot — keep grouping with related calls), add:

```javascript
  listFreeAccounts: () => request('GET', '/free/accounts'),
  createFreeAccounts: (count) => request('POST', '/free/accounts', { count }),
  deleteFreeAccount: (email) => request('DELETE', `/free/accounts/${encodeURIComponent(email)}`),
  refreshFreeAccount: (email) => request('POST', `/free/accounts/${encodeURIComponent(email)}/refresh`),
```

- [ ] **Step 2: Verify build still passes**

Run:
```bash
cd web && npm run build
```
Expected: build succeeds (no syntax errors).

- [ ] **Step 3: Commit**

```bash
git add web/src/api.js
git commit -m "feat(web): api.js 增加 free 账号四个方法"
```

---

## Task 12: Frontend `FreePage.vue`

**Files:**
- Create: `web/src/components/FreePage.vue`

- [ ] **Step 1: Create the component**

Create `web/src/components/FreePage.vue`:

```vue
<template>
  <section class="space-y-6">
    <div v-if="!loaded" class="app-card p-6 text-slate-300">加载中...</div>

    <div v-else-if="!enabled" class="app-card p-6 space-y-3 text-slate-300">
      <h2 class="text-lg font-semibold text-white">Free 账号注册未启用</h2>
      <p>请在 <code>.env</code> 中配置 <code>CLOUDMAIL_FREE_DOMAIN=@your-domain.com</code> 后重启服务。</p>
      <p class="text-amber-300 text-sm">⚠️ 该域名必须与 <code>CLOUDMAIL_DOMAIN</code> 不同，否则新注册的账号会被自动拉进 Team。</p>
    </div>

    <template v-else>
      <div class="app-card p-5 space-y-4">
        <div class="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 class="text-lg font-semibold text-white">Free 账号</h2>
            <p class="mt-1 text-sm text-slate-400">独立域名注册，不参与 Team 轮转。Codex 认证会同步到 CPA。</p>
          </div>
          <div class="flex items-end gap-2">
            <label class="text-sm text-slate-300">
              数量
              <input
                v-model.number="count"
                type="number"
                min="1"
                max="50"
                class="ml-2 w-20 rounded-lg border border-white/10 bg-white/5 px-2 py-1 text-white"
              />
            </label>
            <button
              @click="onCreate"
              :disabled="busy"
              class="app-button-primary"
            >
              {{ busy ? '任务进行中…' : '批量创建' }}
            </button>
            <button @click="reload" :disabled="busy" class="app-button-secondary">刷新</button>
          </div>
        </div>

        <p v-if="message" class="text-sm" :class="messageTone">{{ message }}</p>
      </div>

      <div class="app-card overflow-hidden">
        <table class="w-full table-fixed text-sm">
          <thead class="bg-white/5 text-slate-400">
            <tr>
              <th class="p-3 text-left">邮箱</th>
              <th class="p-3 text-left w-32">创建时间</th>
              <th class="p-3 text-left w-32">最后刷新</th>
              <th class="p-3 text-left w-20">auth</th>
              <th class="p-3 text-right w-44">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="accounts.length === 0">
              <td colspan="5" class="p-6 text-center text-slate-400">还没有 Free 账号</td>
            </tr>
            <tr v-for="acc in accounts" :key="acc.email" class="border-t border-white/5">
              <td class="p-3 truncate" :title="acc.email">{{ acc.email }}</td>
              <td class="p-3 text-slate-400">{{ fmt(acc.created_at) }}</td>
              <td class="p-3 text-slate-400">{{ acc.last_refreshed_at ? fmt(acc.last_refreshed_at) : '—' }}</td>
              <td class="p-3">
                <span v-if="acc.auth_file_exists" class="text-emerald-400">✅</span>
                <span v-else class="text-rose-400" :title="acc.last_error || ''">❌</span>
              </td>
              <td class="p-3 text-right space-x-2">
                <button @click="onRefresh(acc.email)" :disabled="busy" class="app-button-secondary text-xs">刷新</button>
                <button @click="onDelete(acc.email)" :disabled="busy" class="app-button-danger text-xs">删除</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </section>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { api } from '../api.js'

const loaded = ref(false)
const enabled = ref(false)
const accounts = ref([])
const count = ref(1)
const message = ref('')
const messageTone = ref('text-slate-400')
const currentTaskId = ref(null)
let pollTimer = null

const busy = computed(() => currentTaskId.value !== null)

function fmt(ts) {
  if (!ts) return '—'
  const d = new Date(ts * 1000)
  return d.toLocaleString('zh-CN', { hour12: false })
}

function setMessage(text, tone = 'info') {
  message.value = text
  messageTone.value = {
    info: 'text-slate-400',
    success: 'text-emerald-300',
    warn: 'text-amber-300',
    error: 'text-rose-300',
  }[tone] || 'text-slate-400'
}

async function reload() {
  try {
    const data = await api.listFreeAccounts()
    enabled.value = data.enabled
    accounts.value = data.accounts || []
  } catch (e) {
    setMessage(`加载失败: ${e.message}`, 'error')
  } finally {
    loaded.value = true
  }
}

function startPolling(taskId, label) {
  currentTaskId.value = taskId
  setMessage(`${label}进行中…`, 'info')
  pollTimer = setInterval(async () => {
    try {
      const t = await api.getTask(taskId)
      if (t.status === 'completed' || t.status === 'failed') {
        clearInterval(pollTimer)
        pollTimer = null
        currentTaskId.value = null
        if (t.status === 'completed') {
          const r = t.result || {}
          if (typeof r.succeeded !== 'undefined') {
            setMessage(`${label}完成: 成功 ${r.succeeded.length}, 失败 ${r.failed.length}`,
              r.failed.length === 0 ? 'success' : 'warn')
          } else if (r.status === 'ok') {
            setMessage(`${label}完成`, 'success')
          } else {
            setMessage(`${label}完成: ${r.reason || r.status || '未知'}`, 'warn')
          }
        } else {
          setMessage(`${label}失败: ${t.error || '未知错误'}`, 'error')
        }
        await reload()
      }
    } catch (e) {
      clearInterval(pollTimer)
      pollTimer = null
      currentTaskId.value = null
      setMessage(`查询任务失败: ${e.message}`, 'error')
    }
  }, 2000)
}

async function onCreate() {
  const n = Number(count.value) || 0
  if (n < 1 || n > 50) {
    setMessage('数量需在 1..50', 'warn')
    return
  }
  try {
    const task = await api.createFreeAccounts(n)
    startPolling(task.task_id, `创建 ${n} 个 Free 账号`)
  } catch (e) {
    setMessage(`提交创建失败: ${e.message}`, 'error')
  }
}

async function onDelete(email) {
  if (!confirm(`确定删除 ${email}？\n会同时删除 CPA / 本地 auth / CloudMail 临时邮箱。`)) return
  try {
    const task = await api.deleteFreeAccount(email)
    startPolling(task.task_id, `删除 ${email}`)
  } catch (e) {
    setMessage(`提交删除失败: ${e.message}`, 'error')
  }
}

async function onRefresh(email) {
  try {
    const task = await api.refreshFreeAccount(email)
    startPolling(task.task_id, `刷新 ${email}`)
  } catch (e) {
    setMessage(`提交刷新失败: ${e.message}`, 'error')
  }
}

onMounted(reload)
onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>
```

- [ ] **Step 2: Build to confirm no syntax errors**

Run:
```bash
cd web && npm run build
```
Expected: build succeeds.

- [ ] **Step 3: Commit**

```bash
git add web/src/components/FreePage.vue
git commit -m "feat(web): FreePage 组件（列表/批量创建/删除/刷新）"
```

---

## Task 13: Sidebar nav + App.vue route integration

**Files:**
- Modify: `web/src/components/Sidebar.vue:151-207` (the `items` array)
- Modify: `web/src/App.vue:198-204` (route block) + `web/src/App.vue:247` (import)

- [ ] **Step 1: Add Sidebar nav item**

In `web/src/components/Sidebar.vue`, find the `items` array (around line 150). Right after the `pool` entry (the one with `key: 'pool'`), insert:

```javascript
  {
    key: 'free',
    label: 'Free 账号',
    mobileLabel: 'Free',
    copy: '独立域名注册的 Free 账号管理',
    iconPath: 'M12 4v16M4 12h16',
  },
```

- [ ] **Step 2: Wire route in App.vue**

In `web/src/App.vue`, near `import PoolPage from './components/PoolPage.vue'` (around line 247) add:

```javascript
import FreePage from './components/FreePage.vue'
```

In the `<main>` template (around line 198, where `<PoolPage v-else-if="currentPage === 'pool'" .../>` lives), add right after the `PoolPage` block:

```vue
            <FreePage v-else-if="currentPage === 'free'" />
```

- [ ] **Step 3: Build**

Run:
```bash
cd web && npm run build
```
Expected: success.

- [ ] **Step 4: Manual smoke test in dev mode**

Run (in two terminals):
```bash
# Terminal A
uv run autoteam api

# Terminal B
cd web && npm run dev
```
Open `http://localhost:5173`, log in. Verify:
- "Free 账号" entry appears in the sidebar between "账号池操作" and "同步中心".
- Click it: if `CLOUDMAIL_FREE_DOMAIN` is empty, page shows the "未启用" notice.
- If `CLOUDMAIL_FREE_DOMAIN` is set, page shows the empty list with create/refresh controls.

(Don't actually click "创建" yet — that touches real CloudMail/ChatGPT and is reserved for Task 14.)

- [ ] **Step 5: Commit**

```bash
git add web/src/components/Sidebar.vue web/src/App.vue
git commit -m "feat(web): Sidebar 与 App 接入 Free 页面路由"
```

---

## Task 14: End-to-end smoke validation

> No automated test substitutes for this. Run on a machine with working CloudMail + CPA + Playwright.

- [ ] **Step 1: Configure environment**

In `.env`:
```
CLOUDMAIL_FREE_DOMAIN=@<your-second-domain>
```
(Must be different from `CLOUDMAIL_DOMAIN` and not configured to auto-join Team.)

- [ ] **Step 2: CLI single-account creation**

Run:
```bash
uv run autoteam add-free 1
```
Expected:
- A new email like `tmp-xxx@<free-domain>` registers successfully
- `free_accounts.json` has one new row with `plan_type: "free"`
- `auths/codex-<email>-free-<hash>.json` exists
- CPA shows that file (verify via `uv run autoteam status` or the Web Sync page)

- [ ] **Step 3: CLI batch with one expected failure**

Run:
```bash
uv run autoteam add-free 3
```
Expected: 3 attempts run sequentially; final log line shows `成功 N, 失败 M`. Even if some fail (Cloudflare, etc.), failed ones do **not** leave entries in `free_accounts.json` and **do** delete their CloudMail temp email.

- [ ] **Step 4: Web flow**

With `uv run autoteam api` running, open the panel, navigate to "Free 账号":
- Click "批量创建" with count 1 → task progress visible → list refreshes with the new row
- Click "刷新" on a row → task fires → `last_refreshed_at` updates
- Click "删除" → confirm → row disappears, auth file gone, CPA file removed (verify via Sync page or CLI `uv run autoteam status`)

- [ ] **Step 5: Regression check on Team rotation**

Run:
```bash
uv run autoteam status
uv run autoteam rotate 5
```
Expected: Team rotation logic behaves identically to before. No Free entries appear in Team listings.

- [ ] **Step 6: Final commit (only if any tweaks needed during smoke testing)**

If smoke testing required any small fixes, commit them:

```bash
git add -p   # review and stage minimal fixes
git commit -m "fix(free): smoke-test 反馈的细节调整"
```

If nothing needed fixing, no commit needed.

---

## Definition of Done

- [ ] All 14 tasks complete with their commits.
- [ ] `uv run pytest tests/ -v` all pass.
- [ ] `uv run ruff check src/` clean.
- [ ] `cd web && npm run build` succeeds.
- [ ] Smoke test (Task 14) passed against a real CloudMail + CPA setup.
- [ ] `git log --oneline` shows ~13 focused commits matching the task names.
- [ ] No regression in `autoteam rotate` / `autoteam fill` / Team flows.

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

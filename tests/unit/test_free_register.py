from unittest.mock import MagicMock

from autoteam import accounts, free_accounts, free_register


def _patch_state(tmp_path, monkeypatch):
    monkeypatch.setattr(accounts, "ACCOUNTS_FILE", tmp_path / "accounts.json")
    monkeypatch.setattr(accounts, "get_admin_email", lambda: "")
    monkeypatch.setattr(free_accounts, "FREE_ACCOUNTS_FILE", tmp_path / "free_accounts.json")
    monkeypatch.setattr(free_register, "get_cloudmail_free_domain", lambda: "@free.example.com")


def test_create_free_account_success(tmp_path, monkeypatch):
    _patch_state(tmp_path, monkeypatch)

    mail_client = MagicMock()
    mail_client.create_temp_email.return_value = (777, "abc@free.example.com")
    mail_client.delete_account.return_value = True

    monkeypatch.setattr(free_register, "_register_direct_once", lambda *a, **k: True)
    monkeypatch.setattr(
        free_register,
        "login_codex_via_browser",
        lambda email, password, mail_client=None, **kwargs: {
            "access_token": "at",
            "refresh_token": "rt",
            "id_token": "it",
            "account_id": "aid",
            "email": email,
            "plan_type": "free",
        },
    )
    monkeypatch.setattr(
        free_register,
        "save_auth_file",
        lambda bundle: tmp_path / f"codex-{bundle['email']}-free-x.json",
    )
    monkeypatch.setattr(free_register, "upload_to_cpa", lambda path: True)

    result = free_register.create_one_free_account(mail_client)

    assert result["status"] == "ok"
    assert result["email"] == "abc@free.example.com"
    assert mail_client.delete_account.call_count == 0
    rows = free_accounts.load_free_accounts()
    assert len(rows) == 1
    assert rows[0]["email"] == "abc@free.example.com"
    assert rows[0]["plan_type"] == "free"


def test_create_free_account_uses_runtime_proxy_for_free_browser_flows(tmp_path, monkeypatch):
    _patch_state(tmp_path, monkeypatch)

    mail_client = MagicMock()
    mail_client.create_temp_email.return_value = (777, "abc@free.example.com")

    calls = {}

    def fake_register(*args, **kwargs):
        calls["register_free_proxy"] = kwargs.get("use_free_proxy")
        return True

    def fake_login(*args, **kwargs):
        calls["codex_free_proxy"] = kwargs.get("use_free_proxy")
        return {
            "access_token": "at",
            "refresh_token": "rt",
            "id_token": "it",
            "account_id": "aid",
            "email": args[0],
            "plan_type": "free",
        }

    monkeypatch.setattr(free_register, "_register_direct_once", fake_register)
    monkeypatch.setattr(free_register, "login_codex_via_browser", fake_login)
    monkeypatch.setattr(free_register, "save_auth_file", lambda bundle: tmp_path / "auth.json")
    monkeypatch.setattr(free_register, "upload_to_cpa", lambda path: True)

    result = free_register.create_one_free_account(mail_client)

    assert result["status"] == "ok"
    assert calls == {"register_free_proxy": True, "codex_free_proxy": True}


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
    _patch_state(tmp_path, monkeypatch)

    mail_client = MagicMock()
    mail_client.create_temp_email.return_value = (777, "abc@free.example.com")

    monkeypatch.setattr(free_register, "_register_direct_once", lambda *a, **k: True)
    monkeypatch.setattr(
        free_register,
        "login_codex_via_browser",
        lambda *a, **k: {
            "access_token": "at",
            "refresh_token": "rt",
            "id_token": "it",
            "account_id": "aid",
            "email": "abc@free.example.com",
            "plan_type": "free",
        },
    )
    monkeypatch.setattr(free_register, "save_auth_file", lambda bundle: tmp_path / "codex-x.json")

    def boom(path):
        raise RuntimeError("CPA down")

    monkeypatch.setattr(free_register, "upload_to_cpa", boom)

    result = free_register.create_one_free_account(mail_client)

    assert result["status"] == "ok"
    assert len(free_accounts.load_free_accounts()) == 1


def test_batch_creation_aggregates_results(tmp_path, monkeypatch):
    _patch_state(tmp_path, monkeypatch)

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
        lambda email, password, mail_client=None, **kwargs: {
            "access_token": "at",
            "refresh_token": "rt",
            "id_token": "it",
            "account_id": "aid",
            "email": email,
            "plan_type": "free",
        },
    )
    monkeypatch.setattr(free_register, "save_auth_file", lambda bundle: tmp_path / f"codex-{bundle['email']}.json")
    monkeypatch.setattr(free_register, "upload_to_cpa", lambda path: True)

    result = free_register.create_free_accounts_batch(3)

    assert result["count"] == 3
    assert result["succeeded"] == ["a@free.example.com", "c@free.example.com"]
    assert [f["email"] for f in result["failed"]] == ["b@free.example.com"]
    assert result["failed"][0]["reason"] == "register_failed_3x"


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
    _patch_state(tmp_path, monkeypatch)

    free_accounts.save_free_accounts(
        [
            {
                "email": "a@free.example.com",
                "password": "pw",
                "cloudmail_account_id": 99,
                "auth_file": str(tmp_path / "missing.json"),
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
        lambda email, password, mail_client=None, **kwargs: {
            "access_token": "at",
            "refresh_token": "rt",
            "id_token": "it",
            "account_id": "aid",
            "email": email,
            "plan_type": "free",
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
    assert row["auth_file"] == str(tmp_path / "old.json")


def test_refresh_codex_404_when_missing(tmp_path, monkeypatch):
    _patch_state(tmp_path, monkeypatch)
    result = free_register.refresh_codex("missing@x.com")
    assert result["status"] == "not_found"

"""验证 sync_to_cpa 正确合并 Team active + 全部 Free auth 文件。"""

from unittest.mock import patch

from autoteam import accounts, cpa_sync, free_accounts


def test_sync_to_cpa_uploads_team_active_and_all_free(tmp_path, monkeypatch):
    auth_dir = tmp_path / "auths"
    auth_dir.mkdir()

    team_auth = auth_dir / "codex-team@x.com-team-aaa.json"
    team_auth.write_text("{}")
    team_exhausted_auth = auth_dir / "codex-exh@x.com-team-bbb.json"
    team_exhausted_auth.write_text("{}")
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
    deletions = []

    with (
        patch.object(cpa_sync, "list_cpa_files", return_value=[]),
        patch.object(cpa_sync, "upload_to_cpa", side_effect=lambda path: uploads.append(str(path)) or True),
        patch.object(cpa_sync, "delete_from_cpa", side_effect=lambda name: deletions.append(name) or True),
    ):
        cpa_sync.sync_to_cpa()

    uploaded_names = sorted(path.rsplit("/", 1)[-1] for path in uploads)
    assert uploaded_names == [
        "codex-free@y.com-free-ccc.json",
        "codex-team@x.com-team-aaa.json",
    ]
    assert deletions == []


def test_sync_to_cpa_does_not_delete_free_auth_present_in_cpa(tmp_path, monkeypatch):
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

    with (
        patch.object(cpa_sync, "list_cpa_files", return_value=cpa_listing),
        patch.object(cpa_sync, "upload_to_cpa", return_value=True),
        patch.object(cpa_sync, "delete_from_cpa", side_effect=lambda name: deletions.append(name) or True),
    ):
        cpa_sync.sync_to_cpa()

    assert deletions == []

"""GET /api/free/accounts 与未配置降级行为。"""

from fastapi.testclient import TestClient

from autoteam import accounts, free_accounts
from autoteam import api as api_module


def _patch_state(tmp_path, monkeypatch):
    monkeypatch.setattr(accounts, "ACCOUNTS_FILE", tmp_path / "accounts.json")
    monkeypatch.setattr(accounts, "get_admin_email", lambda: "")
    monkeypatch.setattr(free_accounts, "FREE_ACCOUNTS_FILE", tmp_path / "free_accounts.json")
    monkeypatch.setattr(api_module, "API_KEY", "")


def test_get_free_accounts_empty(tmp_path, monkeypatch):
    _patch_state(tmp_path, monkeypatch)
    monkeypatch.setattr(api_module, "get_cloudmail_free_domain", lambda: "@free.example.com")

    client = TestClient(api_module.app)
    response = client.get("/api/free/accounts")
    assert response.status_code == 200
    assert response.json() == {"enabled": True, "accounts": []}


def test_get_free_accounts_returns_sanitized(tmp_path, monkeypatch):
    _patch_state(tmp_path, monkeypatch)
    monkeypatch.setattr(api_module, "get_cloudmail_free_domain", lambda: "@free.example.com")

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
    response = client.get("/api/free/accounts")
    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is True
    assert len(body["accounts"]) == 1
    item = body["accounts"][0]
    assert item["email"] == "a@free.example.com"
    assert item["plan_type"] == "free"
    assert item["auth_file_exists"] is True
    assert "password" not in item


def test_get_free_accounts_missing_auth_file(tmp_path, monkeypatch):
    _patch_state(tmp_path, monkeypatch)
    monkeypatch.setattr(api_module, "get_cloudmail_free_domain", lambda: "@free.example.com")

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
    response = client.get("/api/free/accounts")
    assert response.json()["accounts"][0]["auth_file_exists"] is False


def test_disabled_when_domain_not_configured(tmp_path, monkeypatch):
    _patch_state(tmp_path, monkeypatch)
    monkeypatch.setattr(api_module, "get_cloudmail_free_domain", lambda: "")

    client = TestClient(api_module.app)

    response = client.get("/api/free/accounts")
    assert response.status_code == 200
    assert response.json() == {"enabled": False, "reason": "CLOUDMAIL_FREE_DOMAIN not set", "accounts": []}

    response = client.post("/api/free/accounts", json={"count": 1})
    assert response.status_code == 503

    response = client.delete("/api/free/accounts/a@free.example.com")
    assert response.status_code == 503

    response = client.post("/api/free/accounts/a@free.example.com/refresh")
    assert response.status_code == 503


def test_post_count_validation(tmp_path, monkeypatch):
    _patch_state(tmp_path, monkeypatch)
    monkeypatch.setattr(api_module, "get_cloudmail_free_domain", lambda: "@free.example.com")

    client = TestClient(api_module.app)
    response = client.post("/api/free/accounts", json={"count": 0})
    assert response.status_code == 400

    response = client.post("/api/free/accounts", json={"count": 51})
    assert response.status_code == 400

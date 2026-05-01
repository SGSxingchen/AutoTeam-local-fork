import json

from fastapi.testclient import TestClient

from autoteam import api as api_module
from autoteam import config


def _patch_runtime_config(tmp_path, monkeypatch):
    from autoteam import runtime_config

    monkeypatch.setattr(api_module, "API_KEY", "")
    monkeypatch.setattr(runtime_config, "RUNTIME_CONFIG_FILE", tmp_path / "runtime_config.json")
    monkeypatch.setattr(config, "CLOUDMAIL_FREE_DOMAIN", "@env.example.com")
    monkeypatch.setattr(config, "PLAYWRIGHT_PROXY_URL", "")
    monkeypatch.setattr(config, "PLAYWRIGHT_PROXY_BYPASS", "")
    return runtime_config


def test_get_runtime_config_returns_legacy_runtime_values_without_overriding_env(tmp_path, monkeypatch):
    runtime_config = _patch_runtime_config(tmp_path, monkeypatch)
    runtime_config.RUNTIME_CONFIG_FILE.write_text(
        json.dumps(
            {
                "PLAYWRIGHT_PROXY_URL": "http://user:secret@proxy.example.com:8080",
                "PLAYWRIGHT_PROXY_BYPASS": "localhost,127.0.0.1",
            }
        ),
        encoding="utf-8",
    )

    response = TestClient(api_module.app).get("/api/config/runtime")

    assert response.status_code == 200
    body = response.json()
    assert body["effective"]["CLOUDMAIL_FREE_DOMAIN"] == "@env.example.com"
    assert body["effective"]["PLAYWRIGHT_PROXY_URL"] == ""
    assert body["runtime"]["PLAYWRIGHT_PROXY_URL"] == "http://***:***@proxy.example.com:8080"
    assert body["sources"]["CLOUDMAIL_FREE_DOMAIN"] == "env"
    assert body["sources"]["PLAYWRIGHT_PROXY_URL"] == "runtime"


def test_put_runtime_config_writes_only_submitted_keys(tmp_path, monkeypatch):
    runtime_config = _patch_runtime_config(tmp_path, monkeypatch)
    runtime_config.RUNTIME_CONFIG_FILE.write_text(
        json.dumps({"CLOUDMAIL_FREE_DOMAIN": "@old.example.com"}), encoding="utf-8"
    )

    response = TestClient(api_module.app).put(
        "/api/config/runtime",
        json={
            "CLOUDMAIL_FREE_DOMAIN": "new.example.com",
            "PLAYWRIGHT_PROXY_URL": "http://user:secret@proxy.example.com:8080",
        },
    )

    assert response.status_code == 200
    assert response.json()["effective"]["CLOUDMAIL_FREE_DOMAIN"] == "@env.example.com"
    assert response.json()["effective"]["PLAYWRIGHT_PROXY_URL"] == ""
    assert response.json()["runtime"]["CLOUDMAIL_FREE_DOMAIN"] == "@new.example.com"
    assert response.json()["runtime"]["PLAYWRIGHT_PROXY_URL"] == "http://***:***@proxy.example.com:8080"
    assert json.loads(runtime_config.RUNTIME_CONFIG_FILE.read_text(encoding="utf-8")) == {
        "CLOUDMAIL_FREE_DOMAIN": "@new.example.com",
        "PLAYWRIGHT_PROXY_URL": "http://user:secret@proxy.example.com:8080",
    }

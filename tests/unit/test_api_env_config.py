from fastapi.testclient import TestClient

from autoteam import api, env_config


def _patch_env_files(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "API_KEY", "")
    monkeypatch.setattr(env_config, "ENV_FILE", tmp_path / ".env")
    monkeypatch.setattr(env_config, "RUNTIME_CONFIG_FILE", tmp_path / "runtime_config.json")


def test_get_env_config_endpoint_returns_schema_and_masked_values(tmp_path, monkeypatch):
    _patch_env_files(tmp_path, monkeypatch)
    env_config.ENV_FILE.write_text("API_KEY=secret\nCPA_URL=http://cpa.example.com\n", encoding="utf-8")

    response = TestClient(api.app).get("/api/config/env")

    assert response.status_code == 200
    body = response.json()
    fields = {field["key"]: field for field in body["fields"]}
    assert body["path"].endswith(".env")
    assert fields["API_KEY"]["value"] == ""
    assert fields["API_KEY"]["has_value"] is True
    assert fields["CPA_URL"]["value"] == "http://cpa.example.com"


def test_put_env_config_endpoint_saves_values_and_exposes_restart_required(tmp_path, monkeypatch):
    _patch_env_files(tmp_path, monkeypatch)
    env_config.ENV_FILE.write_text("CPA_URL=http://old.example.com\n", encoding="utf-8")
    monkeypatch.setattr(env_config, "reload_config_modules", lambda: None)

    response = TestClient(api.app).put(
        "/api/config/env",
        json={"values": {"CPA_URL": "http://new.example.com", "AUTO_CHECK_INTERVAL": "180"}},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["updated_keys"] == ["CPA_URL", "AUTO_CHECK_INTERVAL"]
    assert body["restart_required"] is True
    assert "CPA_URL=http://new.example.com" in env_config.ENV_FILE.read_text(encoding="utf-8")


def test_put_env_config_endpoint_updates_auto_check_runtime_state(tmp_path, monkeypatch):
    _patch_env_files(tmp_path, monkeypatch)
    env_config.ENV_FILE.write_text("AUTO_CHECK_INTERVAL=300\n", encoding="utf-8")
    monkeypatch.setattr(env_config, "reload_config_modules", lambda: None)
    monkeypatch.setattr(api, "_auto_check_config", {"interval": 300, "threshold": 10, "min_low": 2})

    class RestartFlag:
        called = False

        def set(self):
            self.called = True

    restart_flag = RestartFlag()
    monkeypatch.setattr(api, "_auto_check_restart", restart_flag)

    response = TestClient(api.app).put(
        "/api/config/env",
        json={
            "values": {
                "AUTO_CHECK_INTERVAL": "180",
                "AUTO_CHECK_THRESHOLD": "15",
                "AUTO_CHECK_MIN_LOW": "3",
            }
        },
    )

    assert response.status_code == 200
    assert response.json()["restart_required"] is False
    assert api._auto_check_config == {"interval": 180, "threshold": 15, "min_low": 3}
    assert restart_flag.called is True


def test_system_restart_endpoint_schedules_restart(monkeypatch):
    monkeypatch.setattr(api, "API_KEY", "")
    monkeypatch.setattr(api, "_schedule_restart", lambda: {"mode": "process-exit", "scheduled": True})

    response = TestClient(api.app).post("/api/system/restart")

    assert response.status_code == 202
    assert response.json() == {"mode": "process-exit", "scheduled": True}

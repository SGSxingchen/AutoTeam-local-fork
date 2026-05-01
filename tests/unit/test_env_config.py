import json

from autoteam import env_config


def _patch_env_files(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    runtime_file = tmp_path / "runtime_config.json"
    monkeypatch.setattr(env_config, "ENV_FILE", env_file)
    monkeypatch.setattr(env_config, "RUNTIME_CONFIG_FILE", runtime_file)
    return env_file, runtime_file


def test_list_env_config_masks_sensitive_values_and_proxy_credentials(tmp_path, monkeypatch):
    env_file, _runtime_file = _patch_env_files(tmp_path, monkeypatch)
    env_file.write_text(
        "\n".join(
            [
                "API_KEY=secret-api-key",
                "CPA_KEY=secret-cpa-key",
                "PLAYWRIGHT_PROXY_URL=http://user:pass@proxy.example.com:8080",
                "FREE_PLAYWRIGHT_PROXY_URL=socks5://free-user:free-pass@free-proxy.example.com:1080",
                "AUTO_CHECK_INTERVAL=120",
            ]
        ),
        encoding="utf-8",
    )

    config = env_config.get_env_config()
    fields = {field["key"]: field for field in config["fields"]}

    assert fields["API_KEY"]["value"] == ""
    assert fields["API_KEY"]["has_value"] is True
    assert fields["API_KEY"]["sensitive"] is True
    assert fields["CPA_KEY"]["value"] == ""
    assert fields["CPA_KEY"]["has_value"] is True
    assert fields["PLAYWRIGHT_PROXY_URL"]["value"] == "http://***:***@proxy.example.com:8080"
    assert fields["PLAYWRIGHT_PROXY_URL"]["masked"] is True
    assert fields["FREE_PLAYWRIGHT_PROXY_URL"]["value"] == "socks5://***:***@free-proxy.example.com:1080"
    assert fields["AUTO_CHECK_INTERVAL"]["value"] == "120"


def test_save_env_config_writes_values_and_marks_restart_required(tmp_path, monkeypatch):
    env_file, _runtime_file = _patch_env_files(tmp_path, monkeypatch)
    env_file.write_text("CPA_URL=http://old.example.com\nAPI_KEY=old-key\n", encoding="utf-8")

    result = env_config.save_env_values(
        {
            "CPA_URL": "http://new.example.com",
            "API_KEY": "",
            "AUTO_CHECK_INTERVAL": "180",
        }
    )

    content = env_file.read_text(encoding="utf-8")
    assert "CPA_URL=http://new.example.com" in content
    assert "API_KEY=" in content
    assert "AUTO_CHECK_INTERVAL=180" in content
    assert result["updated_keys"] == ["CPA_URL", "API_KEY", "AUTO_CHECK_INTERVAL"]
    assert result["restart_required"] is True


def test_save_env_config_marks_hot_auto_check_values_without_restart(tmp_path, monkeypatch):
    env_file, _runtime_file = _patch_env_files(tmp_path, monkeypatch)
    env_file.write_text("AUTO_CHECK_INTERVAL=300\n", encoding="utf-8")

    result = env_config.save_env_values(
        {
            "AUTO_CHECK_INTERVAL": "180",
            "AUTO_CHECK_THRESHOLD": "15",
            "AUTO_CHECK_MIN_LOW": "3",
        }
    )

    assert result["updated_keys"] == ["AUTO_CHECK_INTERVAL", "AUTO_CHECK_THRESHOLD", "AUTO_CHECK_MIN_LOW"]
    assert result["restart_required"] is False


def test_save_env_config_marks_api_and_restart_service_without_restart(tmp_path, monkeypatch):
    env_file, _runtime_file = _patch_env_files(tmp_path, monkeypatch)
    env_file.write_text("API_KEY=old\n", encoding="utf-8")

    result = env_config.save_env_values(
        {
            "API_KEY": "new",
            "AUTOTEAM_SYSTEMD_SERVICE": "autoteam.service",
        }
    )

    assert result["updated_keys"] == ["API_KEY", "AUTOTEAM_SYSTEMD_SERVICE"]
    assert result["restart_required"] is False


def test_mail_provider_is_editable_without_restart(tmp_path, monkeypatch):
    env_file, _runtime_file = _patch_env_files(tmp_path, monkeypatch)
    env_file.write_text("", encoding="utf-8")

    config = env_config.get_env_config()
    fields = {field["key"]: field for field in config["fields"]}

    assert fields["MAIL_PROVIDER"]["value"] == "cloudmail"
    assert fields["MAIL_PROVIDER"]["group"] == "Free"
    assert fields["MAIL_PROVIDER"]["restart_required"] is False

    result = env_config.save_env_values({"MAIL_PROVIDER": "Outlook"})

    assert "MAIL_PROVIDER=outlook" in env_file.read_text(encoding="utf-8")
    assert result["updated_keys"] == ["MAIL_PROVIDER"]
    assert result["restart_required"] is False


def test_save_env_config_rejects_unknown_keys(tmp_path, monkeypatch):
    _patch_env_files(tmp_path, monkeypatch)

    try:
        env_config.save_env_values({"UNKNOWN_KEY": "value"})
    except KeyError as exc:
        assert "UNKNOWN_KEY" in str(exc)
    else:
        raise AssertionError("UNKNOWN_KEY should have raised KeyError")


def test_migrate_runtime_config_moves_free_values_into_env_without_overwriting(tmp_path, monkeypatch):
    env_file, runtime_file = _patch_env_files(tmp_path, monkeypatch)
    env_file.write_text(
        "CLOUDMAIL_FREE_DOMAIN=@already.example.com\nFREE_PLAYWRIGHT_PROXY_URL=http://existing-proxy:8080\n",
        encoding="utf-8",
    )
    runtime_file.write_text(
        json.dumps(
            {
                "CLOUDMAIL_FREE_DOMAIN": "@runtime.example.com",
                "PLAYWRIGHT_PROXY_URL": "http://runtime-proxy.example.com:8080",
                "PLAYWRIGHT_PROXY_BYPASS": "localhost,127.0.0.1",
                "MAIL_PROVIDER": "outlook",
            }
        ),
        encoding="utf-8",
    )

    result = env_config.migrate_runtime_config_to_env()

    content = env_file.read_text(encoding="utf-8")
    assert "CLOUDMAIL_FREE_DOMAIN=@already.example.com" in content
    assert "FREE_PLAYWRIGHT_PROXY_URL=http://existing-proxy:8080" in content
    assert "FREE_PLAYWRIGHT_PROXY_BYPASS=localhost,127.0.0.1" in content
    assert "MAIL_PROVIDER=outlook" in content
    assert result == {
        "migrated_keys": ["FREE_PLAYWRIGHT_PROXY_BYPASS", "MAIL_PROVIDER"],
        "skipped_keys": ["CLOUDMAIL_FREE_DOMAIN", "FREE_PLAYWRIGHT_PROXY_URL"],
    }

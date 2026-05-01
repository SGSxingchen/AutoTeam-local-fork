import json
import logging

from autoteam import config


def test_free_domain_reads_env_config(monkeypatch):
    monkeypatch.setattr(config, "CLOUDMAIL_FREE_DOMAIN", "@free.example.com")

    assert config.get_cloudmail_free_domain() == "@free.example.com"


def test_runtime_proxy_does_not_affect_default_team_playwright_options(tmp_path, monkeypatch):
    from autoteam import runtime_config

    runtime_file = tmp_path / "runtime_config.json"
    runtime_file.write_text(
        json.dumps({"PLAYWRIGHT_PROXY_URL": "http://runtime-proxy.example.com:8080"}), encoding="utf-8"
    )

    monkeypatch.setattr(runtime_config, "RUNTIME_CONFIG_FILE", runtime_file)
    monkeypatch.setattr(config, "PLAYWRIGHT_PROXY_URL", "")
    monkeypatch.setattr(config, "PLAYWRIGHT_PROXY_SERVER", "")
    monkeypatch.setattr(config, "PLAYWRIGHT_PROXY_BYPASS", "")

    options = config.get_playwright_launch_options()

    assert "proxy" not in options


def test_free_playwright_does_not_fall_back_to_team_proxy(monkeypatch):
    monkeypatch.setattr(config, "PLAYWRIGHT_PROXY_URL", "http://env-proxy.example.com:8080")
    monkeypatch.setattr(config, "PLAYWRIGHT_PROXY_BYPASS", "")

    monkeypatch.setattr(config, "FREE_PLAYWRIGHT_PROXY_URL", "")
    monkeypatch.setattr(config, "FREE_PLAYWRIGHT_PROXY_BYPASS", "")

    options = config.get_playwright_launch_options(use_free_proxy=True)

    assert "proxy" not in options


def test_free_playwright_launch_options_reads_free_env(monkeypatch):
    monkeypatch.setattr(config, "PLAYWRIGHT_PROXY_URL", "")
    monkeypatch.setattr(config, "PLAYWRIGHT_PROXY_SERVER", "")
    monkeypatch.setattr(config, "PLAYWRIGHT_PROXY_BYPASS", "")
    monkeypatch.setattr(config, "FREE_PLAYWRIGHT_PROXY_URL", "http://user:secret@proxy-one.example.com:8080")
    monkeypatch.setattr(config, "FREE_PLAYWRIGHT_PROXY_BYPASS", "localhost,127.0.0.1")

    first = config.get_playwright_launch_options(use_free_proxy=True)
    assert first["proxy"] == {
        "server": "http://proxy-one.example.com:8080",
        "username": "user",
        "password": "secret",
        "bypass": "localhost,127.0.0.1",
    }

    monkeypatch.setattr(config, "FREE_PLAYWRIGHT_PROXY_URL", "socks5://proxy-two.example.com:1080")
    monkeypatch.setattr(config, "FREE_PLAYWRIGHT_PROXY_BYPASS", "")

    second = config.get_playwright_launch_options(use_free_proxy=True)
    assert second["proxy"] == {"server": "socks5://proxy-two.example.com:1080"}


def test_runtime_config_write_is_atomic_and_preserves_existing_keys(tmp_path, monkeypatch):
    from autoteam import runtime_config

    runtime_file = tmp_path / "runtime_config.json"
    runtime_file.write_text(json.dumps({"CLOUDMAIL_FREE_DOMAIN": "@old.example.com"}), encoding="utf-8")

    monkeypatch.setattr(runtime_config, "RUNTIME_CONFIG_FILE", runtime_file)

    saved = runtime_config.write_runtime_config({"PLAYWRIGHT_PROXY_BYPASS": "localhost,127.0.0.1"})

    assert saved == {
        "CLOUDMAIL_FREE_DOMAIN": "@old.example.com",
        "PLAYWRIGHT_PROXY_BYPASS": "localhost,127.0.0.1",
    }
    assert json.loads(runtime_file.read_text(encoding="utf-8")) == saved


def test_free_playwright_launch_options_logs_masked_proxy(monkeypatch, caplog):
    monkeypatch.setattr(config, "PLAYWRIGHT_PROXY_URL", "")
    monkeypatch.setattr(config, "PLAYWRIGHT_PROXY_SERVER", "")
    monkeypatch.setattr(config, "PLAYWRIGHT_PROXY_BYPASS", "")
    monkeypatch.setattr(config, "FREE_PLAYWRIGHT_PROXY_URL", "http://user:secret@proxy.example.com:8080")
    monkeypatch.setattr(config, "FREE_PLAYWRIGHT_PROXY_BYPASS", "localhost,127.0.0.1")

    with caplog.at_level(logging.INFO, logger="autoteam.config"):
        config.get_playwright_launch_options(use_free_proxy=True)

    assert (
        "[Playwright] 使用代理: server=http://proxy.example.com:8080 auth=enabled bypass=localhost,127.0.0.1"
        in caplog.text
    )
    assert "secret" not in caplog.text
    assert "user:secret" not in caplog.text


def test_free_playwright_launch_options_logs_direct_connection(monkeypatch, caplog):
    monkeypatch.setattr(config, "PLAYWRIGHT_PROXY_URL", "")
    monkeypatch.setattr(config, "PLAYWRIGHT_PROXY_SERVER", "")
    monkeypatch.setattr(config, "PLAYWRIGHT_PROXY_BYPASS", "")
    monkeypatch.setattr(config, "FREE_PLAYWRIGHT_PROXY_URL", "")
    monkeypatch.setattr(config, "FREE_PLAYWRIGHT_PROXY_BYPASS", "")

    with caplog.at_level(logging.INFO, logger="autoteam.config"):
        config.get_playwright_launch_options(use_free_proxy=True)

    assert "[Playwright] 未使用代理" in caplog.text

import pytest

from autoteam import manager


def test_cmd_add_free_invalid_domain_exits(monkeypatch):
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

    def fake_batch(count):
        calls["batch"] = count
        return {"count": count, "succeeded": ["a@x.com"], "failed": []}

    def fake_sync():
        calls["synced"] = True

    monkeypatch.setattr("autoteam.free_register.create_free_accounts_batch", fake_batch)
    monkeypatch.setattr("autoteam.cpa_sync.sync_to_cpa", fake_sync)

    manager.cmd_add_free(2)

    assert calls == {"batch": 2, "synced": True}

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

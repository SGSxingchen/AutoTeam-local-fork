from autoteam import manager


def test_submit_direct_password_uses_create_account_label(monkeypatch):
    captured = {}

    class PasswordInput:
        def fill(self, value):
            captured["password"] = value

    def fake_click(page, field, labels):
        captured["page"] = page
        captured["field"] = field
        captured["labels"] = labels
        return True

    page = object()
    password_input = PasswordInput()

    monkeypatch.setattr(manager.time, "sleep", lambda *_: None)
    monkeypatch.setattr(manager, "_click_primary_auth_button", fake_click)

    assert manager._submit_direct_password(page, password_input, "Tmp_password1!") is True

    assert captured["password"] == "Tmp_password1!"
    assert captured["page"] is page
    assert captured["field"] is password_input
    assert "Create account" in captured["labels"]

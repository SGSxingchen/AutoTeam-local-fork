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


def test_direct_register_page_error_detects_openai_create_failure():
    class Body:
        def inner_text(self, timeout=None):
            return "Create a password\nFailed to create account. Please try again"

    class Page:
        def locator(self, selector):
            assert selector == "body"
            return Body()

    reason, excerpt = manager._direct_register_page_error(Page())

    assert reason == "failed_to_create_account"
    assert "Failed to create account" in excerpt

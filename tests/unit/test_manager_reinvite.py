import sys
import types

from autoteam import accounts, manager


class _FakeLocator:
    def __init__(self, visible=False):
        self._visible = visible
        self.value = None
        self.clicked = False

    @property
    def first(self):
        return self

    def is_visible(self, timeout=None):
        return self._visible

    def fill(self, value):
        self.value = value

    def click(self):
        self.clicked = True


class _FakePage:
    def __init__(self):
        self.url = ""
        self.email_input = _FakeLocator(visible=True)
        self.password_input = _FakeLocator(visible=False)
        self.code_input = _FakeLocator(visible=False)
        self.login_button = _FakeLocator(visible=False)

    def goto(self, url, **kwargs):
        self.url = url

    def content(self):
        return "<html></html>"

    def locator(self, selector):
        if selector == 'button:has-text("登录"), button:has-text("Log in")':
            return self.login_button
        if selector == 'input[name="email"], input[type="email"]':
            return self.email_input
        if selector == 'input[type="password"]':
            return self.password_input
        if selector == 'input[name="code"], input[placeholder*="验证码"]':
            return self.code_input
        return _FakeLocator(visible=False)


class _FakeContext:
    def __init__(self, page):
        self._page = page

    def new_page(self):
        return self._page


class _FakeBrowser:
    def __init__(self, page):
        self._page = page
        self.closed = False

    def new_context(self, **kwargs):
        return _FakeContext(self._page)

    def close(self):
        self.closed = True


class _FakePlaywright:
    def __init__(self, page):
        self.chromium = types.SimpleNamespace(launch=lambda **kwargs: _FakeBrowser(page))


class _FakeSyncPlaywright:
    def __init__(self, page):
        self._playwright = _FakePlaywright(page)

    def __enter__(self):
        return self._playwright

    def __exit__(self, exc_type, exc, tb):
        return False


def test_reinvite_account_stops_when_primary_submit_redirects_to_google(monkeypatch):
    page = _FakePage()
    updates = []
    click_labels = []

    fake_invite_module = types.ModuleType("autoteam.invite")
    fake_invite_module.screenshot = lambda page_obj, name: None
    monkeypatch.setitem(sys.modules, "autoteam.invite", fake_invite_module)

    monkeypatch.setattr("playwright.sync_api.sync_playwright", lambda: _FakeSyncPlaywright(page))
    monkeypatch.setattr(manager.time, "sleep", lambda *_args, **_kwargs: None)

    def fake_click_primary(page_obj, field, labels):
        click_labels.append(tuple(labels))
        page_obj.url = "https://accounts.google.com/v3/signin/identifier"
        return True

    monkeypatch.setattr(manager, "_click_primary_auth_button", fake_click_primary)
    monkeypatch.setattr(
        manager, "_is_email_in_team", lambda email: (_ for _ in ()).throw(AssertionError("should not check team"))
    )
    monkeypatch.setattr(
        manager,
        "update_account",
        lambda email, **kwargs: updates.append((email, kwargs)),
    )
    monkeypatch.setattr(
        manager,
        "login_codex_via_browser",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("should not refresh codex")),
    )

    result = manager.reinvite_account(
        types.SimpleNamespace(browser=None),
        None,
        {"email": "tmp-user@example.com", "password": "secret"},
    )

    assert result is False
    assert page.email_input.value == "tmp-user@example.com"
    assert click_labels == [("Continue", "继续")]
    assert updates == [("tmp-user@example.com", {"status": accounts.STATUS_STANDBY})]

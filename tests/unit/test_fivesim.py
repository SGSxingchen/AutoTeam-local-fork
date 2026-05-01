import pytest

from autoteam import fivesim


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(fivesim.time, "sleep", lambda _seconds: None)


class FakeLocator:
    def __init__(self, page, selector):
        self.page = page
        self.selector = selector

    @property
    def first(self):
        return self

    def is_visible(self, timeout=0):
        return self.page.is_visible(self.selector)

    def inner_text(self, timeout=0):
        return self.page.body

    def fill(self, value):
        self.page.fills.append((self.selector, value))

    def click(self):
        self.page.clicks.append(self.selector)
        self.page.handle_click(self.selector)

    def all(self):
        return []


class FakePhonePage:
    def __init__(self, *, body="", submit_success=True):
        self.body = body
        self.submit_success = submit_success
        self.state = "phone"
        self.fills = []
        self.clicks = []

    def locator(self, selector):
        return FakeLocator(self, selector)

    def is_visible(self, selector):
        if selector == "body":
            return True
        if selector == 'input[autocomplete="tel"]':
            return self.state == "phone"
        if selector == 'button:has-text("Send code")':
            return self.state == "phone"
        if selector == 'input[autocomplete="one-time-code"]':
            return self.state == "sms"
        if selector == 'button:has-text("Continue")':
            return self.state == "sms"
        return False

    def handle_click(self, selector):
        if selector == 'button:has-text("Send code")':
            self.state = "sms"
        elif selector == 'button:has-text("Continue")' and self.submit_success:
            self.state = "done"
            self.body = "Welcome"
        elif selector == 'button:has-text("Continue")':
            self.body = "Invalid code"


class FakeSmsCodeTelPage(FakePhonePage):
    def __init__(self):
        super().__init__(body="Enter the verification code we sent by text message")
        self.state = "sms"

    def is_visible(self, selector):
        if selector == "body":
            return True
        if selector == 'input[type="tel"]':
            return True
        if selector == 'input[autocomplete="one-time-code"]':
            return True
        return False


class FakeNumericPhonePage(FakePhonePage):
    def __init__(self):
        super().__init__(body="Add a phone number")
        self.state = "phone"

    def is_visible(self, selector):
        if selector == "body":
            return True
        if selector == 'input[inputmode="numeric"]':
            return True
        return False


class FakeFiveSimClient:
    is_configured = True
    product = "openai"

    def __init__(self):
        self.finished = []
        self.canceled = []
        self.buy_kwargs = []

    def buy_number(self, **kwargs):
        self.buy_kwargs.append(kwargs)
        return {"id": 123, "phone": "+442012345678"}

    def wait_for_sms(self, order_id):
        assert order_id == 123
        return "654321"

    def finish_order(self, order_id):
        self.finished.append(order_id)

    def cancel_order(self, order_id):
        self.canceled.append(order_id)


def test_is_phone_page_does_not_treat_sms_code_tel_input_as_phone_page():
    page = FakeSmsCodeTelPage()

    assert fivesim.is_phone_page(page) is False


def test_is_phone_page_accepts_numeric_phone_input_with_phone_hint():
    page = FakeNumericPhonePage()

    assert fivesim.is_phone_page(page) is True


def test_fill_phone_number_preserves_international_number():
    page = FakePhonePage(body="Add a phone number")

    assert fivesim.fill_phone_number(page, "+442012345678") is True
    assert page.fills == [('input[autocomplete="tel"]', "+442012345678")]


def test_try_phone_verification_cancels_order_when_page_stays_on_sms_step():
    page = FakePhonePage(body="Add a phone number", submit_success=False)
    client = FakeFiveSimClient()

    assert fivesim.try_phone_verification(page, client) is False
    assert client.finished == []
    assert client.canceled == [123]


def test_try_phone_verification_finishes_order_after_page_accepts_code():
    page = FakePhonePage(body="Add a phone number", submit_success=True)
    client = FakeFiveSimClient()

    assert fivesim.try_phone_verification(page, client) is True
    assert client.finished == [123]
    assert client.canceled == []

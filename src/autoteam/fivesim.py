"""5sim 接码平台 API 客户端 — 自动购买号码、接收短信验证码"""

import logging
import re
import time

import requests

from autoteam.config import FIVESIM_API_KEY, FIVESIM_COUNTRY, FIVESIM_OPERATOR, FIVESIM_PRODUCT

logger = logging.getLogger(__name__)

FIVESIM_BASE_URL = "https://5sim.net/v1"
DEFAULT_TIMEOUT = 120
POLL_INTERVAL = 3


class FiveSimClient:
    def __init__(self, api_key=None, product=None, country=None, operator=None):
        self.api_key = api_key or FIVESIM_API_KEY
        self.product = product or FIVESIM_PRODUCT
        self.country = country or FIVESIM_COUNTRY
        self.operator = operator or FIVESIM_OPERATOR
        self.session = requests.Session()
        self._base_headers = {"Accept": "application/json"}
        if self.api_key:
            self._base_headers["Authorization"] = f"Bearer {self.api_key}"

    @property
    def is_configured(self):
        return bool(self.api_key)

    def _get(self, path, params=None):
        resp = self.session.get(
            f"{FIVESIM_BASE_URL}{path}",
            headers=self._base_headers,
            params=params,
            timeout=30,
        )
        return resp

    def buy_number(self, country=None, operator=None, product=None):
        """购买激活号码，返回 {id, phone, operator, product, price, status, country}。"""
        country = country or self.country or "any"
        operator = operator or self.operator or "any"
        product = product or self.product
        url = f"/user/buy/activation/{country}/{operator}/{product}"
        logger.info("[5sim] 购买号码: country=%s operator=%s product=%s", country, operator, product)

        resp = self._get(url)
        if resp.status_code != 200:
            logger.error("[5sim] 购买失败: HTTP %d %s", resp.status_code, resp.text[:200])
            return None

        data = resp.json()
        if isinstance(data, dict) and data.get("id"):
            logger.info(
                "[5sim] 号码购买成功: id=%s phone=%s price=%.2f country=%s",
                data["id"],
                data.get("phone"),
                float(data.get("price", 0)),
                data.get("country"),
            )
            return data

        logger.warning("[5sim] 购买失败（无可用号码或余额不足）: %s", resp.text[:200])
        return None

    def wait_for_sms(self, order_id, timeout=None):
        """轮询等待短信到达，返回 code 字符串；超时返回 None。"""
        timeout = timeout or DEFAULT_TIMEOUT
        deadline = time.time() + timeout
        logger.info("[5sim] 等待短信到达 orderId=%s (超时 %ds)...", order_id, timeout)

        while time.time() < deadline:
            resp = self._get(f"/user/check/{order_id}")
            if resp.status_code != 200:
                time.sleep(POLL_INTERVAL)
                continue

            data = resp.json()
            sms_list = data.get("sms") or []
            if sms_list:
                sms = sms_list[0]
                code = sms.get("code") or ""
                if not code:
                    text = sms.get("text", "")
                    m = re.search(r"\b(\d{4,8})\b", text)
                    code = m.group(1) if m else ""
                if code:
                    logger.info("[5sim] 收到短信验证码: %s (sender=%s)", code, sms.get("sender"))
                    return code

            status = data.get("status", "")
            if status in ("CANCELED", "TIMEOUT", "BANNED"):
                logger.warning("[5sim] 订单异常: status=%s", status)
                return None

            elapsed = int(time.time() - (deadline - timeout))
            if elapsed % 15 < POLL_INTERVAL:
                logger.debug("[5sim] 等待短信中... (%ds) status=%s", elapsed, status)
            time.sleep(POLL_INTERVAL)

        logger.warning("[5sim] 等待短信超时 orderId=%s", order_id)
        return None

    def finish_order(self, order_id):
        """确认订单完成。"""
        resp = self._get(f"/user/finish/{order_id}")
        if resp.status_code == 200:
            logger.info("[5sim] 订单已确认: %s", order_id)
            return True
        logger.warning("[5sim] 确认订单失败: HTTP %d %s", resp.status_code, resp.text[:100])
        return False

    def cancel_order(self, order_id):
        """取消订单。"""
        resp = self._get(f"/user/cancel/{order_id}")
        if resp.status_code == 200:
            logger.info("[5sim] 订单已取消: %s", order_id)
            return True
        logger.warning("[5sim] 取消订单失败: HTTP %d %s", resp.status_code, resp.text[:100])
        return False


_PHONE_INPUT_SELECTORS = (
    'input[name="phone"]',
    'input[name="phone_number"]',
    'input[name="phoneNumber"]',
    'input[placeholder*="phone" i]',
    'input[placeholder*="Phone" i]',
    'input[placeholder*="手机"]',
    'input[placeholder*="电话"]',
    'input[autocomplete="tel"]',
    'input[autocomplete="tel-national"]',
)
_GENERIC_TEL_SELECTOR = 'input[type="tel"]'

_PHONE_SUBMIT_BUTTONS = (
    'button:has-text("Send code")',
    'button:has-text("send code")',
    'button:has-text("发送")',
    'button:has-text("Send")',
    'button:has-text("Text me")',
    'button:has-text("下一步")',
    'button:has-text("Next")',
    'button:has-text("确认")',
    'button:has-text("Continue")',
    'button:has-text("继续")',
    'button[type="submit"]',
)
_SMS_SUBMIT_BUTTONS = (
    'button:has-text("Verify")',
    'button:has-text("Submit")',
    'button:has-text("Continue")',
    'button:has-text("继续")',
    'button:has-text("确认")',
    'button[type="submit"]',
)
_SMS_CODE_SELECTORS = (
    'input[name="code"]',
    'input[placeholder*="code" i]',
    'input[placeholder*="验证码"]',
    'input[placeholder*="短信"]',
    'input[inputmode="numeric"]',
    'input[autocomplete="one-time-code"]',
)
_SMS_CODE_DETECTION_SELECTORS = (
    'input[name="code"]',
    'input[placeholder*="code" i]',
    'input[placeholder*="验证码"]',
    'input[placeholder*="短信"]',
    'input[autocomplete="one-time-code"]',
)
_PHONE_FALLBACK_INPUT_SELECTORS = (
    _GENERIC_TEL_SELECTOR,
    'input[inputmode="numeric"]',
)

_PHONE_BODY_HINTS = (
    "phone number",
    "phone numbers",
    "手机号",
    "电话号码",
    "短信验证",
    "verify your phone",
    "verify phone",
    "phone verification",
    "add a phone number",
    "we need your phone number",
    "enter your phone",
    "text message",
    "send a code to your phone",
    "send code to your",
)
_SMS_BODY_HINTS = (
    "enter the verification code",
    "enter verification code",
    "verification code we sent",
    "one-time code",
    "sms code",
    "text message code",
    "输入验证码",
    "输入短信验证码",
)
_PHONE_ERROR_HINTS = (
    "invalid code",
    "incorrect code",
    "wrong code",
    "expired code",
    "try again",
    "验证码无效",
    "验证码错误",
    "验证码已过期",
)


def _body_text(page, timeout=1000):
    try:
        return page.locator("body").inner_text(timeout=timeout).lower()
    except Exception:
        return ""


def _has_visible_locator(page, selectors, timeout=300):
    for sel in selectors:
        try:
            if page.locator(sel).first.is_visible(timeout=timeout):
                return True
        except Exception:
            continue
    return False


def _first_visible_locator(page, selectors, timeout=300):
    for sel in selectors:
        try:
            locator = page.locator(sel).first
            if locator.is_visible(timeout=timeout):
                return locator
        except Exception:
            continue
    return None


def _has_phone_hint(body):
    return any(hint in body for hint in _PHONE_BODY_HINTS)


def _looks_like_sms_code_page(page, body):
    if _has_visible_locator(page, _SMS_CODE_DETECTION_SELECTORS, timeout=200):
        return True
    return any(hint in body for hint in _SMS_BODY_HINTS)


def _phone_error_hint(page):
    body = _body_text(page, timeout=800)
    for hint in _PHONE_ERROR_HINTS:
        if hint in body:
            return hint
    return ""


def is_phone_page(page):
    """检测当前页面是否需要填写手机号，而不是短信验证码页。"""
    if not page:
        return False

    body = _body_text(page)
    if _looks_like_sms_code_page(page, body):
        return False

    if _has_visible_locator(page, _PHONE_INPUT_SELECTORS):
        return True

    return bool(_has_phone_hint(body) and _has_visible_locator(page, _PHONE_FALLBACK_INPUT_SELECTORS))


def fill_phone_number(page, phone_number):
    """在页面中填写手机号，保留国际区号。"""
    raw = (phone_number or "").strip()
    if raw.startswith("+"):
        normalized_number = "+" + re.sub(r"\D", "", raw)
    else:
        normalized_number = re.sub(r"\D", "", raw)

    inp = _first_visible_locator(page, _PHONE_INPUT_SELECTORS)
    if not inp and _has_phone_hint(_body_text(page)):
        inp = _first_visible_locator(page, _PHONE_FALLBACK_INPUT_SELECTORS)
    if inp:
        inp.fill(normalized_number)
        logger.info("[Phone] 已填入手机号: %s (原始: %s)", normalized_number, phone_number)
        time.sleep(0.5)
        return True
    return False


def click_send_code_button(page):
    """点击发送验证码按钮。"""
    for sel in _PHONE_SUBMIT_BUTTONS:
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=1000):
                btn.click()
                logger.info("[Phone] 已点击发送验证码按钮: %s", sel)
                time.sleep(3)
                return True
        except Exception:
            continue

    try:
        page.keyboard.press("Enter")
        time.sleep(3)
        return True
    except Exception:
        return False


def fill_sms_code(page, code):
    """在页面中填写短信验证码。"""
    inp = _first_visible_locator(page, _SMS_CODE_SELECTORS)
    if inp:
        inp.fill(code)
        logger.info("[Phone] 已填入短信验证码: %s", code)
        time.sleep(0.5)
        return True

    single_inputs = page.locator('input[maxlength="1"]').all()
    if len(single_inputs) >= 4:
        logger.info("[Phone] 检测到 %d 个单字符输入框", len(single_inputs))
        for i, char in enumerate(code):
            if i < len(single_inputs):
                single_inputs[i].fill(char)
                time.sleep(0.1)
        time.sleep(0.5)
        return True

    return False


def click_sms_submit_button(page):
    """点击短信验证码提交按钮。"""
    for sel in _SMS_SUBMIT_BUTTONS:
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=1000):
                btn.click()
                logger.info("[Phone] 已点击短信验证码提交按钮: %s", sel)
                time.sleep(3)
                return True
        except Exception:
            continue
    return False


def wait_for_phone_verification_result(page, timeout=15):
    """等待页面确认短信验证码结果。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        error_hint = _phone_error_hint(page)
        if error_hint:
            logger.warning("[Phone] 手机验证码被页面拒绝: %s", error_hint)
            return False

        if not _has_visible_locator(page, _SMS_CODE_SELECTORS, timeout=300) and not is_phone_page(page):
            return True

        time.sleep(1)
    logger.warning("[Phone] 提交短信验证码后未确认通过")
    return False


def try_phone_verification(page, fivesim_client, product=None):
    """
    检测并在需要时自动完成手机号验证。
    返回 True 表示验证完成或不需要验证，False 表示验证失败。
    """
    if not fivesim_client or not fivesim_client.is_configured:
        return False

    if not is_phone_page(page):
        return False

    logger.info("[Phone] 检测到手机号验证页面，开始自动接码...")
    product = product or fivesim_client.product

    order = fivesim_client.buy_number(product=product)
    if not order:
        logger.warning("[Phone] 无法购买号码，跳过自动手机验证")
        return False

    order_id = order["id"]
    phone_number = order.get("phone", "")

    if not fill_phone_number(page, phone_number):
        logger.warning("[Phone] 未找到手机号输入框，取消订单")
        fivesim_client.cancel_order(order_id)
        return False

    if not click_send_code_button(page):
        logger.warning("[Phone] 未找到发送按钮，取消订单")
        fivesim_client.cancel_order(order_id)
        return False

    code = fivesim_client.wait_for_sms(order_id)
    if not code:
        logger.warning("[Phone] 未收到短信，取消订单")
        fivesim_client.cancel_order(order_id)
        return False

    if not fill_sms_code(page, code):
        logger.warning("[Phone] 未找到验证码输入框，取消订单")
        fivesim_client.cancel_order(order_id)
        return False

    if not click_sms_submit_button(page):
        logger.warning("[Phone] 未找到短信验证码提交按钮，取消订单")
        fivesim_client.cancel_order(order_id)
        return False

    if not wait_for_phone_verification_result(page):
        logger.warning("[Phone] 手机验证码提交后未通过，取消订单")
        fivesim_client.cancel_order(order_id)
        return False

    fivesim_client.finish_order(order_id)
    logger.info("[Phone] 手机验证完成")
    return True

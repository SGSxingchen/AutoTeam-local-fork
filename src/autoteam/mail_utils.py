"""邮件正文解析的纯函数,CloudMail / Outlook 两端共用。"""

import html as _html_mod
import re

_VERIFICATION_CODE_PATTERNS = (
    r"(?:temporary\s+(?:openai|chatgpt)\s+login\s+code(?:\s+is)?|verification\s+code(?:\s+is)?|login\s+code(?:\s+is)?|code(?:\s+is)?|验证码(?:为|是)?)\D{0,24}(\d{6})",
    r"\b(\d{6})\b",
)


def html_to_visible_text(value):
    """剥 HTML 标签,保留可见文本。"""
    content = str(value or "")
    if not content:
        return ""

    content = re.sub(r"(?is)<(script|style)\b.*?>.*?</\1>", " ", content)
    content = re.sub(r"(?is)<!--.*?-->", " ", content)
    content = re.sub(r"(?i)<br\\s*/?>", "\n", content)
    content = re.sub(r"(?i)</(?:p|div|tr|table|h[1-6]|li|td|section|article)>", "\n", content)
    content = re.sub(r"(?s)<[^>]+>", " ", content)
    content = _html_mod.unescape(content)
    content = re.sub(r"[\t\r\f\v ]+", " ", content)
    content = re.sub(r"\n\s+", "\n", content)
    content = re.sub(r"\n{2,}", "\n", content)
    return content.strip()


def extract_verification_code(email_data):
    """从邮件 dict 中提取 6 位验证码。"""
    sources = []

    plain_text = str(email_data.get("text") or "").strip()
    if plain_text:
        sources.append(plain_text)

    html_text = html_to_visible_text(email_data.get("content"))
    if html_text and html_text not in sources:
        sources.append(html_text)

    for source in sources:
        for pattern in _VERIFICATION_CODE_PATTERNS:
            match = re.search(pattern, source, re.IGNORECASE)
            if match:
                return match.group(1)

    return None


def extract_invite_link(email_data):
    """从 OpenAI 邀请邮件中提取邀请链接。"""
    html = email_data.get("content", "")
    text = email_data.get("text", "")

    links = re.findall(r'href="(https://chatgpt\.com/auth/login\?[^"]*)"', html)
    if links:
        return links[0]

    links = re.findall(r'(https://chatgpt\.com/auth/login\?[^\s<>"\']+)', text)
    if links:
        return links[0]

    link_pattern = r'https?://[^\s<>"\']+(?:invite|accept|join|workspace)[^\s<>"\']*'
    match = re.search(link_pattern, html or text, re.IGNORECASE)
    if match:
        return match.group(0)

    return None

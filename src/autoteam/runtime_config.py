"""运行时配置文件。

`runtime_config.json` 用于覆盖少量需要热切换的 .env 配置。读取函数不做缓存，
确保后续新任务能拿到文件中的最新值。
"""

import json
import logging
import os
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

PROJECT_ROOT = Path(__file__).parent.parent.parent
RUNTIME_CONFIG_FILE = PROJECT_ROOT / "runtime_config.json"
RUNTIME_CONFIG_KEYS = (
    "CLOUDMAIL_FREE_DOMAIN",
    "PLAYWRIGHT_PROXY_URL",
    "PLAYWRIGHT_PROXY_BYPASS",
)

logger = logging.getLogger(__name__)


def _normalize_runtime_value(key: str, value) -> str:
    text = str(value or "").strip()
    if key == "CLOUDMAIL_FREE_DOMAIN" and text and not text.startswith("@"):
        text = f"@{text}"
    return text


def load_runtime_config() -> dict[str, str]:
    """读取 runtime_config.json；文件不存在或格式错误时返回空配置。"""
    if not RUNTIME_CONFIG_FILE.exists():
        return {}

    try:
        raw = json.loads(RUNTIME_CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("[配置] runtime_config.json 读取失败，忽略运行时覆盖: %s", exc)
        return {}

    if not isinstance(raw, dict):
        logger.warning("[配置] runtime_config.json 顶层必须是对象，已忽略")
        return {}

    config: dict[str, str] = {}
    for key in RUNTIME_CONFIG_KEYS:
        if key in raw:
            config[key] = _normalize_runtime_value(key, raw[key])
    return config


def get_runtime_override(key: str) -> str | None:
    """返回运行时覆盖值。None 表示未配置覆盖；空字符串表示显式清空。"""
    if key not in RUNTIME_CONFIG_KEYS:
        raise KeyError(f"unsupported runtime config key: {key}")
    config = load_runtime_config()
    if key not in config:
        return None
    return config[key]


def get_runtime_value(key: str, default: str = "") -> str:
    override = get_runtime_override(key)
    if override is None:
        return default
    return override


def write_runtime_config(updates: dict[str, str]) -> dict[str, str]:
    """原子更新 runtime_config.json，并保留未提交的既有键。"""
    current = load_runtime_config()
    for key, value in updates.items():
        if key not in RUNTIME_CONFIG_KEYS:
            raise KeyError(f"unsupported runtime config key: {key}")
        current[key] = _normalize_runtime_value(key, value)

    RUNTIME_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = RUNTIME_CONFIG_FILE.with_name(f".{RUNTIME_CONFIG_FILE.name}.tmp")
    tmp_path.write_text(
        json.dumps(current, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp_path, RUNTIME_CONFIG_FILE)
    return current


def mask_proxy_url(value: str) -> str:
    """遮蔽代理 URL 中的账号密码，供 API 响应和日志使用。"""
    text = str(value or "").strip()
    if not text or "://" not in text:
        return text

    parsed = urlsplit(text)
    if not parsed.username and not parsed.password:
        return text

    host = parsed.hostname or ""
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    if parsed.port:
        host = f"{host}:{parsed.port}"

    credentials = "***:***" if parsed.password is not None else "***"
    return urlunsplit((parsed.scheme, f"{credentials}@{host}", parsed.path, parsed.query, parsed.fragment))


def sanitize_runtime_config(config: dict[str, str]) -> dict[str, str]:
    sanitized = dict(config)
    if "PLAYWRIGHT_PROXY_URL" in sanitized:
        sanitized["PLAYWRIGHT_PROXY_URL"] = mask_proxy_url(sanitized["PLAYWRIGHT_PROXY_URL"])
    return sanitized

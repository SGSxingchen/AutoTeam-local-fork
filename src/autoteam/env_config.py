"""Web 可编辑的 .env 配置中心。"""

from __future__ import annotations

import importlib
import os
import sys
from dataclasses import dataclass

from autoteam.config import PROJECT_ROOT
from autoteam.runtime_config import mask_proxy_url
from autoteam.textio import parse_env_line, write_text

ENV_FILE = PROJECT_ROOT / ".env"
RUNTIME_CONFIG_FILE = PROJECT_ROOT / "runtime_config.json"


@dataclass(frozen=True)
class EnvField:
    key: str
    label: str
    group: str
    default: str = ""
    optional: bool = True
    sensitive: bool = False
    restart_required: bool = True
    value_type: str = "text"
    mask: str = ""
    description: str = ""


ENV_FIELDS = (
    EnvField("CLOUDMAIL_BASE_URL", "CloudMail API 地址", "CloudMail", optional=False),
    EnvField("CLOUDMAIL_EMAIL", "CloudMail 登录邮箱", "CloudMail", optional=False),
    EnvField("CLOUDMAIL_PASSWORD", "CloudMail 登录密码", "CloudMail", optional=False, sensitive=True),
    EnvField("CLOUDMAIL_DOMAIN", "Team 邮箱域名", "CloudMail", optional=False),
    EnvField("CLOUDMAIL_FREE_DOMAIN", "Free 邮箱域名", "CloudMail"),
    EnvField("CPA_URL", "CPA 地址", "CPA", default="http://127.0.0.1:8317", optional=False),
    EnvField("CPA_KEY", "CPA 管理密钥", "CPA", optional=False, sensitive=True),
    EnvField("API_KEY", "Web API Key", "安全", optional=False, sensitive=True, restart_required=False),
    EnvField("CHATGPT_ACCOUNT_ID", "ChatGPT Workspace ID", "Team"),
    EnvField("EMAIL_POLL_INTERVAL", "邮件轮询间隔（秒）", "轮询", default="3", value_type="number"),
    EnvField("EMAIL_POLL_TIMEOUT", "邮件轮询超时（秒）", "轮询", default="300", value_type="number"),
    EnvField(
        "AUTO_CHECK_INTERVAL", "巡检间隔（秒）", "巡检", default="300", restart_required=False, value_type="number"
    ),
    EnvField(
        "AUTO_CHECK_THRESHOLD", "额度阈值（%）", "巡检", default="10", restart_required=False, value_type="number"
    ),
    EnvField("AUTO_CHECK_MIN_LOW", "触发账号数", "巡检", default="2", restart_required=False, value_type="number"),
    EnvField("MAIL_TIMEOUT", "注册邮件等待超时（秒）", "高级", default="180", value_type="number"),
    EnvField(
        "REUSE_RESET_GRACE_SECONDS",
        "额度恢复复用缓冲（秒）",
        "高级",
        default="300",
        value_type="number",
    ),
    EnvField("PLAYWRIGHT_HEADLESS", "浏览器无头模式", "Playwright", default="0", value_type="bool"),
    EnvField("PLAYWRIGHT_PROXY_URL", "Team/全局代理 URL", "Playwright", mask="proxy_url"),
    EnvField("PLAYWRIGHT_PROXY_SERVER", "Team/全局代理 Server", "Playwright", mask="proxy_url"),
    EnvField("PLAYWRIGHT_PROXY_USERNAME", "Team/全局代理用户名", "Playwright"),
    EnvField("PLAYWRIGHT_PROXY_PASSWORD", "Team/全局代理密码", "Playwright", sensitive=True),
    EnvField("PLAYWRIGHT_PROXY_BYPASS", "Team/全局代理绕过", "Playwright"),
    EnvField("FREE_PLAYWRIGHT_PROXY_URL", "Free 专用代理 URL", "Free", mask="proxy_url"),
    EnvField("FREE_PLAYWRIGHT_PROXY_BYPASS", "Free 专用代理绕过", "Free"),
    EnvField("FIVESIM_API_KEY", "5sim API Key", "5sim", sensitive=True),
    EnvField("FIVESIM_PRODUCT", "5sim 产品", "5sim", default="openai"),
    EnvField("FIVESIM_COUNTRY", "5sim 国家", "5sim", default="any"),
    EnvField("FIVESIM_OPERATOR", "5sim 运营商", "5sim", default="any"),
    EnvField("AUTOTEAM_SYSTEMD_SERVICE", "systemd 服务名", "高级", restart_required=False),
)

ENV_FIELD_BY_KEY = {field.key: field for field in ENV_FIELDS}
RUNTIME_ENV_MIGRATION = {
    "CLOUDMAIL_FREE_DOMAIN": "CLOUDMAIL_FREE_DOMAIN",
    "PLAYWRIGHT_PROXY_URL": "FREE_PLAYWRIGHT_PROXY_URL",
    "PLAYWRIGHT_PROXY_BYPASS": "FREE_PLAYWRIGHT_PROXY_BYPASS",
}


def read_env_file() -> dict[str, str]:
    env: dict[str, str] = {}
    if not ENV_FILE.exists():
        return env
    for line in ENV_FILE.read_text(encoding="utf-8-sig").splitlines():
        parsed = parse_env_line(line)
        if parsed:
            key, value = parsed
            env[key] = value
    return env


def _normalize_env_value(field: EnvField, value) -> str:
    text = "" if value is None else str(value).strip()
    if field.value_type == "bool":
        return "1" if text.lower() in {"1", "true", "yes", "on"} else "0"
    if field.value_type == "number" and text:
        return str(int(text))
    if field.key in {"CLOUDMAIL_DOMAIN", "CLOUDMAIL_FREE_DOMAIN"} and text and not text.startswith("@"):
        return f"@{text}"
    return text


def _write_env_values(updates: dict[str, str]) -> None:
    lines = ENV_FILE.read_text(encoding="utf-8-sig").splitlines() if ENV_FILE.exists() else []
    remaining = dict(updates)
    output: list[str] = []

    for line in lines:
        parsed = parse_env_line(line)
        if parsed and parsed[0] in remaining:
            key = parsed[0]
            output.append(f"{key}={remaining.pop(key)}")
        else:
            output.append(line)

    for key, value in remaining.items():
        output.append(f"{key}={value}")

    ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
    write_text(ENV_FILE, "\n".join(output).rstrip() + "\n")


def migrate_runtime_config_to_env() -> dict[str, list[str]]:
    if not RUNTIME_CONFIG_FILE.exists():
        return {"migrated_keys": [], "skipped_keys": []}

    try:
        import json

        raw = json.loads(RUNTIME_CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"migrated_keys": [], "skipped_keys": []}
    if not isinstance(raw, dict):
        return {"migrated_keys": [], "skipped_keys": []}

    env = read_env_file()
    updates: dict[str, str] = {}
    skipped: list[str] = []
    for runtime_key, env_key in RUNTIME_ENV_MIGRATION.items():
        if runtime_key not in raw:
            continue
        if env.get(env_key, ""):
            skipped.append(env_key)
            continue
        value = str(raw.get(runtime_key) or "").strip()
        if not value:
            continue
        field = ENV_FIELD_BY_KEY[env_key]
        updates[env_key] = _normalize_env_value(field, value)

    if updates:
        _write_env_values(updates)
        for key, value in updates.items():
            os.environ[key] = value
    return {"migrated_keys": list(updates), "skipped_keys": skipped}


def _field_value(field: EnvField, env: dict[str, str]) -> tuple[str, bool, str]:
    if field.key in env:
        return env[field.key], bool(env[field.key]), "env"
    if field.key in os.environ:
        value = os.environ.get(field.key, "")
        return value, bool(value), "process"
    return field.default, bool(field.default), "default"


def _serialize_field(field: EnvField, env: dict[str, str]) -> dict:
    value, has_value, source = _field_value(field, env)
    masked = False
    if field.sensitive:
        display_value = ""
    elif field.mask == "proxy_url":
        display_value = mask_proxy_url(value)
        masked = display_value != value
    else:
        display_value = value
    return {
        "key": field.key,
        "label": field.label,
        "group": field.group,
        "value": display_value,
        "has_value": has_value,
        "source": source,
        "default": field.default,
        "optional": field.optional,
        "sensitive": field.sensitive,
        "restart_required": field.restart_required,
        "type": field.value_type,
        "masked": masked,
        "description": field.description,
    }


def get_env_config() -> dict:
    migration = migrate_runtime_config_to_env()
    env = read_env_file()
    groups = []
    for field in ENV_FIELDS:
        if field.group not in groups:
            groups.append(field.group)
    return {
        "path": str(ENV_FILE),
        "groups": groups,
        "fields": [_serialize_field(field, env) for field in ENV_FIELDS],
        "migration": migration,
    }


def save_env_values(values: dict[str, object]) -> dict:
    unknown = sorted(key for key in values if key not in ENV_FIELD_BY_KEY)
    if unknown:
        raise KeyError(", ".join(unknown))

    updates: dict[str, str] = {}
    restart_required = False
    for key, value in values.items():
        field = ENV_FIELD_BY_KEY[key]
        updates[key] = _normalize_env_value(field, value)
        restart_required = restart_required or field.restart_required

    _write_env_values(updates)
    for key, value in updates.items():
        os.environ[key] = value
    return {"updated_keys": list(updates), "restart_required": restart_required}


def reload_config_modules() -> None:
    module_names = (
        "autoteam.config",
        "autoteam.cloudmail",
        "autoteam.cpa_sync",
        "autoteam.fivesim",
        "autoteam.playwright_config",
    )
    for name in module_names:
        module = sys.modules.get(name)
        if module is not None:
            importlib.reload(module)

import sys

from autoteam.config import PLAYWRIGHT_HEADLESS, get_playwright_launch_options

DEFAULT_CONTEXT_KWARGS = {
    "viewport": {"width": 1280, "height": 800},
    "user_agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/146.0.0.0 Safari/537.36"
    ),
}


def chromium_launch_kwargs() -> dict:
    kwargs = get_playwright_launch_options()
    if sys.platform.startswith("win") and not PLAYWRIGHT_HEADLESS:
        kwargs["slow_mo"] = 100
    return kwargs


def browser_context_kwargs() -> dict:
    return dict(DEFAULT_CONTEXT_KWARGS)

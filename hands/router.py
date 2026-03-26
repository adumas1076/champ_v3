# ============================================
# CHAMP V3 — Hands Router
# Auto-detects: am I running locally (pyautogui
# available, display present) or in cloud?
# Routes to direct local calls or remote WebSocket.
#
# tools.py imports from here instead of
# desktop.py / stealth_browser.py directly.
# Same interface, transparent routing.
# ============================================

import logging
import os

logger = logging.getLogger(__name__)

# ---- Detect environment ----
_is_local = None


def _detect_local() -> bool:
    """Check if we're running on a machine with a display (local) or headless (cloud)."""
    global _is_local
    if _is_local is not None:
        return _is_local

    # Explicit override via env var
    env = os.getenv("CHAMP_HANDS_MODE", "").lower()
    if env == "local":
        _is_local = True
        logger.info("[HANDS ROUTER] Mode: LOCAL (env override)")
        return True
    if env == "remote":
        _is_local = False
        logger.info("[HANDS ROUTER] Mode: REMOTE (env override)")
        return False

    # Auto-detect: try to import pyautogui and check for display
    try:
        import pyautogui
        # On Linux without display, this would fail
        # On Windows/Mac with display, this works
        size = pyautogui.size()
        if size.width > 0:
            _is_local = True
            logger.info(f"[HANDS ROUTER] Mode: LOCAL (display detected: {size.width}x{size.height})")
            return True
    except Exception:
        pass

    _is_local = False
    logger.info("[HANDS ROUTER] Mode: REMOTE (no display detected)")
    return False


# ============================================
# DESKTOP EXPORTS
# Same function signatures as desktop.py
# ============================================

async def desktop_action(instruction: str) -> dict:
    if _detect_local():
        from hands.desktop import desktop_action as _local
        return await _local(instruction)
    else:
        from hands.remote import desktop_action as _remote
        return await _remote(instruction)


async def open_app(app_name: str) -> dict:
    if _detect_local():
        from hands.desktop import open_app as _local
        return await _local(app_name)
    else:
        from hands.remote import open_app as _remote
        return await _remote(app_name)


async def get_open_windows() -> dict:
    if _detect_local():
        from hands.desktop import get_open_windows as _local
        return await _local()
    else:
        from hands.remote import get_open_windows as _remote
        return await _remote()


async def press_key(key: str) -> dict:
    if _detect_local():
        from hands.desktop import press_key as _local
        return await _local(key)
    else:
        from hands.remote import press_key as _remote
        return await _remote(key)


async def desktop_screenshot(region: tuple = None) -> dict:
    if _detect_local():
        from hands.desktop import take_screenshot as _local
        return await _local(region=region)
    else:
        from hands.remote import take_screenshot as _remote
        return await _remote(region=region)


# ============================================
# BROWSER EXPORTS
# Same function signatures as stealth_browser.py
# ============================================

async def browse(url: str) -> dict:
    if _detect_local():
        from hands.stealth_browser import browse as _local
        return await _local(url)
    else:
        from hands.remote import browse as _remote
        return await _remote(url)


async def browser_screenshot(url: str = None) -> dict:
    if _detect_local():
        from hands.stealth_browser import take_screenshot as _local
        return await _local(url=url)
    else:
        from hands.remote import browser_screenshot as _remote
        return await _remote(url=url)


async def click_element(selector: str) -> dict:
    if _detect_local():
        from hands.stealth_browser import click_element as _local
        return await _local(selector)
    else:
        from hands.remote import click_element as _remote
        return await _remote(selector)


async def browser_type_text(selector: str, text: str) -> dict:
    if _detect_local():
        from hands.stealth_browser import type_text as _local
        return await _local(selector, text)
    else:
        from hands.remote import browser_type_text as _remote
        return await _remote(selector, text)


async def fill_form(url: str, fields: list, submit_selector: str = None) -> dict:
    if _detect_local():
        from hands.stealth_browser import fill_form as _local
        return await _local(url, fields, submit_selector)
    else:
        from hands.remote import fill_form as _remote
        return await _remote(url, fields, submit_selector)


async def google_search(query: str) -> dict:
    if _detect_local():
        from hands.stealth_browser import google_search as _local
        return await _local(query)
    else:
        from hands.remote import google_search as _remote
        return await _remote(query)


async def get_page_content() -> dict:
    if _detect_local():
        from hands.stealth_browser import get_page_content as _local
        return await _local()
    else:
        from hands.remote import get_page_content as _remote
        return await _remote()


async def execute_js(script: str) -> dict:
    if _detect_local():
        from hands.stealth_browser import execute_js as _local
        return await _local(script)
    else:
        from hands.remote import execute_js as _remote
        return await _remote(script)


# ============================================
# STATUS
# ============================================

def get_hands_status() -> dict:
    """Return current hands routing status."""
    is_local = _detect_local()
    result = {
        "mode": "local" if is_local else "remote",
        "env_override": os.getenv("CHAMP_HANDS_MODE", "auto"),
    }
    if not is_local:
        from hands.remote import is_agent_connected
        result["agent_connected"] = is_agent_connected()
    return result

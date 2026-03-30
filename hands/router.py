# ============================================
# CHAMP V3 — Hands Router
# Auto-detects: am I running locally (pyautogui
# available, display present) or in cloud?
# Routes to direct local calls or remote WebSocket.
#
# Three modes:
#   LOCAL  — pyautogui/nodriver (has display)
#   REMOTE — direct WebSocket to local agent (Brain process)
#   PROXY  — HTTP to Brain API which relays to local agent (Hetzner agent)
#
# tools.py imports from here instead of
# desktop.py / stealth_browser.py directly.
# Same interface, transparent routing.
# ============================================

import logging
import os

import requests as _requests

logger = logging.getLogger(__name__)

# ---- Detect environment ----
_is_local = None
_mode = None  # "local", "remote", or "proxy"


def _detect_mode() -> str:
    """Detect routing mode: local, remote (Brain process), or proxy (Hetzner agent)."""
    global _mode, _is_local
    if _mode is not None:
        return _mode

    # Explicit override via env var
    env = os.getenv("CHAMP_HANDS_MODE", "").lower()
    if env == "local":
        _mode = "local"
        _is_local = True
        logger.info("[HANDS ROUTER] Mode: LOCAL (env override)")
        return _mode
    if env == "remote":
        _mode = "remote"
        _is_local = False
        logger.info("[HANDS ROUTER] Mode: REMOTE (env override)")
        return _mode
    if env == "proxy":
        _mode = "proxy"
        _is_local = False
        logger.info("[HANDS ROUTER] Mode: PROXY (env override)")
        return _mode

    # Auto-detect: try to import pyautogui and check for display
    try:
        import pyautogui
        size = pyautogui.size()
        if size.width > 0:
            _mode = "local"
            _is_local = True
            logger.info(f"[HANDS ROUTER] Mode: LOCAL (display detected: {size.width}x{size.height})")
            return _mode
    except Exception:
        pass

    _is_local = False

    # No display — are we the Brain process (has WebSocket) or a separate agent?
    # If BRAIN_URL is set and points to another host, we're a separate agent → proxy
    brain_url = os.getenv("BRAIN_URL", "")
    if brain_url and not brain_url.startswith("http://127.0.0.1") and not brain_url.startswith("http://localhost"):
        _mode = "proxy"
        logger.info(f"[HANDS ROUTER] Mode: PROXY (BRAIN_URL={brain_url})")
    else:
        _mode = "remote"
        logger.info("[HANDS ROUTER] Mode: REMOTE (Brain process, direct WebSocket)")

    return _mode


def _detect_local() -> bool:
    """Legacy compat — returns True if local mode."""
    _detect_mode()
    return _is_local


# ============================================
# PROXY — HTTP calls to Brain /v1/hands/execute
# Used by Hetzner agent to reach local desktop
# ============================================

def _brain_url() -> str:
    return os.getenv("BRAIN_URL", "http://127.0.0.1:8100")


async def _proxy_command(command: str, args: dict, timeout: float = 60.0) -> dict:
    """Send a command to the Brain's hands proxy endpoint."""
    try:
        resp = _requests.post(
            f"{_brain_url()}/v1/hands/execute",
            json={"command": command, "args": args, "timeout": timeout},
            timeout=timeout + 5,
        )
        return resp.json()
    except _requests.Timeout:
        return {"ok": False, "error": f"Brain proxy timed out after {timeout}s"}
    except Exception as e:
        return {"ok": False, "error": f"Brain proxy error: {e}"}


# ============================================
# DESKTOP EXPORTS
# Same function signatures as desktop.py
# ============================================

async def desktop_action(instruction: str) -> dict:
    mode = _detect_mode()
    if mode == "local":
        from hands.desktop import desktop_action as _local
        return await _local(instruction)
    elif mode == "proxy":
        return await _proxy_command("desktop_action", {"instruction": instruction})
    else:
        from hands.remote import desktop_action as _remote
        return await _remote(instruction)


async def open_app(app_name: str) -> dict:
    mode = _detect_mode()
    if mode == "local":
        from hands.desktop import open_app as _local
        return await _local(app_name)
    elif mode == "proxy":
        return await _proxy_command("open_app", {"app_name": app_name})
    else:
        from hands.remote import open_app as _remote
        return await _remote(app_name)


async def get_open_windows() -> dict:
    mode = _detect_mode()
    if mode == "local":
        from hands.desktop import get_open_windows as _local
        return await _local()
    elif mode == "proxy":
        return await _proxy_command("get_open_windows", {})
    else:
        from hands.remote import get_open_windows as _remote
        return await _remote()


async def press_key(key: str) -> dict:
    mode = _detect_mode()
    if mode == "local":
        from hands.desktop import press_key as _local
        return await _local(key)
    elif mode == "proxy":
        return await _proxy_command("press_key", {"key": key})
    else:
        from hands.remote import press_key as _remote
        return await _remote(key)


async def desktop_screenshot(region: tuple = None) -> dict:
    mode = _detect_mode()
    if mode == "local":
        from hands.desktop import take_screenshot as _local
        return await _local(region=region)
    elif mode == "proxy":
        return await _proxy_command("desktop_screenshot", {"region": list(region) if region else None})
    else:
        from hands.remote import take_screenshot as _remote
        return await _remote(region=region)


# ============================================
# BROWSER EXPORTS
# Same function signatures as stealth_browser.py
# ============================================

async def browse(url: str) -> dict:
    mode = _detect_mode()
    if mode == "local":
        from hands.stealth_browser import browse as _local
        return await _local(url)
    elif mode == "proxy":
        return await _proxy_command("browse", {"url": url})
    else:
        from hands.remote import browse as _remote
        return await _remote(url)


async def browser_screenshot(url: str = None) -> dict:
    mode = _detect_mode()
    if mode == "local":
        from hands.stealth_browser import take_screenshot as _local
        return await _local(url=url)
    elif mode == "proxy":
        return await _proxy_command("browser_screenshot", {"url": url})
    else:
        from hands.remote import browser_screenshot as _remote
        return await _remote(url=url)


async def click_element(selector: str) -> dict:
    mode = _detect_mode()
    if mode == "local":
        from hands.stealth_browser import click_element as _local
        return await _local(selector)
    elif mode == "proxy":
        return await _proxy_command("click_element", {"selector": selector})
    else:
        from hands.remote import click_element as _remote
        return await _remote(selector)


async def browser_type_text(selector: str, text: str) -> dict:
    mode = _detect_mode()
    if mode == "local":
        from hands.stealth_browser import type_text as _local
        return await _local(selector, text)
    elif mode == "proxy":
        return await _proxy_command("browser_type_text", {"selector": selector, "text": text})
    else:
        from hands.remote import browser_type_text as _remote
        return await _remote(selector, text)


async def fill_form(url: str, fields: list, submit_selector: str = None) -> dict:
    mode = _detect_mode()
    if mode == "local":
        from hands.stealth_browser import fill_form as _local
        return await _local(url, fields, submit_selector)
    elif mode == "proxy":
        return await _proxy_command("fill_form", {"url": url, "fields": fields, "submit_selector": submit_selector})
    else:
        from hands.remote import fill_form as _remote
        return await _remote(url, fields, submit_selector)


async def google_search(query: str) -> dict:
    mode = _detect_mode()
    if mode == "local":
        from hands.stealth_browser import google_search as _local
        return await _local(query)
    elif mode == "proxy":
        return await _proxy_command("google_search", {"query": query})
    else:
        from hands.remote import google_search as _remote
        return await _remote(query)


async def get_page_content() -> dict:
    mode = _detect_mode()
    if mode == "local":
        from hands.stealth_browser import get_page_content as _local
        return await _local()
    elif mode == "proxy":
        return await _proxy_command("get_page_content", {})
    else:
        from hands.remote import get_page_content as _remote
        return await _remote()


async def execute_js(script: str) -> dict:
    mode = _detect_mode()
    if mode == "local":
        from hands.stealth_browser import execute_js as _local
        return await _local(script)
    elif mode == "proxy":
        return await _proxy_command("execute_js", {"script": script})
    else:
        from hands.remote import execute_js as _remote
        return await _remote(script)


# ============================================
# STATUS
# ============================================

def get_hands_status() -> dict:
    """Return current hands routing status."""
    mode = _detect_mode()
    result = {
        "mode": mode,
        "env_override": os.getenv("CHAMP_HANDS_MODE", "auto"),
    }
    if mode == "remote":
        from hands.remote import is_agent_connected
        result["agent_connected"] = is_agent_connected()
    elif mode == "proxy":
        try:
            resp = _requests.get(f"{_brain_url()}/v1/hands/status", timeout=5)
            result["brain_hands_status"] = resp.json()
        except Exception:
            result["brain_hands_status"] = {"error": "Could not reach Brain"}
    return result

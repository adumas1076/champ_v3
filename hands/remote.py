# ============================================
# CHAMP V3 — Remote Hands Client
# Cloud-side: sends commands to the local agent
# via WebSocket. Same interface as desktop.py
# and stealth_browser.py so tools.py doesn't
# know the difference.
# ============================================

import asyncio
import json
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

# The connected local agent (set by Brain WebSocket endpoint)
_agent_ws = None
_agent_lock = asyncio.Lock()
_pending: dict[str, asyncio.Future] = {}
_request_counter = 0


def set_agent_connection(ws):
    """Called by Brain WS endpoint when a local agent connects."""
    global _agent_ws
    _agent_ws = ws
    logger.info("[REMOTE HANDS] Local agent connected")


def clear_agent_connection():
    """Called when local agent disconnects."""
    global _agent_ws
    _agent_ws = None
    logger.info("[REMOTE HANDS] Local agent disconnected")


def is_agent_connected() -> bool:
    return _agent_ws is not None


async def _send_command(command: str, args: dict, timeout: float = 60.0) -> dict:
    """Send a command to the local agent and wait for the response."""
    global _request_counter

    if not _agent_ws:
        return {"ok": False, "error": "No local hands agent connected. Run local_agent.py on your machine."}

    _request_counter += 1
    request_id = f"req-{_request_counter}-{int(time.time())}"

    payload = json.dumps({
        "id": request_id,
        "command": command,
        "args": args,
    })

    # Create a future to wait for the response
    loop = asyncio.get_event_loop()
    future = loop.create_future()
    _pending[request_id] = future

    try:
        await _agent_ws.send_text(payload)
        logger.info(f"[REMOTE HANDS] Sent: {command} (id={request_id})")

        # Wait for response with timeout
        result = await asyncio.wait_for(future, timeout=timeout)
        return result

    except asyncio.TimeoutError:
        logger.error(f"[REMOTE HANDS] Timeout waiting for {command} (id={request_id})")
        return {"ok": False, "error": f"Local agent timed out after {timeout}s"}
    except Exception as e:
        logger.error(f"[REMOTE HANDS] Error sending {command}: {e}")
        return {"ok": False, "error": str(e)}
    finally:
        _pending.pop(request_id, None)


def handle_agent_response(data: dict):
    """Called by Brain WS endpoint when the local agent sends a response."""
    request_id = data.get("id")
    if request_id and request_id in _pending:
        future = _pending[request_id]
        if not future.done():
            future.set_result(data.get("result", {"ok": False, "error": "No result"}))
    else:
        logger.warning(f"[REMOTE HANDS] Got response for unknown request: {request_id}")


# ============================================
# DESKTOP COMMANDS (mirror desktop.py interface)
# ============================================

async def desktop_action(instruction: str) -> dict:
    return await _send_command("desktop_action", {"instruction": instruction})

async def open_app(app_name: str) -> dict:
    return await _send_command("open_app", {"app_name": app_name})

async def get_open_windows() -> dict:
    return await _send_command("get_open_windows", {})

async def focus_window(title_contains: str) -> dict:
    return await _send_command("focus_window", {"title_contains": title_contains})

async def mouse_click(x: int, y: int, button: str = "left", clicks: int = 1) -> dict:
    return await _send_command("mouse_click", {"x": x, "y": y, "button": button, "clicks": clicks})

async def press_key(key: str) -> dict:
    return await _send_command("press_key", {"key": key})

async def type_text(text: str, interval: float = 0.03) -> dict:
    return await _send_command("type_text", {"text": text, "interval": interval})

async def take_screenshot(region: tuple = None) -> dict:
    return await _send_command("desktop_screenshot", {"region": list(region) if region else None})


# ============================================
# BROWSER COMMANDS (mirror stealth_browser.py interface)
# ============================================

async def browse(url: str) -> dict:
    return await _send_command("browse", {"url": url})

async def browser_screenshot(url: str = None) -> dict:
    return await _send_command("browser_screenshot", {"url": url})

async def click_element(selector: str) -> dict:
    return await _send_command("click_element", {"selector": selector})

async def browser_type_text(selector: str, text: str) -> dict:
    return await _send_command("browser_type_text", {"selector": selector, "text": text})

async def fill_form(url: str, fields: list, submit_selector: str = None) -> dict:
    return await _send_command("fill_form", {"url": url, "fields": fields, "submit_selector": submit_selector})

async def google_search(query: str) -> dict:
    return await _send_command("google_search", {"query": query})

async def get_page_content() -> dict:
    return await _send_command("get_page_content", {})

async def execute_js(script: str) -> dict:
    return await _send_command("execute_js", {"script": script})

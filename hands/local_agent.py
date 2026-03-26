#!/usr/bin/env python3
# ============================================
# CHAMP V3 — Local Hands Agent
# Run this on any machine you want Champ to
# control. Connects to cloud Brain via WebSocket
# and executes desktop/browser commands locally.
#
# Usage:
#   python hands/local_agent.py
#   python hands/local_agent.py --brain wss://your-brain.railway.app
#
# Requires: pyautogui, pygetwindow, nodriver, websockets
# ============================================

import argparse
import asyncio
import base64
import json
import logging
import os
import sys
import time
from pathlib import Path

# Add parent dir so we can import hands modules when run standalone
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import websockets

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [HANDS] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ============================================
# COMMAND HANDLERS
# Map command names to local functions.
# Each handler receives args dict, returns result dict.
# ============================================

async def handle_desktop_action(args: dict) -> dict:
    from hands.desktop import desktop_action
    return await desktop_action(args.get("instruction", ""))


async def handle_open_app(args: dict) -> dict:
    from hands.desktop import open_app
    return await open_app(args.get("app_name", ""))


async def handle_get_open_windows(args: dict) -> dict:
    from hands.desktop import get_open_windows
    return await get_open_windows()


async def handle_focus_window(args: dict) -> dict:
    from hands.desktop import focus_window
    return await focus_window(args.get("title_contains", ""))


async def handle_mouse_click(args: dict) -> dict:
    from hands.desktop import mouse_click
    return await mouse_click(
        x=args.get("x", 0),
        y=args.get("y", 0),
        button=args.get("button", "left"),
        clicks=args.get("clicks", 1),
    )


async def handle_press_key(args: dict) -> dict:
    from hands.desktop import press_key
    return await press_key(args.get("key", ""))


async def handle_type_text(args: dict) -> dict:
    from hands.desktop import type_text
    return await type_text(
        text=args.get("text", ""),
        interval=args.get("interval", 0.03),
    )


async def handle_desktop_screenshot(args: dict) -> dict:
    from hands.desktop import take_screenshot
    region = args.get("region")
    if region and isinstance(region, list) and len(region) == 4:
        region = tuple(region)
    else:
        region = None
    result = await take_screenshot(region=region)

    # Encode screenshot as base64 so it can travel over WebSocket
    if result.get("ok") and result.get("path"):
        try:
            with open(result["path"], "rb") as f:
                result["image_b64"] = base64.b64encode(f.read()).decode("ascii")
        except Exception:
            pass
    return result


async def handle_browse(args: dict) -> dict:
    from hands.stealth_browser import browse
    return await browse(args.get("url", ""))


async def handle_browser_screenshot(args: dict) -> dict:
    from hands.stealth_browser import take_screenshot
    result = await take_screenshot(url=args.get("url"))

    # Encode screenshot as base64
    if result.get("ok") and result.get("path"):
        try:
            with open(result["path"], "rb") as f:
                result["image_b64"] = base64.b64encode(f.read()).decode("ascii")
        except Exception:
            pass
    return result


async def handle_click_element(args: dict) -> dict:
    from hands.stealth_browser import click_element
    return await click_element(args.get("selector", ""))


async def handle_browser_type_text(args: dict) -> dict:
    from hands.stealth_browser import type_text
    return await type_text(
        selector=args.get("selector", ""),
        text=args.get("text", ""),
    )


async def handle_fill_form(args: dict) -> dict:
    from hands.stealth_browser import fill_form
    return await fill_form(
        url=args.get("url", ""),
        fields=args.get("fields", []),
        submit_selector=args.get("submit_selector"),
    )


async def handle_google_search(args: dict) -> dict:
    from hands.stealth_browser import google_search
    return await google_search(args.get("query", ""))


async def handle_get_page_content(args: dict) -> dict:
    from hands.stealth_browser import get_page_content
    return await get_page_content()


async def handle_execute_js(args: dict) -> dict:
    from hands.stealth_browser import execute_js
    return await execute_js(args.get("script", ""))


# Command registry
HANDLERS = {
    "desktop_action": handle_desktop_action,
    "open_app": handle_open_app,
    "get_open_windows": handle_get_open_windows,
    "focus_window": handle_focus_window,
    "mouse_click": handle_mouse_click,
    "press_key": handle_press_key,
    "type_text": handle_type_text,
    "desktop_screenshot": handle_desktop_screenshot,
    "browse": handle_browse,
    "browser_screenshot": handle_browser_screenshot,
    "click_element": handle_click_element,
    "browser_type_text": handle_browser_type_text,
    "fill_form": handle_fill_form,
    "google_search": handle_google_search,
    "get_page_content": handle_get_page_content,
    "execute_js": handle_execute_js,
}


# ============================================
# WEBSOCKET CLIENT
# Connects OUT to Brain, receives commands,
# executes locally, sends results back.
# ============================================

async def run_agent(brain_url: str, auth_token: str = ""):
    """Main loop — connect to Brain and process commands."""
    headers = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    while True:
        try:
            ws_url = f"{brain_url}/ws/hands"
            logger.info(f"Connecting to Brain at {ws_url}...")

            async with websockets.connect(
                ws_url,
                additional_headers=headers,
                ping_interval=20,
                ping_timeout=10,
                max_size=10 * 1024 * 1024,  # 10MB for screenshots
            ) as ws:
                logger.info("Connected to Brain! Waiting for commands...")

                async for message in ws:
                    try:
                        data = json.loads(message)
                        request_id = data.get("id", "unknown")
                        command = data.get("command", "")
                        args = data.get("args", {})

                        logger.info(f"Command: {command} (id={request_id})")

                        handler = HANDLERS.get(command)
                        if not handler:
                            result = {"ok": False, "error": f"Unknown command: {command}"}
                        else:
                            try:
                                result = await handler(args)
                            except Exception as e:
                                logger.error(f"Handler error for {command}: {e}")
                                result = {"ok": False, "error": str(e)}

                        # Send response back
                        response = json.dumps({
                            "id": request_id,
                            "result": result,
                        })
                        await ws.send(response)
                        logger.info(f"Response sent for {command} (ok={result.get('ok')})")

                    except json.JSONDecodeError:
                        logger.error(f"Invalid JSON received: {message[:100]}")
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")

        except websockets.ConnectionClosedError as e:
            logger.warning(f"Connection closed: {e}. Reconnecting in 5s...")
        except ConnectionRefusedError:
            logger.warning("Brain not reachable. Retrying in 5s...")
        except Exception as e:
            logger.error(f"Connection error: {e}. Retrying in 5s...")

        await asyncio.sleep(5)


def main():
    parser = argparse.ArgumentParser(
        description="CHAMP Local Hands Agent — run on any machine for remote desktop/browser control"
    )
    parser.add_argument(
        "--brain",
        default=os.getenv("CHAMP_BRAIN_URL", "ws://127.0.0.1:8100"),
        help="Brain WebSocket URL (default: ws://127.0.0.1:8100 or CHAMP_BRAIN_URL env var)",
    )
    parser.add_argument(
        "--token",
        default=os.getenv("CHAMP_HANDS_TOKEN", ""),
        help="Auth token for Brain connection (default: CHAMP_HANDS_TOKEN env var)",
    )
    args = parser.parse_args()

    print("=" * 50)
    print("  CHAMP Local Hands Agent")
    print(f"  Brain: {args.brain}")
    print(f"  Auth: {'yes' if args.token else 'none'}")
    print("  Ctrl+C to stop")
    print("=" * 50)

    asyncio.run(run_agent(args.brain, args.token))


if __name__ == "__main__":
    main()

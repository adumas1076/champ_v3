# ============================================
# CHAMP V3 — Hands Bridge
# Python async wrapper for Node.js Puppeteer CLI
# Calls: node index.js <command> '<json_args>'
# ============================================

import asyncio
import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

HANDS_DIR = Path(__file__).resolve().parent
INDEX_JS = HANDS_DIR / "index.js"
NODE_BIN = "node"


async def call_hands(command: str, args: dict, timeout: float = 60.0) -> dict:
    """Call the Hands Node.js bridge with a command and arguments."""
    args_json = json.dumps(args)
    logger.info(f"[HANDS] {command} | args={args_json[:200]}")

    try:
        process = await asyncio.create_subprocess_exec(
            NODE_BIN, str(INDEX_JS), command, args_json,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(HANDS_DIR),
        )

        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=timeout
        )

        if stderr:
            logger.debug(f"[HANDS] stderr: {stderr.decode()[:500]}")

        if process.returncode != 0:
            error_msg = stderr.decode().strip() or f"Process exited with code {process.returncode}"
            logger.error(f"[HANDS] Failed: {error_msg}")
            return {"ok": False, "error": error_msg}

        output = stdout.decode().strip()
        if not output:
            return {"ok": False, "error": "No output from Hands"}

        # Parse first line only (JSON protocol)
        first_line = output.split("\n")[0]
        result = json.loads(first_line)
        logger.info(f"[HANDS] {command} complete | ok={result.get('ok')}")
        return result

    except asyncio.TimeoutError:
        logger.error(f"[HANDS] Timeout after {timeout}s for {command}")
        return {"ok": False, "error": f"Timeout after {timeout}s"}
    except json.JSONDecodeError as e:
        logger.error(f"[HANDS] Invalid JSON from Node: {e}")
        return {"ok": False, "error": f"Invalid JSON response: {e}"}
    except Exception as e:
        logger.error(f"[HANDS] Bridge error: {e}")
        return {"ok": False, "error": str(e)}


# ---- Convenience functions ----

async def browse(url: str) -> dict:
    """Navigate to URL, return page text and metadata."""
    return await call_hands("browse", {"url": url})


async def take_screenshot(url: str) -> dict:
    """Navigate to URL, take screenshot, return file path."""
    return await call_hands("screenshot", {"url": url})


async def fill_form(url: str, fields: list, submit_selector: str = None) -> dict:
    """Navigate to URL, fill form fields with human-like typing."""
    args = {"url": url, "fields": fields}
    if submit_selector:
        args["submit_selector"] = submit_selector
    return await call_hands("fill_form", args)

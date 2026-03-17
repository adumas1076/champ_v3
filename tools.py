# ============================================
# CHAMP V3 — Function Tools
# Ported from champ_v1/core/tools.py + Brain + Hands
# Pattern: @function_tool() + RunContext
# ============================================

import asyncio
import json as _json
import logging
import os
from pathlib import Path
from livekit.agents import function_tool, RunContext
import requests
# Puppeteer removed — stealth browser (nodriver) is the only browser now
from hands.stealth_browser import (
    browse as stealth_browse,
    take_screenshot as stealth_screenshot,
    fill_form as stealth_fill_form,
    click_element as stealth_click,
    type_text as stealth_type,
    google_search as stealth_google_search,
    get_page_content as stealth_get_page,
    execute_js as stealth_js,
)
from hands.desktop import (
    desktop_action,
    open_app as desktop_open_app,
    get_open_windows as desktop_list_windows,
    press_key as desktop_press_key,
    take_screenshot as desktop_screenshot,
    get_ui_elements,
)

OUTPUT_DIR = Path(__file__).resolve().parent / "output"

BRAIN_URL = os.getenv("BRAIN_URL", "http://127.0.0.1:8100")

# Session state — set by start_brain_session(), used by ask_brain
_conversation_id = None

# Self Mode run tracking — for proactive notifications
_pending_run_ids: set[str] = set()


def start_brain_session() -> str | None:
    """Start a Brain session. Returns conversation_id."""
    global _conversation_id
    try:
        r = requests.post(f"{BRAIN_URL}/v1/session/start", json={"channel": "voice"}, timeout=10)
        r.raise_for_status()
        _conversation_id = r.json().get("conversation_id")
        logging.info(f"Brain session started: {_conversation_id}")
        return _conversation_id
    except Exception as e:
        logging.error(f"Failed to start brain session: {e}")
        return None


def end_brain_session():
    """End the current Brain session."""
    global _conversation_id
    if not _conversation_id:
        return
    try:
        requests.post(
            f"{BRAIN_URL}/v1/session/end",
            json={"conversation_id": _conversation_id},
            timeout=10,
        )
        logging.info(f"Brain session ended: {_conversation_id}")
    except Exception as e:
        logging.error(f"Failed to end brain session: {e}")
    _conversation_id = None


@function_tool()
async def get_weather(
    context: RunContext,
    city: str,
) -> str:
    """Get the current weather for a given city."""
    try:
        response = requests.get(f"https://wttr.in/{city}?format=3")
        if response.status_code == 200:
            logging.info(f"Weather for {city}: {response.text.strip()}")
            return response.text.strip()
        else:
            logging.error(f"Failed to get weather for {city}: {response.status_code}")
            return f"Could not retrieve weather for {city}."
    except Exception as e:
        logging.error(f"Error retrieving weather for {city}: {e}")
        return f"An error occurred while retrieving weather for {city}."


# search_web removed — replaced by google_search (real browser)


@function_tool()
async def ask_brain(
    context: RunContext,
    question: str,
) -> str:
    """Ask the Brain for a deep, thoughtful answer. Use this for complex questions,
    coding help, build plans, architecture advice, or anything that needs more than
    a quick voice response. The Brain uses Claude Sonnet with Champ's full persona."""
    try:
        payload = {
            "model": "claude-sonnet",
            "messages": [{"role": "user", "content": question}],
            "stream": False,
            "max_tokens": 1000,
        }
        if _conversation_id:
            payload["user"] = _conversation_id
        response = requests.post(
            f"{BRAIN_URL}/v1/chat/completions",
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        logging.info(f"Brain response for '{question[:50]}...': {len(content)} chars")
        return content
    except Exception as e:
        logging.error(f"Brain error for '{question[:50]}...': {e}")
        return f"Brain is offline or errored: {e}"


# ============================================
# HANDS TOOLS — Brick 5
# ============================================

@function_tool()
async def browse_url(
    context: RunContext,
    url: str,
) -> str:
    """Browse a URL using the real browser (undetectable). Returns the page title and visible text.
    Use this when the user asks you to go to a website, check a page, or read web content.
    This uses the user's actual browser — logged-in sessions, cookies, everything."""
    try:
        result = await stealth_browse(url)
        if not result.get("ok"):
            return f"Failed to browse {url}: {result.get('error', 'Unknown error')}"
        title = result.get("title", "No title")
        text = result.get("text", "No content")[:1500]
        return f"Page: {title}\nURL: {result.get('url', url)}\n\nContent:\n{text}"
    except Exception as e:
        logging.error(f"browse_url error: {e}")
        return f"Browser error: {e}"


@function_tool()
async def take_screenshot(
    context: RunContext,
    url: str = "",
) -> str:
    """Take a screenshot of a webpage or the current desktop screen.
    If url is provided, navigates there first. If empty, captures current screen.
    Use this when the user asks to capture or screenshot a page or their screen."""
    try:
        if url:
            result = await stealth_screenshot(url)
        else:
            result = await desktop_screenshot()

        if not result.get("ok"):
            return f"Failed to screenshot: {result.get('error', 'Unknown error')}"
        filepath = result.get("path", "unknown")
        title = result.get("title", "")
        msg = f"Screenshot saved: {filepath}"
        if title:
            msg += f"\nPage: {title}"
        return msg
    except Exception as e:
        logging.error(f"screenshot error: {e}")
        return f"Screenshot error: {e}"


@function_tool()
async def fill_web_form(
    context: RunContext,
    url: str,
    fields: str,
) -> str:
    """Fill form fields on a webpage with human-like typing in the real browser.
    The fields parameter should be a JSON string like:
    [{"selector": "input[name='email']", "value": "test@example.com"}]
    Use this when the user asks to fill out or sign up on a website."""
    try:
        fields_list = _json.loads(fields)
        result = await stealth_fill_form(url, fields_list)
        if not result.get("ok"):
            return f"Failed to fill form on {url}: {result.get('error', 'Unknown error')}"
        filled = result.get("fields_filled", [])
        return f"Form filled on {result.get('title', url)}: {len(filled)} fields completed"
    except _json.JSONDecodeError:
        return "Invalid fields format. Expected JSON array of {selector, value} objects."
    except Exception as e:
        logging.error(f"fill_form error: {e}")
        return f"Form fill error: {e}"


# ============================================
# GOOGLE SEARCH — Real Browser
# ============================================

@function_tool()
async def google_search(
    context: RunContext,
    query: str,
) -> str:
    """Search Google using the user's real browser. Returns top 5 results with titles,
    URLs, and snippets. This uses the user's actual Google account — personalized results.
    Use this when the user asks to search or Google something."""
    try:
        result = await stealth_google_search(query)
        if not result.get("ok"):
            return f"Google search failed: {result.get('error', 'Unknown error')}"

        results = result.get("results", [])
        if not results:
            return f"No results found for: {query}"

        output = f"Google results for '{query}':\n\n"
        for i, r in enumerate(results, 1):
            output += f"{i}. {r.get('title', 'No title')}\n"
            output += f"   {r.get('url', '')}\n"
            output += f"   {r.get('snippet', '')}\n\n"
        return output
    except Exception as e:
        logging.error(f"google_search error: {e}")
        return f"Search error: {e}"


# ============================================
# DESKTOP CONTROL TOOLS — Full Hands
# ============================================

@function_tool()
async def control_desktop(
    context: RunContext,
    instruction: str,
) -> str:
    """Control the desktop — open apps, click buttons, type text, press keys, take screenshots.
    This controls the user's ACTUAL screen. Examples:
    - "open Chrome" / "open Excel" / "open Spotify"
    - "type Hello World"
    - "press ctrl+c" / "press enter" / "press alt+f4"
    - "click Save in Notepad"
    - "screenshot"
    - "list windows"
    - "focus Chrome"
    - "scroll down"
    Use this when the user asks to interact with desktop apps or their screen."""
    try:
        result = await desktop_action(instruction)
        if not result.get("ok"):
            return f"Desktop action failed: {result.get('error', 'Unknown error')}"

        # Build response based on action type
        action = result.get("action", "")
        if action == "launched":
            return f"Opened {result.get('app', instruction)}"
        elif action == "focused":
            return f"Focused window: {result.get('window', '')}"
        elif "windows" in result:
            windows = result["windows"]
            if not windows:
                return "No windows open."
            output = f"Open windows ({len(windows)}):\n"
            for w in windows[:15]:
                output += f"  - {w['title']}\n"
            return output
        elif "path" in result:
            return f"Screenshot saved: {result['path']}"
        elif "clicked" in result:
            return f"Clicked: {result['clicked']}"
        elif "typed" in result:
            return f"Typed: {result['typed']}"
        elif "key" in result:
            return f"Pressed: {result['key']}"
        elif "scrolled" in result:
            return f"Scrolled {result['scrolled']} clicks"
        else:
            return f"Done: {_json.dumps(result)}"
    except Exception as e:
        logging.error(f"control_desktop error: {e}")
        return f"Desktop error: {e}"


@function_tool()
async def read_screen(
    context: RunContext,
    window_title: str = "",
) -> str:
    """Read the UI elements visible on screen or in a specific window.
    Returns clickable elements with their names — useful for figuring out
    what to click or interact with. Use this before clicking things on the desktop."""
    try:
        result = await get_ui_elements(window_title or None)
        if not result.get("ok"):
            return f"Could not read UI: {result.get('error', 'Unknown error')}"

        elements = result.get("elements", [])
        if not elements:
            return f"No UI elements found in '{window_title or 'foreground window'}'."

        output = f"UI elements in '{result.get('window', 'foreground')}' ({len(elements)} found):\n\n"
        for el in elements[:30]:
            output += f"  [{el['type']}] \"{el['name']}\" at ({el['x']}, {el['y']})\n"
        if len(elements) > 30:
            output += f"\n  ... and {len(elements) - 30} more"
        return output
    except Exception as e:
        logging.error(f"read_screen error: {e}")
        return f"Screen read error: {e}"


@function_tool()
async def run_code(
    context: RunContext,
    code: str,
    language: str = "python",
) -> str:
    """Execute a code snippet and return the output. Supports Python and JavaScript.
    Use this when the user asks to run, execute, or test code."""
    try:
        if language.lower() in ("python", "py"):
            proc = await asyncio.create_subprocess_exec(
                "python", "-c", code,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        elif language.lower() in ("javascript", "js", "node"):
            proc = await asyncio.create_subprocess_exec(
                "node", "-e", code,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        else:
            return f"Unsupported language: {language}. Use 'python' or 'javascript'."

        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30.0)
        output = stdout.decode().strip()
        errors = stderr.decode().strip()

        if proc.returncode != 0:
            return f"Error (exit {proc.returncode}):\n{errors}"

        result = output if output else "(no output)"
        if errors:
            result += f"\n\nWarnings:\n{errors}"
        return result
    except asyncio.TimeoutError:
        return "Code execution timed out after 30 seconds."
    except Exception as e:
        logging.error(f"run_code error: {e}")
        return f"Execution error: {e}"


@function_tool()
async def create_file(
    context: RunContext,
    filename: str,
    content: str,
) -> str:
    """Create a file with the given content and save it. Returns the file path.
    Use this when the user asks to write, create, or save a file or script."""
    try:
        OUTPUT_DIR.mkdir(exist_ok=True)
        safe_name = Path(filename).name
        if not safe_name:
            return "Invalid filename."
        filepath = OUTPUT_DIR / safe_name
        filepath.write_text(content, encoding="utf-8")
        logging.info(f"File created: {filepath} ({len(content)} chars)")
        return f"File saved: {filepath}"
    except Exception as e:
        logging.error(f"create_file error: {e}")
        return f"File creation error: {e}"


# ============================================
# SELF MODE TOOLS -- Brick 8.5
# ============================================

@function_tool()
async def go_do(
    context: RunContext,
    task: str,
) -> str:
    """Hand off a task to Self Mode for autonomous execution.
    Use this when the user asks you to build, create, write, or make something
    that requires multiple steps -- like a script, tool, data pipeline, scraper, etc.
    Self Mode will plan, execute, review, fix, and deliver the result autonomously.
    Returns a run ID so you can check on progress later with check_task."""
    try:
        response = requests.post(
            f"{BRAIN_URL}/v1/self_mode/submit",
            json={"task": task},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        run_id = data.get("run_id", "unknown")
        _pending_run_ids.add(run_id)
        logging.info(f"Self Mode task submitted: {run_id} for '{task[:60]}'")
        return (
            f"Got it -- I'm on it. Self Mode run started: {run_id}. "
            f"I'll plan, build, test, and deliver this autonomously. "
            f"You can ask me to check on it anytime."
        )
    except Exception as e:
        logging.error(f"go_do error: {e}")
        return f"Failed to start Self Mode task: {e}. Brain might be offline."


@function_tool()
async def check_task(
    context: RunContext,
    run_id: str,
) -> str:
    """Check the status of a Self Mode task that was handed off earlier.
    Use this when the user asks about the progress of a task you handed off."""
    try:
        response = requests.get(
            f"{BRAIN_URL}/v1/self_mode/status/{run_id}",
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()

        status = data.get("db_status") or data.get("in_memory_status", "unknown")
        step = data.get("current_step", "?")
        result_pack = data.get("result_pack")

        step_names = [
            "receive", "plan", "approve", "execute",
            "review", "fix", "package", "learn", "deliver",
        ]
        step_label = step_names[step] if isinstance(step, int) and step < len(step_names) else str(step)

        summary = f"Run {run_id}: status={status}, step={step_label}"

        if result_pack:
            rp_status = result_pack.get("status", "")
            deliverables = result_pack.get("deliverables", "")
            issues = result_pack.get("issues_hit", "")
            summary += f"\nResult: {rp_status}"
            if deliverables:
                summary += f"\nDeliverables: {deliverables[:500]}"
            if issues and issues != "No issues":
                summary += f"\nIssues: {issues[:300]}"

        return summary
    except requests.exceptions.HTTPError as e:
        if e.response and e.response.status_code == 404:
            return f"Run {run_id} not found. It may have expired or the ID might be wrong."
        return f"Error checking task: {e}"
    except Exception as e:
        logging.error(f"check_task error: {e}")
        return f"Error checking task status: {e}"


@function_tool()
async def approve_task(
    context: RunContext,
    run_id: str,
) -> str:
    """Approve a Self Mode task that is waiting for approval.
    Use this when the user says to approve a task, go ahead, or gives the green light."""
    try:
        response = requests.post(
            f"{BRAIN_URL}/v1/self_mode/approve/{run_id}",
            timeout=30,
        )
        if response.status_code == 404:
            return f"Run {run_id} not found."
        if response.status_code == 400:
            data = response.json()
            return f"Can't approve: {data.get('error', 'unknown reason')}"
        response.raise_for_status()
        return f"Approved. Task {run_id} is now resuming execution."
    except Exception as e:
        logging.error(f"approve_task error: {e}")
        return f"Failed to approve task: {e}"


@function_tool()
async def resume_task(
    context: RunContext,
    run_id: str,
) -> str:
    """Resume a Self Mode task that crashed or got blocked.
    Use this when the user asks to retry, resume, or continue a failed or stuck task."""
    try:
        response = requests.post(
            f"{BRAIN_URL}/v1/self_mode/resume/{run_id}",
            timeout=30,
        )
        if response.status_code == 404:
            return f"Run {run_id} not found."
        if response.status_code == 400:
            return f"Can't resume: {response.json().get('error', 'unknown')}"
        if response.status_code == 409:
            return f"Task {run_id} is already running."
        response.raise_for_status()
        data = response.json()
        return f"Resuming task {run_id} from step {data.get('from_step', '?')}."
    except Exception as e:
        logging.error(f"resume_task error: {e}")
        return f"Failed to resume task: {e}"


# ============================================
# PROACTIVE NOTIFICATION — Polling Helper
# ============================================

def poll_completed_runs() -> list[dict]:
    """
    Check all pending run_ids for completion.
    Returns list of completed run dicts and removes them from pending.
    Called by the notification coroutine in agent.py.
    """
    global _pending_run_ids
    completed = []
    to_remove = set()
    for run_id in list(_pending_run_ids):
        try:
            response = requests.get(
                f"{BRAIN_URL}/v1/self_mode/status/{run_id}",
                timeout=5,
            )
            if response.status_code != 200:
                continue
            data = response.json()
            db_status = data.get("db_status", "")
            in_memory = data.get("in_memory_status", "")
            # Terminal states
            if db_status in (
                "complete", "partial", "failed", "blocked",
            ) or in_memory in ("finished", "error"):
                completed.append(data)
                to_remove.add(run_id)
        except Exception:
            pass  # Network error, skip this tick
    _pending_run_ids -= to_remove
    return completed

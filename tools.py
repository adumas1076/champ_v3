# ============================================
# CHAMP V3 — Function Tools
# Ported from champ_v1/core/tools.py + Brain + Hands
# Pattern: @function_tool() + RunContext
# ============================================

import asyncio
import base64
import json as _json
import logging
import os
from pathlib import Path
from livekit.agents import function_tool, RunContext
import requests
# Hands Router — auto-detects local vs cloud, routes accordingly
from hands.router import (
    browse as stealth_browse,
    browser_screenshot as stealth_screenshot,
    fill_form as stealth_fill_form,
    click_element as stealth_click,
    browser_type_text as stealth_type,
    google_search as stealth_google_search,
    get_page_content as stealth_get_page,
    execute_js as stealth_js,
    desktop_action,
    open_app as desktop_open_app,
    get_open_windows as desktop_list_windows,
    press_key as desktop_press_key,
    desktop_screenshot,
)
# UI elements only work locally — import with fallback
try:
    from hands.desktop import get_ui_elements
except Exception:
    async def get_ui_elements(window_title=None):
        return {"ok": False, "error": "UI elements only available with local hands agent"}

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


# ============================================
# ACTIVE VISION — Screenshot + LLM Analysis
# ============================================

# Vision-capable models registered in LiteLLM
VISION_MODELS = {"gemini-flash", "gpt-4o", "claude-sonnet"}
DEFAULT_VISION_MODEL = "gemini-flash"  # Fast + cheap for quick screen reads


@function_tool()
async def analyze_screen(
    context: RunContext,
    question: str = "Describe what you see on screen in detail.",
    url: str = "",
    model: str = "",
) -> str:
    """Look at the screen or a webpage and analyze what you see using a vision model.
    This is your EYES — use this when you need to UNDERSTAND what's on screen, not just capture it.

    - question: What to analyze (e.g. "what app is open?", "read the error message", "describe the UI")
    - url: Optional URL to screenshot first. If empty, captures the current desktop screen.
    - model: Vision model to use. Options: "gemini-flash" (fast/cheap, default), "gpt-4o" (detailed),
      "claude-sonnet" (code-heavy screens). Leave empty for auto (gemini-flash).

    Use this when the user says "look at my screen", "what do you see", "read that error",
    "what's on the page", or any time you need to visually understand something."""
    try:
        # 1. Capture screenshot
        if url:
            result = await stealth_screenshot(url)
        else:
            result = await desktop_screenshot()

        if not result.get("ok"):
            return f"Failed to capture screen: {result.get('error', 'Unknown error')}"

        filepath = result.get("path", "")
        if not filepath or not Path(filepath).exists():
            return "Screenshot captured but file not found."

        # 2. Read + base64 encode the image
        image_bytes = Path(filepath).read_bytes()
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        # 3. Pick the vision model
        vision_model = model.strip().lower() if model.strip() else DEFAULT_VISION_MODEL
        if vision_model not in VISION_MODELS:
            return (
                f"Unknown vision model '{vision_model}'. "
                f"Available: {', '.join(sorted(VISION_MODELS))}"
            )

        # 4. Send to Brain with image for vision analysis
        payload = {
            "model": vision_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": question},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_b64}",
                            },
                        },
                    ],
                }
            ],
            "stream": False,
            "max_tokens": 1000,
        }

        response = requests.post(
            f"{BRAIN_URL}/v1/chat/completions",
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        analysis = data["choices"][0]["message"]["content"]

        title = result.get("title", "")
        source = f" ({title})" if title else " (desktop)"
        logging.info(
            f"[VISION] Analyzed{source} with {vision_model}: "
            f"{len(analysis)} chars"
        )
        return analysis

    except Exception as e:
        logging.error(f"analyze_screen error: {e}")
        return f"Vision analysis failed: {e}"


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
# COST ESTIMATION — The Differentiator
# No competitor tells you what a task will cost
# BEFORE running it. CHAMP does.
# ============================================

# Capability → cost mapping (mirrors AIOSCP bridge)
_CAPABILITY_COSTS = {
    # (min_cost, max_cost, avg_latency_ms, description)
    "browse_url":       (0.00,  0.00,  3000,  "Browse a webpage"),
    "google_search":    (0.00,  0.00,  4000,  "Google search"),
    "take_screenshot":  (0.00,  0.00,  2000,  "Take screenshot"),
    "analyze_screen":   (0.005, 0.05,  3000,  "Vision analysis"),
    "fill_web_form":    (0.00,  0.00,  5000,  "Fill web form"),
    "control_desktop":  (0.00,  0.00,  1000,  "Desktop control"),
    "run_code":         (0.00,  0.00,  2000,  "Run code"),
    "create_file":      (0.00,  0.00,  100,   "Create file"),
    "ask_brain":        (0.01,  0.10,  5000,  "Brain thinking"),
    "read_screen":      (0.00,  0.00,  500,   "Read UI elements"),
    "go_do":            (0.10,  2.00,  300000, "Self Mode (autonomous)"),
}

# Task keyword → likely capabilities mapping
_TASK_CAPABILITY_MAP = {
    # Research / browsing
    "search": ["google_search", "browse_url", "ask_brain"],
    "google": ["google_search"],
    "browse": ["browse_url"],
    "website": ["browse_url", "analyze_screen"],
    "look up": ["google_search", "browse_url"],
    "find": ["google_search", "browse_url"],
    "research": ["google_search", "browse_url", "ask_brain", "analyze_screen"],
    # Building / coding
    "build": ["ask_brain", "run_code", "create_file"],
    "create": ["ask_brain", "create_file"],
    "write": ["ask_brain", "create_file"],
    "script": ["ask_brain", "run_code", "create_file"],
    "code": ["ask_brain", "run_code"],
    "make": ["ask_brain", "run_code", "create_file"],
    # Desktop
    "open": ["control_desktop"],
    "click": ["control_desktop", "read_screen"],
    "desktop": ["control_desktop", "read_screen"],
    "app": ["control_desktop"],
    # Screen / vision
    "screen": ["analyze_screen"],
    "look at": ["analyze_screen"],
    "what's on": ["analyze_screen"],
    "see": ["analyze_screen"],
    "read": ["analyze_screen", "read_screen"],
    # Forms / automation
    "sign up": ["browse_url", "fill_web_form"],
    "fill": ["browse_url", "fill_web_form"],
    "log in": ["browse_url", "fill_web_form"],
    # Autonomous
    "scraper": ["go_do"],
    "pipeline": ["go_do"],
    "automate": ["go_do"],
    "autonomous": ["go_do"],
}


def _estimate_from_task(task_description: str) -> dict:
    """
    Analyze a task description and estimate cost + time.
    Returns dict with cost range, time estimate, and capabilities.
    """
    task_lower = task_description.lower()
    matched_caps = set()

    # Match keywords to capabilities
    for keyword, caps in _TASK_CAPABILITY_MAP.items():
        if keyword in task_lower:
            matched_caps.update(caps)

    # Default: at least brain thinking
    if not matched_caps:
        matched_caps.add("ask_brain")

    # Calculate totals
    min_cost = 0.0
    max_cost = 0.0
    total_latency = 0

    cap_details = []
    for cap_id in sorted(matched_caps):
        if cap_id in _CAPABILITY_COSTS:
            cmin, cmax, latency, desc = _CAPABILITY_COSTS[cap_id]
            min_cost += cmin
            max_cost += cmax
            total_latency += latency
            cap_details.append({
                "capability": cap_id,
                "description": desc,
                "cost": f"${cmin:.3f}-{cmax:.2f}" if cmin != cmax else f"${cmin:.2f}",
                "time": f"{latency/1000:.0f}s" if latency < 60000 else f"{latency/60000:.0f}min",
            })

    # Format time
    if total_latency < 60000:
        time_est = f"{total_latency/1000:.0f} seconds"
    elif total_latency < 3600000:
        time_est = f"{total_latency/60000:.0f} minutes"
    else:
        time_est = f"{total_latency/3600000:.1f} hours"

    # Format cost
    if min_cost == max_cost:
        cost_est = f"${min_cost:.2f}"
    else:
        cost_est = f"${min_cost:.2f}-{max_cost:.2f}"

    return {
        "estimated_cost": cost_est,
        "estimated_time": time_est,
        "capabilities_needed": len(matched_caps),
        "details": cap_details,
        "is_free": max_cost == 0.0,
    }


@function_tool()
async def estimate_task(
    context: RunContext,
    task: str,
) -> str:
    """Estimate the cost and time for a task BEFORE doing it.
    Use this when the user asks about cost, price, how long something takes,
    or before starting an expensive/complex task.
    Also use this proactively for Self Mode tasks — always estimate before go_do.

    Examples: "how much would it cost to...", "how long to...",
    "what would it take to...", "estimate this task"."""
    try:
        estimate = _estimate_from_task(task)

        if estimate["is_free"]:
            summary = (
                f"That task is free — no API costs. "
                f"Should take about {estimate['estimated_time']}. "
                f"Uses {estimate['capabilities_needed']} capabilities."
            )
        else:
            summary = (
                f"Estimated cost: {estimate['estimated_cost']}. "
                f"Estimated time: {estimate['estimated_time']}. "
                f"Uses {estimate['capabilities_needed']} capabilities."
            )

        # Add breakdown for complex tasks
        if len(estimate["details"]) > 2:
            summary += "\n\nBreakdown:"
            for d in estimate["details"]:
                summary += f"\n  - {d['description']}: {d['cost']} ({d['time']})"

        logging.info(
            f"[COST] Estimate for '{task[:50]}': "
            f"{estimate['estimated_cost']} / {estimate['estimated_time']}"
        )
        return summary
    except Exception as e:
        logging.error(f"estimate_task error: {e}")
        return f"Couldn't estimate: {e}"


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
        # Estimate cost BEFORE submitting
        estimate = _estimate_from_task(task)
        cost_note = f"Estimated cost: {estimate['estimated_cost']}."

        response = requests.post(
            f"{BRAIN_URL}/v1/self_mode/submit",
            json={"task": task},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        run_id = data.get("run_id", "unknown")
        _pending_run_ids.add(run_id)
        logging.info(
            f"Self Mode task submitted: {run_id} for '{task[:60]}' | "
            f"{cost_note}"
        )
        return (
            f"Got it -- I'm on it. Self Mode run started: {run_id}. "
            f"{cost_note} "
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


# ============================================
# RESEARCH — YouTube Transcript Extraction
# ============================================

@function_tool()
async def get_youtube_transcript(
    context: RunContext,
    video_url: str,
    summary: bool = True,
) -> str:
    """Pull the full transcript from any public YouTube video.
    Use this to research business frameworks, strategies, tutorials, or any video content.
    Pass a YouTube URL (or just the video ID).
    Set summary=True (default) to get a condensed version, or summary=False for the full raw transcript.
    Use this when: user says "watch this video", "what does this video say", "pull the transcript",
    or when researching a topic from YouTube content."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        # Extract video ID from URL
        video_id = video_url.strip()
        if "youtube.com" in video_id:
            if "v=" in video_id:
                video_id = video_id.split("v=")[1].split("&")[0]
            elif "/shorts/" in video_id:
                video_id = video_id.split("/shorts/")[1].split("?")[0]
        elif "youtu.be" in video_id:
            video_id = video_id.split("youtu.be/")[1].split("?")[0]

        ytt_api = YouTubeTranscriptApi()
        transcript = ytt_api.fetch(video_id)

        # Build full text with timestamps
        lines = []
        for entry in transcript.snippets:
            minutes = int(entry.start // 60)
            seconds = int(entry.start % 60)
            lines.append(f"[{minutes}:{seconds:02d}] {entry.text}")

        full_text = "\n".join(lines)
        total_duration = transcript.snippets[-1].start if transcript.snippets else 0
        duration_min = int(total_duration // 60)

        header = (
            f"YouTube Transcript ({len(transcript.snippets)} segments, "
            f"~{duration_min} min)\n"
            f"Video: https://www.youtube.com/watch?v={video_id}\n"
            f"{'=' * 50}\n\n"
        )

        if summary and len(full_text) > 4000:
            # Return first 2000 + last 2000 chars for context
            truncated = full_text[:2000] + "\n\n[... middle truncated ...]\n\n" + full_text[-2000:]
            return header + truncated + f"\n\nFull transcript: {len(full_text)} chars. Set summary=False for complete text."
        else:
            return header + full_text

    except ImportError:
        return "youtube-transcript-api not installed. Run: pip install youtube-transcript-api"
    except Exception as e:
        logging.error(f"get_youtube_transcript error: {e}")
        return f"Failed to get transcript: {e}"


# ============================================
# RESEARCH — Podcast Transcript Extraction
# ============================================

@function_tool()
async def get_podcast_transcript(
    context: RunContext,
    rss_url: str = "",
    audio_url: str = "",
    episode_index: int = 0,
) -> str:
    """Pull episode list from a podcast RSS feed, or get details about a specific episode.
    Pass an RSS feed URL to list episodes. Pass audio_url to get episode info.
    Use episode_index to select a specific episode from the feed (0 = latest).
    Use this when: user mentions a podcast, wants to research podcast content,
    or says "check this podcast"."""
    try:
        import podcastparser
        import urllib.request

        if rss_url:
            # Parse RSS feed and list episodes
            req = urllib.request.Request(rss_url, headers={"User-Agent": "Mozilla/5.0"})
            feed = podcastparser.parse(rss_url, urllib.request.urlopen(req, timeout=30))

            title = feed.get("title", "Unknown Podcast")
            episodes = feed.get("episodes", [])

            if not episodes:
                return f"Podcast '{title}' found but no episodes available."

            # List episodes
            header = f"Podcast: {title}\nTotal Episodes: {len(episodes)}\n{'=' * 50}\n\n"

            if episode_index < len(episodes):
                ep = episodes[episode_index]
                ep_detail = (
                    f"Episode {episode_index}: {ep.get('title', 'Untitled')}\n"
                    f"Published: {ep.get('published', 'Unknown')}\n"
                    f"Duration: {ep.get('total_time', 0) // 60} min\n"
                    f"Description: {ep.get('description', 'No description')[:500]}\n"
                )
                # Get audio URL
                for enc in ep.get("enclosures", []):
                    ep_detail += f"Audio URL: {enc.get('url', 'N/A')}\n"
                header += ep_detail + "\n"

            # List first 20 episodes
            listing = "Recent Episodes:\n"
            for i, ep in enumerate(episodes[:20]):
                dur = ep.get("total_time", 0) // 60
                listing += f"  [{i}] {ep.get('title', 'Untitled')} ({dur} min)\n"

            return header + listing

        return "Provide an rss_url to list podcast episodes."

    except ImportError:
        return "podcastparser not installed. Run: pip install podcastparser"
    except Exception as e:
        logging.error(f"get_podcast_transcript error: {e}")
        return f"Failed to get podcast info: {e}"


# ============================================
# RESEARCH — Blog / Web Page Content Extraction
# ============================================

@function_tool()
async def get_web_content(
    context: RunContext,
    url: str,
    summary: bool = True,
) -> str:
    """Pull and extract the main text content from any web page, blog post, or article.
    Use this to research blog posts, Substack articles, documentation, competitor pages,
    or any public web content.
    Pass a URL and get the clean text content back.
    Use this when: user says "read this article", "check this blog", "what does this page say",
    or when researching content from websites."""
    try:
        from bs4 import BeautifulSoup
        import urllib.request

        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        response = urllib.request.urlopen(req, timeout=30)
        html = response.read().decode("utf-8", errors="ignore")

        soup = BeautifulSoup(html, "html.parser")

        # Remove script, style, nav, footer, header elements
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
            tag.decompose()

        # Extract title
        title = soup.title.string if soup.title else "Untitled"

        # Try to find main content area
        main = soup.find("main") or soup.find("article") or soup.find("div", class_="content") or soup.body
        if not main:
            main = soup

        # Extract text
        text = main.get_text(separator="\n", strip=True)

        # Clean up excessive newlines
        import re
        text = re.sub(r"\n{3,}", "\n\n", text)

        header = (
            f"Web Content Extraction\n"
            f"URL: {url}\n"
            f"Title: {title}\n"
            f"Length: {len(text)} chars\n"
            f"{'=' * 50}\n\n"
        )

        if summary and len(text) > 6000:
            truncated = text[:3000] + "\n\n[... middle truncated ...]\n\n" + text[-3000:]
            return header + truncated + f"\n\nFull content: {len(text)} chars. Set summary=False for complete text."
        else:
            return header + text

    except Exception as e:
        logging.error(f"get_web_content error: {e}")
        return f"Failed to extract web content: {e}"


# ============================================
# RESEARCH — PDF / Document Text Extraction
# ============================================

@function_tool()
async def get_pdf_content(
    context: RunContext,
    file_path: str,
    start_page: int = 0,
    end_page: int = 0,
) -> str:
    """Extract text content from a PDF file.
    Pass a file path to a PDF. Optionally specify start_page and end_page (0-indexed).
    If end_page is 0, extracts all pages.
    Use this when: user says "read this PDF", "extract from this document",
    "what does this book say", or when processing business documents, SOPs, or books."""
    try:
        import pdfplumber

        with pdfplumber.open(file_path) as pdf:
            total_pages = len(pdf.pages)

            if end_page == 0 or end_page > total_pages:
                end_page = total_pages

            pages_text = []
            for i in range(start_page, end_page):
                page = pdf.pages[i]
                text = page.extract_text()
                if text:
                    pages_text.append(f"--- Page {i + 1} ---\n{text}")

            full_text = "\n\n".join(pages_text)

            header = (
                f"PDF Content Extraction\n"
                f"File: {file_path}\n"
                f"Total Pages: {total_pages}\n"
                f"Extracted: Pages {start_page + 1}-{end_page}\n"
                f"Length: {len(full_text)} chars\n"
                f"{'=' * 50}\n\n"
            )

            return header + full_text

    except ImportError:
        return "pdfplumber not installed. Run: pip install pdfplumber"
    except FileNotFoundError:
        return f"File not found: {file_path}"
    except Exception as e:
        logging.error(f"get_pdf_content error: {e}")
        return f"Failed to extract PDF content: {e}"


# ============================================
# FILE SYSTEM — Read, Edit, List, Search
# The eyes and hands for code and documents.
# ============================================

@function_tool()
async def read_file(
    context: RunContext,
    path: str,
    start_line: int = 0,
    end_line: int = 0,
) -> str:
    """Read the contents of any file on the machine.
    Use this to read source code, config files, logs, documents, or any text file.
    Optionally specify start_line and end_line to read a specific section (1-indexed).
    If end_line is 0, reads the entire file.

    Use this when: you need to understand code before editing it, read configs,
    check logs, review files, or inspect your own source code for self-correction."""
    try:
        p = Path(path).resolve()
        if not p.exists():
            return f"File not found: {path}"
        if not p.is_file():
            return f"Not a file: {path}"
        if p.stat().st_size > 5 * 1024 * 1024:
            return f"File too large ({p.stat().st_size / 1024 / 1024:.1f}MB). Use start_line/end_line to read sections."

        text = p.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()

        if start_line > 0 or end_line > 0:
            s = max(start_line - 1, 0)
            e = end_line if end_line > 0 else len(lines)
            selected = lines[s:e]
            numbered = [f"{i + s + 1:4d} | {line}" for i, line in enumerate(selected)]
            return f"File: {path} (lines {s + 1}-{min(e, len(lines))} of {len(lines)})\n\n" + "\n".join(numbered)
        else:
            numbered = [f"{i + 1:4d} | {line}" for i, line in enumerate(lines)]
            return f"File: {path} ({len(lines)} lines)\n\n" + "\n".join(numbered)

    except Exception as e:
        logging.error(f"read_file error: {e}")
        return f"Error reading file: {e}"


@function_tool()
async def edit_file(
    context: RunContext,
    path: str,
    old_text: str,
    new_text: str,
) -> str:
    """Make a surgical edit to a file — find old_text and replace it with new_text.
    ALWAYS read_file first to see the current content before editing.
    The old_text must match exactly (including whitespace/indentation).

    Use this when: fixing bugs, updating code, modifying configs, correcting your own source code.
    For creating new files, use create_file instead."""
    try:
        p = Path(path).resolve()
        if not p.exists():
            return f"File not found: {path}"

        content = p.read_text(encoding="utf-8")

        if old_text not in content:
            # Try to help find a near-match
            lines = content.splitlines()
            first_line = old_text.strip().splitlines()[0] if old_text.strip() else ""
            near = [i + 1 for i, l in enumerate(lines) if first_line and first_line.strip() in l]
            hint = f" Possible near-matches at lines: {near[:5]}" if near else ""
            return f"old_text not found in {path}.{hint} Use read_file to check exact content."

        count = content.count(old_text)
        if count > 1:
            return f"old_text matches {count} locations in {path}. Make it more specific (include surrounding lines)."

        new_content = content.replace(old_text, new_text, 1)
        p.write_text(new_content, encoding="utf-8")

        logging.info(f"edit_file: {path} ({len(old_text)} chars -> {len(new_text)} chars)")
        return f"Edited {path} successfully. Changed {len(old_text)} chars to {len(new_text)} chars."

    except Exception as e:
        logging.error(f"edit_file error: {e}")
        return f"Error editing file: {e}"


@function_tool()
async def list_directory(
    context: RunContext,
    path: str = ".",
    pattern: str = "*",
    recursive: bool = False,
) -> str:
    """List files and directories at the given path.
    Optionally filter with a glob pattern (e.g. '*.py', '*.md').
    Set recursive=True to search subdirectories.

    Use this when: navigating a project, finding files, exploring codebases,
    checking what files exist before reading/editing."""
    try:
        p = Path(path).resolve()
        if not p.exists():
            return f"Path not found: {path}"
        if not p.is_dir():
            return f"Not a directory: {path}"

        if recursive:
            items = sorted(p.rglob(pattern))
        else:
            items = sorted(p.glob(pattern))

        entries = []
        for item in items[:200]:  # Cap at 200 entries
            rel = item.relative_to(p)
            if item.is_dir():
                entries.append(f"  [DIR]  {rel}/")
            else:
                size = item.stat().st_size
                if size < 1024:
                    size_str = f"{size}B"
                elif size < 1024 * 1024:
                    size_str = f"{size / 1024:.0f}KB"
                else:
                    size_str = f"{size / 1024 / 1024:.1f}MB"
                entries.append(f"  {size_str:>8s}  {rel}")

        total = len(list(p.rglob(pattern) if recursive else p.glob(pattern)))
        header = f"Directory: {p}\nPattern: {pattern} | Showing {len(entries)} of {total}\n"
        return header + "\n".join(entries)

    except Exception as e:
        logging.error(f"list_directory error: {e}")
        return f"Error listing directory: {e}"


@function_tool()
async def search_files(
    context: RunContext,
    query: str,
    path: str = ".",
    file_pattern: str = "*",
    max_results: int = 30,
) -> str:
    """Search for text content across files — like grep.
    Finds all lines matching the query string in files under the given path.
    Optionally filter by file pattern (e.g. '*.py').

    Use this when: looking for where something is defined, finding usages,
    searching for patterns, debugging, or understanding codebases."""
    try:
        p = Path(path).resolve()
        if not p.exists():
            return f"Path not found: {path}"

        results = []
        files_searched = 0

        for filepath in p.rglob(file_pattern):
            if not filepath.is_file():
                continue
            if filepath.stat().st_size > 2 * 1024 * 1024:
                continue  # Skip large files
            # Skip binary and hidden files
            if any(part.startswith('.') for part in filepath.parts):
                continue
            if filepath.suffix in ('.pyc', '.pyo', '.exe', '.dll', '.so', '.png', '.jpg', '.gif', '.zip', '.gz'):
                continue

            files_searched += 1
            try:
                text = filepath.read_text(encoding="utf-8", errors="ignore")
                for i, line in enumerate(text.splitlines(), 1):
                    if query.lower() in line.lower():
                        rel = filepath.relative_to(p)
                        results.append(f"{rel}:{i}: {line.strip()[:150]}")
                        if len(results) >= max_results:
                            break
            except Exception:
                continue

            if len(results) >= max_results:
                break

        header = f"Search: '{query}' in {path} ({file_pattern})\nFiles searched: {files_searched} | Matches: {len(results)}\n{'=' * 50}\n"
        if results:
            return header + "\n".join(results)
        else:
            return header + "No matches found."

    except Exception as e:
        logging.error(f"search_files error: {e}")
        return f"Error searching files: {e}"


# ============================================
# SHELL — Run Any Terminal Command
# Full access to the system. No prison.
# ============================================

@function_tool()
async def run_shell(
    context: RunContext,
    command: str,
    working_dir: str = "",
    timeout_seconds: int = 120,
) -> str:
    """Execute any shell/terminal command and return the output.
    Use this for: installing packages, running builds, checking system info,
    managing processes, running scripts, or anything you'd type in a terminal.

    Examples: 'pip install flask', 'npm run build', 'git status', 'ls -la',
    'docker ps', 'netstat -tlnp', 'python test.py'

    Set working_dir to run from a specific directory.
    Default timeout is 120 seconds."""
    import subprocess

    # Safety: block obviously destructive commands
    blocked = ["rm -rf /", "format c:", "del /f /s /q c:\\"]
    if any(b in command.lower() for b in blocked):
        return "Blocked: that command could destroy the system. Be more specific about what to delete."

    try:
        cwd = working_dir if working_dir else None
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            cwd=cwd,
        )

        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += ("\n--- STDERR ---\n" + result.stderr) if result.stdout else result.stderr

        if not output.strip():
            output = "(no output)"

        # Cap output size
        if len(output) > 10000:
            output = output[:5000] + "\n\n[... truncated ...]\n\n" + output[-5000:]

        status = "OK" if result.returncode == 0 else f"EXIT CODE {result.returncode}"
        logging.info(f"run_shell: '{command[:60]}' -> {status}")
        return f"[{status}]\n{output}"

    except subprocess.TimeoutExpired:
        return f"Command timed out after {timeout_seconds}s: {command}"
    except Exception as e:
        logging.error(f"run_shell error: {e}")
        return f"Shell error: {e}"


# ============================================
# GIT — Version Control
# Commit, push, pull, branch, diff.
# ============================================

@function_tool()
async def git_command(
    context: RunContext,
    operation: str,
    args: str = "",
    working_dir: str = "",
) -> str:
    """Run git operations on any repository.
    Operations: status, diff, log, add, commit, push, pull, branch, checkout, stash, remote

    Examples:
    - git_command("status") — see what's changed
    - git_command("diff") — see exact changes
    - git_command("log", "--oneline -10") — last 10 commits
    - git_command("add", ".") — stage all changes
    - git_command("commit", "-m 'fix: browser timeout'") — commit
    - git_command("push") — push to remote
    - git_command("pull") — pull latest
    - git_command("branch", "feature/new-tool") — create branch
    - git_command("checkout", "main") — switch branch

    Use this for: self-correction (commit fixes), deploying changes,
    managing code versions, collaborating on repos."""
    import subprocess

    # Allowed operations
    allowed = {"status", "diff", "log", "add", "commit", "push", "pull",
               "branch", "checkout", "stash", "remote", "fetch", "merge",
               "rebase", "reset", "show", "tag", "clone", "init"}

    op = operation.strip().lower()
    if op not in allowed:
        return f"Git operation '{op}' not recognized. Allowed: {', '.join(sorted(allowed))}"

    # Build command
    cmd = f"git {op}"
    if args:
        cmd += f" {args}"

    try:
        cwd = working_dir if working_dir else None
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=cwd,
        )

        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            # Git often puts info in stderr (like push progress)
            output += ("\n" + result.stderr) if result.stdout else result.stderr

        if not output.strip():
            output = "(no output — command succeeded)"

        if len(output) > 10000:
            output = output[:5000] + "\n\n[... truncated ...]\n\n" + output[-5000:]

        status = "OK" if result.returncode == 0 else f"ERROR (exit {result.returncode})"
        logging.info(f"git {op}: {status}")
        return f"[git {op}: {status}]\n{output}"

    except subprocess.TimeoutExpired:
        return f"Git command timed out: {cmd}"
    except Exception as e:
        logging.error(f"git_command error: {e}")
        return f"Git error: {e}"


# ============================================
# CLIPBOARD — Read/Write System Clipboard
# Share data between apps seamlessly.
# ============================================

@function_tool()
async def clipboard(
    context: RunContext,
    action: str = "read",
    text: str = "",
) -> str:
    """Read from or write to the system clipboard.
    action='read' — get whatever is currently on the clipboard.
    action='write' — put text onto the clipboard so you (or the user) can paste it elsewhere.

    Use this when: sharing data between apps, grabbing copied text,
    putting results somewhere the user can paste."""
    try:
        import subprocess

        if action == "read":
            # Windows clipboard read
            result = subprocess.run(
                ["powershell", "-command", "Get-Clipboard"],
                capture_output=True, text=True, timeout=5,
            )
            content = result.stdout.strip()
            if content:
                return f"Clipboard contents ({len(content)} chars):\n{content[:5000]}"
            else:
                return "Clipboard is empty."

        elif action == "write":
            if not text:
                return "Nothing to write — provide text."
            # Windows clipboard write
            process = subprocess.Popen(
                ["powershell", "-command", "Set-Clipboard", "-Value", text[:10000]],
                stdin=subprocess.PIPE, timeout=5,
            )
            process.wait(timeout=5)
            return f"Copied to clipboard ({len(text)} chars). Ready to paste."

        else:
            return "action must be 'read' or 'write'"

    except Exception as e:
        logging.error(f"clipboard error: {e}")
        return f"Clipboard error: {e}"


# ============================================
# TASKS & NOTES — Persistent Productivity
# Survives across sessions via Brain API.
# ============================================

@function_tool()
async def manage_tasks(
    context: RunContext,
    action: str,
    task: str = "",
    task_id: str = "",
    priority: str = "medium",
) -> str:
    """Manage a persistent task/TODO list that survives across sessions.
    Actions:
    - 'add' — add a new task (provide task text and optional priority: high/medium/low)
    - 'list' — show all open tasks
    - 'done' — mark a task as complete (provide task_id)
    - 'remove' — delete a task (provide task_id)

    Use this when: user says "remind me to", "add to my list", "what's on my plate",
    "mark X as done", or when tracking work items across sessions."""
    try:
        response = requests.post(
            f"{BRAIN_URL}/v1/tasks",
            json={"action": action, "task": task, "task_id": task_id, "priority": priority},
            timeout=10,
        )
        if response.status_code == 404:
            # Tasks endpoint not yet deployed — use local fallback
            return await _local_task_fallback(action, task, task_id, priority)
        response.raise_for_status()
        return response.json().get("result", "Done.")
    except requests.exceptions.ConnectionError:
        return await _local_task_fallback(action, task, task_id, priority)
    except Exception as e:
        logging.error(f"manage_tasks error: {e}")
        return f"Task error: {e}"


# Local task fallback (file-based when Brain doesn't have the endpoint yet)
_TASKS_FILE = Path(__file__).resolve().parent / "output" / "tasks.json"


async def _local_task_fallback(action: str, task: str, task_id: str, priority: str) -> str:
    """File-based task management as fallback."""
    import uuid

    _TASKS_FILE.parent.mkdir(exist_ok=True)
    tasks = []
    if _TASKS_FILE.exists():
        try:
            tasks = _json.loads(_TASKS_FILE.read_text())
        except Exception:
            tasks = []

    if action == "add":
        if not task:
            return "Provide a task description."
        new_task = {
            "id": f"T-{uuid.uuid4().hex[:6]}",
            "task": task,
            "priority": priority,
            "status": "open",
            "created": datetime.now().isoformat() if 'datetime' in dir() else "now",
        }
        tasks.append(new_task)
        _TASKS_FILE.write_text(_json.dumps(tasks, indent=2))
        return f"Added: [{new_task['id']}] {task} (priority: {priority})"

    elif action == "list":
        open_tasks = [t for t in tasks if t.get("status") == "open"]
        if not open_tasks:
            return "No open tasks. All clear."
        lines = []
        for t in open_tasks:
            p = t.get("priority", "medium").upper()
            lines.append(f"  [{t['id']}] [{p}] {t['task']}")
        return f"Open Tasks ({len(open_tasks)}):\n" + "\n".join(lines)

    elif action == "done":
        for t in tasks:
            if t.get("id") == task_id:
                t["status"] = "done"
                _TASKS_FILE.write_text(_json.dumps(tasks, indent=2))
                return f"Marked done: {t['task']}"
        return f"Task {task_id} not found."

    elif action == "remove":
        tasks = [t for t in tasks if t.get("id") != task_id]
        _TASKS_FILE.write_text(_json.dumps(tasks, indent=2))
        return f"Removed task {task_id}."

    return f"Unknown action: {action}. Use add/list/done/remove."


@function_tool()
async def take_notes(
    context: RunContext,
    action: str,
    content: str = "",
    topic: str = "general",
) -> str:
    """Persistent notepad — save and retrieve notes across sessions.
    Actions:
    - 'save' — save a note (provide content and optional topic)
    - 'read' — read all notes (optionally filter by topic)
    - 'clear' — clear notes for a topic

    Use this when: saving research findings, storing plans, keeping track of ideas,
    recording meeting notes, or when you need to remember something for later."""
    try:
        notes_dir = Path(__file__).resolve().parent / "output" / "notes"
        notes_dir.mkdir(parents=True, exist_ok=True)

        safe_topic = "".join(c for c in topic if c.isalnum() or c in "-_").lower() or "general"
        notes_file = notes_dir / f"{safe_topic}.md"

        if action == "save":
            if not content:
                return "Provide content to save."
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            entry = f"\n## [{timestamp}]\n{content}\n"

            with open(notes_file, "a", encoding="utf-8") as f:
                f.write(entry)

            logging.info(f"Note saved to {safe_topic} ({len(content)} chars)")
            return f"Note saved to '{safe_topic}' ({len(content)} chars)."

        elif action == "read":
            if notes_file.exists():
                text = notes_file.read_text(encoding="utf-8")
                return f"Notes [{safe_topic}] ({len(text)} chars):\n\n{text[-8000:]}"
            else:
                # List available topics
                available = [f.stem for f in notes_dir.glob("*.md")]
                if available:
                    return f"No notes for '{safe_topic}'. Available topics: {', '.join(available)}"
                return "No notes saved yet."

        elif action == "clear":
            if notes_file.exists():
                notes_file.unlink()
                return f"Cleared all notes for '{safe_topic}'."
            return f"No notes for '{safe_topic}'."

        return f"Unknown action: {action}. Use save/read/clear."

    except Exception as e:
        logging.error(f"take_notes error: {e}")
        return f"Notes error: {e}"


# ============================================
# SELF-CORRECTION — Fix Your Own Code
# Read source → understand → edit → test → deploy
# ============================================

@function_tool()
async def self_correct(
    context: RunContext,
    action: str,
    description: str = "",
) -> str:
    """Self-correction workflow — inspect and fix your own source code.
    Actions:
    - 'diagnose' — read your own source files related to the issue, describe what you see
    - 'fix' — apply a fix (use read_file + edit_file for the actual edits, then call this with action='fix' to log it)
    - 'test' — run your gate tests to verify the fix
    - 'deploy' — commit and push the fix (triggers Railway auto-deploy)

    This is your self-improvement loop. When something breaks:
    1. self_correct('diagnose', 'the browse tool is timing out')
    2. read_file the relevant source
    3. edit_file to fix it
    4. self_correct('test') to verify
    5. self_correct('deploy', 'fix: browser timeout increased') to ship it

    Use this when: user reports a bug, something fails, or you identify an issue in your own behavior."""
    import subprocess

    champ_root = str(Path(__file__).resolve().parent)

    if action == "diagnose":
        # List all source files and their recent changes
        try:
            result = subprocess.run(
                "git diff --stat HEAD~3",
                shell=True, capture_output=True, text=True,
                timeout=10, cwd=champ_root,
            )
            recent_changes = result.stdout or "No recent git changes detected."

            # Get list of core source files
            core_files = []
            for pattern in ["*.py", "brain/*.py", "hands/*.py", "mind/*.py",
                           "operators/*.py", "self_mode/*.py", "ears/*.py"]:
                for f in Path(champ_root).glob(pattern):
                    core_files.append(str(f.relative_to(champ_root)))

            return (
                f"Self-Correction Diagnosis\n"
                f"Issue: {description}\n"
                f"{'=' * 50}\n"
                f"CHAMP root: {champ_root}\n"
                f"Core files ({len(core_files)}):\n"
                + "\n".join(f"  {f}" for f in sorted(core_files))
                + f"\n\nRecent changes:\n{recent_changes}\n"
                f"\nNext: use read_file to inspect the relevant source, "
                f"then edit_file to fix it."
            )
        except Exception as e:
            return f"Diagnosis error: {e}"

    elif action == "test":
        # Run gate tests
        try:
            result = subprocess.run(
                "python -c \"import tools; print('tools.py: OK')\" && "
                "python -c \"from brain.main import app; print('brain: OK')\" && "
                "python -c \"from hands.router import get_hands_status; print('router:', get_hands_status())\"",
                shell=True, capture_output=True, text=True,
                timeout=30, cwd=champ_root,
            )
            output = result.stdout + (result.stderr if result.returncode != 0 else "")
            status = "ALL TESTS PASSED" if result.returncode == 0 else "TESTS FAILED"
            return f"[{status}]\n{output}"
        except Exception as e:
            return f"Test error: {e}"

    elif action == "deploy":
        # Git add + commit + push
        if not description:
            return "Provide a commit message in the description."
        try:
            cmds = [
                "git add -A",
                f'git commit -m "{description}"',
                "git push",
            ]
            outputs = []
            for cmd in cmds:
                result = subprocess.run(
                    cmd, shell=True, capture_output=True, text=True,
                    timeout=30, cwd=champ_root,
                )
                outputs.append(f"$ {cmd}\n{result.stdout}{result.stderr}")
                if result.returncode != 0 and "push" not in cmd:
                    return f"Deploy failed at: {cmd}\n{''.join(outputs)}"

            return f"Deployed!\n{''.join(outputs)}"
        except Exception as e:
            return f"Deploy error: {e}"

    elif action == "fix":
        # Just log the fix (actual editing done via edit_file)
        logging.info(f"[SELF-CORRECT] Fix applied: {description}")
        return f"Fix logged: {description}. Run self_correct('test') to verify, then self_correct('deploy', 'your commit message') to ship."

    return f"Unknown action: {action}. Use diagnose/fix/test/deploy."

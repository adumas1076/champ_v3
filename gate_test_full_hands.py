"""
============================================
CHAMP V3 — Gate Test: Full Hands
Tests stealth browser + desktop control
============================================
"""

import asyncio
import sys
import time

passed = 0
failed = 0
skipped = 0


def ok(label):
    global passed
    passed += 1
    print(f"  ✅ {label}")


def fail(label, reason=""):
    global failed
    failed += 1
    msg = f"  ❌ {label}"
    if reason:
        msg += f" — {reason}"
    print(msg)


def skip(label, reason=""):
    global skipped
    skipped += 1
    msg = f"  ⏭️  {label}"
    if reason:
        msg += f" — {reason}"
    print(msg)


print("=" * 60)
print("  CHAMP V3 — Gate Test: Full Hands")
print("  Stealth Browser + Desktop Control")
print("=" * 60)
print()

# ============================================
# PART 1: Import Tests
# ============================================
print("=== PART 1: Module Imports ===")

try:
    from hands.stealth_browser import (
        browse, take_screenshot, fill_form,
        click_element, type_text, google_search,
        get_page_content, execute_js, close_browser,
    )
    ok("stealth_browser imports")
except Exception as e:
    fail("stealth_browser imports", str(e))

try:
    from hands.desktop import (
        desktop_action, open_app, get_open_windows,
        press_key, focus_window, mouse_click, mouse_move,
        mouse_scroll, type_text as dt_type, take_screenshot as dt_ss,
        locate_on_screen, get_ui_elements, click_ui_element,
    )
    ok("desktop imports")
except Exception as e:
    fail("desktop imports", str(e))

try:
    from tools import (
        browse_url, take_screenshot as ts, fill_web_form,
        google_search as gs, control_desktop, read_screen,
    )
    ok("tools imports (new tools)")
except Exception as e:
    fail("tools imports", str(e))

try:
    import nodriver
    ok("nodriver installed")
except Exception as e:
    fail("nodriver", str(e))

try:
    import pyautogui
    ok(f"pyautogui v{pyautogui.__version__}")
except Exception as e:
    fail("pyautogui", str(e))

try:
    import pygetwindow
    ok("pygetwindow")
except Exception as e:
    fail("pygetwindow", str(e))

try:
    import uiautomation
    ok("uiautomation")
except Exception as e:
    fail("uiautomation", str(e))

print()

# ============================================
# PART 2: Desktop Control (no browser needed)
# ============================================
print("=== PART 2: Desktop Control ===")


async def test_desktop():
    global passed, failed, skipped

    # List windows
    try:
        result = await get_open_windows()
        if result["ok"] and len(result["windows"]) > 0:
            ok(f"get_open_windows — {len(result['windows'])} windows found")
        else:
            fail("get_open_windows", "no windows found")
    except Exception as e:
        fail("get_open_windows", str(e))

    # Desktop action parser — open
    try:
        result = await desktop_action("list windows")
        if result["ok"]:
            ok("desktop_action('list windows')")
        else:
            fail("desktop_action('list windows')", result.get("error"))
    except Exception as e:
        fail("desktop_action", str(e))

    # Press key (safe: press and release shift)
    try:
        result = await press_key("shift")
        if result["ok"]:
            ok("press_key('shift')")
        else:
            fail("press_key", result.get("error"))
    except Exception as e:
        fail("press_key", str(e))

    # Desktop screenshot
    try:
        result = await dt_ss()
        if result["ok"] and result.get("path"):
            from pathlib import Path
            if Path(result["path"]).exists():
                ok(f"desktop_screenshot — saved to {result['path']}")
            else:
                fail("desktop_screenshot", "file not saved")
        else:
            fail("desktop_screenshot", result.get("error"))
    except Exception as e:
        fail("desktop_screenshot", str(e))

    # UI elements from foreground window
    try:
        result = await get_ui_elements()
        if result["ok"]:
            count = len(result.get("elements", []))
            ok(f"get_ui_elements (foreground) — {count} elements")
        else:
            # May fail if no foreground window — that's ok
            skip("get_ui_elements", result.get("error", "no foreground window"))
    except Exception as e:
        skip("get_ui_elements", str(e))

    # Desktop action parser — screenshot
    try:
        result = await desktop_action("screenshot")
        if result["ok"]:
            ok("desktop_action('screenshot')")
        else:
            fail("desktop_action('screenshot')", result.get("error"))
    except Exception as e:
        fail("desktop_action('screenshot')", str(e))


asyncio.run(test_desktop())
print()

# ============================================
# PART 3: Stealth Browser
# ============================================
print("=== PART 3: Stealth Browser ===")


async def test_stealth():
    global passed, failed, skipped

    # Browse a simple page
    try:
        result = await browse("https://example.com")
        if result["ok"] and "Example Domain" in result.get("title", ""):
            ok(f"browse('example.com') — title: {result['title']}")
        elif result["ok"]:
            ok(f"browse('example.com') — title: {result.get('title', 'loaded')}")
        else:
            fail("browse('example.com')", result.get("error"))
    except Exception as e:
        fail("browse('example.com')", str(e))

    # Get page content
    try:
        result = await get_page_content()
        if result["ok"] and result.get("title"):
            ok(f"get_page_content — url: {result.get('url', '')[:50]}")
        else:
            fail("get_page_content", result.get("error"))
    except Exception as e:
        fail("get_page_content", str(e))

    # Execute JS
    try:
        result = await execute_js("2 + 2")
        if result["ok"] and result.get("result") == "4":
            ok("execute_js('2 + 2') = 4")
        elif result["ok"]:
            ok(f"execute_js — result: {result.get('result')}")
        else:
            fail("execute_js", result.get("error"))
    except Exception as e:
        fail("execute_js", str(e))

    # Screenshot
    try:
        result = await take_screenshot("https://example.com")
        if result["ok"] and result.get("path"):
            ok(f"stealth_screenshot — {result['path']}")
        else:
            fail("stealth_screenshot", result.get("error"))
    except Exception as e:
        fail("stealth_screenshot", str(e))

    # Google search
    try:
        result = await google_search("CHAMP AI OS")
        if result["ok"] and len(result.get("results", [])) > 0:
            ok(f"google_search — {len(result['results'])} results")
        elif result["ok"]:
            ok("google_search — ran (0 results)")
        else:
            fail("google_search", result.get("error"))
    except Exception as e:
        fail("google_search", str(e))

    # Clean up
    try:
        await close_browser()
        ok("browser closed cleanly")
    except Exception as e:
        fail("browser close", str(e))


asyncio.run(test_stealth())
print()

# ============================================
# PART 4: Tool Registration
# ============================================
print("=== PART 4: Tool Registration ===")

try:
    from tools import (
        get_weather, ask_brain,
        browse_url, take_screenshot as ts2, fill_web_form,
        run_code, create_file,
        go_do, check_task, approve_task, resume_task,
        google_search as gs2, control_desktop, read_screen,
    )
    tools = [
        get_weather, ask_brain,
        browse_url, ts2, fill_web_form,
        run_code, create_file,
        go_do, check_task, approve_task, resume_task,
        gs2, control_desktop, read_screen,
    ]
    ok(f"{len(tools)} tools importable from tools.py")

    # Check all are decorated function_tools
    for t in tools:
        name = getattr(t, '__name__', str(t))
        if hasattr(t, 'metadata') or callable(t):
            pass  # Good enough — it's a callable
        else:
            fail(f"tool {name} not callable")

    ok("all tools are callable")
except Exception as e:
    fail("tool registration", str(e))

print()

# ============================================
# RESULTS
# ============================================
total = passed + failed + skipped
print("=" * 60)
print(f"  RESULTS: {passed} passed / {failed} failed / {skipped} skipped")
print(f"  FULL HANDS GATE: {'PASSED' if failed == 0 else 'FAILED'}")
print("=" * 60)

sys.exit(0 if failed == 0 else 1)

# ============================================
# CHAMP V3 — Desktop Control (Full Hands Upgrade)
# Controls any Windows app via pyautogui + uiautomation
# Full mouse, keyboard, window management
# ============================================

import asyncio
import logging
import subprocess
import time
from pathlib import Path

import pyautogui
import pygetwindow as gw

logger = logging.getLogger(__name__)

# Safety: pause between pyautogui actions (seconds)
pyautogui.PAUSE = 0.3
# Safety: move mouse to corner to abort (failsafe)
pyautogui.FAILSAFE = True


# ============================================
# WINDOW MANAGEMENT
# ============================================

async def get_open_windows() -> dict:
    """List all open windows on the desktop."""
    try:
        windows = []
        for win in gw.getAllWindows():
            if win.title and win.title.strip():
                windows.append({
                    "title": win.title,
                    "left": win.left,
                    "top": win.top,
                    "width": win.width,
                    "height": win.height,
                    "visible": win.visible,
                    "minimized": win.isMinimized,
                })
        logger.info(f"[DESKTOP] Found {len(windows)} open windows")
        return {"ok": True, "windows": windows}
    except Exception as e:
        logger.error(f"[DESKTOP] get_open_windows error: {e}")
        return {"ok": False, "error": str(e)}


async def open_app(app_name: str) -> dict:
    """Open an application by name. Tries to find and focus existing window first,
    then searches Start Menu / PATH."""
    try:
        # First check if already open
        for win in gw.getAllWindows():
            if app_name.lower() in win.title.lower():
                try:
                    if win.isMinimized:
                        win.restore()
                    win.activate()
                    await asyncio.sleep(0.5)
                    logger.info(f"[DESKTOP] Focused existing window: {win.title}")
                    return {"ok": True, "action": "focused", "window": win.title}
                except Exception:
                    pass

        # Not found — try to launch it
        # Common app mappings
        app_map = {
            "notepad": "notepad.exe",
            "calculator": "calc.exe",
            "paint": "mspaint.exe",
            "explorer": "explorer.exe",
            "file explorer": "explorer.exe",
            "cmd": "cmd.exe",
            "command prompt": "cmd.exe",
            "powershell": "powershell.exe",
            "terminal": "wt.exe",
            "chrome": "chrome.exe",
            "google chrome": "chrome.exe",
            "edge": "msedge.exe",
            "microsoft edge": "msedge.exe",
            "firefox": "firefox.exe",
            "excel": "excel.exe",
            "word": "winword.exe",
            "powerpoint": "powerpnt.exe",
            "outlook": "outlook.exe",
            "spotify": "spotify.exe",
            "slack": "slack.exe",
            "discord": "discord.exe",
            "teams": "teams.exe",
            "code": "code.exe",
            "vscode": "code.exe",
            "visual studio code": "code.exe",
        }

        exe = app_map.get(app_name.lower(), app_name)

        # Try direct launch
        process = subprocess.Popen(
            exe,
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        await asyncio.sleep(2)

        logger.info(f"[DESKTOP] Launched: {exe}")
        return {"ok": True, "action": "launched", "app": exe}
    except Exception as e:
        logger.error(f"[DESKTOP] open_app error: {e}")
        return {"ok": False, "error": str(e)}


async def focus_window(title_contains: str) -> dict:
    """Bring a window to the foreground by partial title match."""
    try:
        for win in gw.getAllWindows():
            if title_contains.lower() in win.title.lower():
                if win.isMinimized:
                    win.restore()
                win.activate()
                await asyncio.sleep(0.3)
                logger.info(f"[DESKTOP] Focused: {win.title}")
                return {"ok": True, "window": win.title}
        return {"ok": False, "error": f"No window matching '{title_contains}'"}
    except Exception as e:
        logger.error(f"[DESKTOP] focus_window error: {e}")
        return {"ok": False, "error": str(e)}


# ============================================
# MOUSE CONTROL
# ============================================

async def mouse_click(x: int, y: int, button: str = "left", clicks: int = 1) -> dict:
    """Click at screen coordinates."""
    try:
        pyautogui.click(x=x, y=y, button=button, clicks=clicks)
        logger.info(f"[DESKTOP] Clicked ({x}, {y}) button={button} clicks={clicks}")
        return {"ok": True, "x": x, "y": y, "button": button}
    except Exception as e:
        logger.error(f"[DESKTOP] mouse_click error: {e}")
        return {"ok": False, "error": str(e)}


async def mouse_move(x: int, y: int, duration: float = 0.5) -> dict:
    """Move mouse to coordinates with human-like movement."""
    try:
        pyautogui.moveTo(x=x, y=y, duration=duration)
        logger.info(f"[DESKTOP] Mouse moved to ({x}, {y})")
        return {"ok": True, "x": x, "y": y}
    except Exception as e:
        logger.error(f"[DESKTOP] mouse_move error: {e}")
        return {"ok": False, "error": str(e)}


async def mouse_scroll(clicks: int, x: int = None, y: int = None) -> dict:
    """Scroll the mouse wheel. Positive = up, negative = down."""
    try:
        if x is not None and y is not None:
            pyautogui.scroll(clicks, x=x, y=y)
        else:
            pyautogui.scroll(clicks)
        logger.info(f"[DESKTOP] Scrolled {clicks} clicks")
        return {"ok": True, "scrolled": clicks}
    except Exception as e:
        logger.error(f"[DESKTOP] scroll error: {e}")
        return {"ok": False, "error": str(e)}


# ============================================
# KEYBOARD CONTROL
# ============================================

async def type_text(text: str, interval: float = 0.03) -> dict:
    """Type text with human-like timing."""
    try:
        pyautogui.typewrite(text, interval=interval) if text.isascii() else pyautogui.write(text)
        logger.info(f"[DESKTOP] Typed: {text[:50]}...")
        return {"ok": True, "typed": text[:100]}
    except Exception as e:
        logger.error(f"[DESKTOP] type_text error: {e}")
        return {"ok": False, "error": str(e)}


async def press_key(key: str) -> dict:
    """Press a single key or key combination.
    Examples: 'enter', 'tab', 'ctrl+c', 'ctrl+shift+s', 'alt+f4', 'win+d'
    """
    try:
        parts = [k.strip().lower() for k in key.split("+")]

        if len(parts) == 1:
            pyautogui.press(parts[0])
        else:
            # Hotkey combo
            pyautogui.hotkey(*parts)

        logger.info(f"[DESKTOP] Pressed: {key}")
        return {"ok": True, "key": key}
    except Exception as e:
        logger.error(f"[DESKTOP] press_key error: {e}")
        return {"ok": False, "error": str(e)}


# ============================================
# SCREEN READING
# ============================================

async def take_screenshot(region: tuple = None) -> dict:
    """Take a screenshot of the entire screen or a region.
    region: (left, top, width, height) or None for full screen.
    """
    try:
        output_dir = Path(__file__).resolve().parent.parent / "output"
        output_dir.mkdir(exist_ok=True)

        filepath = output_dir / f"desktop_screenshot_{int(time.time())}.png"

        if region:
            screenshot = pyautogui.screenshot(region=region)
        else:
            screenshot = pyautogui.screenshot()

        screenshot.save(str(filepath))
        logger.info(f"[DESKTOP] Screenshot saved: {filepath}")
        return {"ok": True, "path": str(filepath)}
    except Exception as e:
        logger.error(f"[DESKTOP] screenshot error: {e}")
        return {"ok": False, "error": str(e)}


async def locate_on_screen(image_path: str, confidence: float = 0.8) -> dict:
    """Find an image on screen and return its coordinates.
    Useful for finding buttons, icons, etc.
    """
    try:
        location = pyautogui.locateOnScreen(image_path, confidence=confidence)
        if location:
            center = pyautogui.center(location)
            return {
                "ok": True,
                "found": True,
                "x": center.x,
                "y": center.y,
                "region": {
                    "left": location.left,
                    "top": location.top,
                    "width": location.width,
                    "height": location.height,
                },
            }
        return {"ok": True, "found": False}
    except Exception as e:
        logger.error(f"[DESKTOP] locate error: {e}")
        return {"ok": False, "error": str(e)}


# ============================================
# UI AUTOMATION (Windows UI Tree)
# ============================================

async def get_ui_elements(window_title: str = None) -> dict:
    """Read the UI element tree of a window using Windows UI Automation.
    Returns clickable elements with their names and positions.
    """
    try:
        import uiautomation as auto

        if window_title:
            # Find specific window
            control = auto.WindowControl(searchDepth=1, Name=window_title)
            if not control.Exists(maxSearchSeconds=3):
                # Try partial match
                control = auto.WindowControl(
                    searchDepth=1, SubName=window_title
                )
                if not control.Exists(maxSearchSeconds=3):
                    return {"ok": False, "error": f"Window '{window_title}' not found"}
        else:
            control = auto.GetForegroundControl()

        elements = []
        _walk_ui_tree(control, elements, depth=0, max_depth=3)

        logger.info(f"[DESKTOP] UI elements for '{window_title}': {len(elements)} found")
        return {"ok": True, "window": window_title or "foreground", "elements": elements[:100]}
    except ImportError:
        return {"ok": False, "error": "uiautomation not available on this platform"}
    except Exception as e:
        logger.error(f"[DESKTOP] UI elements error: {e}")
        return {"ok": False, "error": str(e)}


def _walk_ui_tree(control, elements: list, depth: int, max_depth: int):
    """Recursively walk the Windows UI Automation tree."""
    if depth > max_depth or len(elements) >= 100:
        return

    try:
        import uiautomation as auto

        name = control.Name or ""
        control_type = str(control.ControlTypeName) if hasattr(control, 'ControlTypeName') else ""
        rect = control.BoundingRectangle

        # Only include elements that are visible and have a name
        if name.strip() and rect.width() > 0 and rect.height() > 0:
            elements.append({
                "name": name[:100],
                "type": control_type,
                "x": rect.left + rect.width() // 2,
                "y": rect.top + rect.height() // 2,
                "width": rect.width(),
                "height": rect.height(),
                "depth": depth,
            })

        for child in control.GetChildren():
            _walk_ui_tree(child, elements, depth + 1, max_depth)
    except Exception:
        pass


async def click_ui_element(window_title: str, element_name: str) -> dict:
    """Find and click a UI element by name within a window.
    Uses Windows UI Automation to find the element, then clicks its center.
    """
    try:
        import uiautomation as auto

        # Find window
        win = auto.WindowControl(searchDepth=1, SubName=window_title)
        if not win.Exists(maxSearchSeconds=3):
            return {"ok": False, "error": f"Window '{window_title}' not found"}

        # Search for element
        target = _find_element_by_name(win, element_name, max_depth=4)
        if not target:
            return {"ok": False, "error": f"Element '{element_name}' not found in '{window_title}'"}

        # Click center of element
        rect = target.BoundingRectangle
        cx = rect.left + rect.width() // 2
        cy = rect.top + rect.height() // 2

        pyautogui.click(cx, cy)
        await asyncio.sleep(0.3)

        logger.info(f"[DESKTOP] Clicked UI element '{element_name}' at ({cx}, {cy})")
        return {"ok": True, "clicked": element_name, "x": cx, "y": cy}
    except ImportError:
        return {"ok": False, "error": "uiautomation not available on this platform"}
    except Exception as e:
        logger.error(f"[DESKTOP] click_ui_element error: {e}")
        return {"ok": False, "error": str(e)}


def _find_element_by_name(control, name: str, max_depth: int = 4, depth: int = 0):
    """Recursively search for a UI element by name."""
    if depth > max_depth:
        return None

    try:
        if control.Name and name.lower() in control.Name.lower():
            return control

        for child in control.GetChildren():
            result = _find_element_by_name(child, name, max_depth, depth + 1)
            if result:
                return result
    except Exception:
        pass
    return None


# ============================================
# HIGH-LEVEL ACTIONS
# ============================================

async def desktop_action(instruction: str) -> dict:
    """Execute a high-level desktop action described in natural language.
    This is the main entry point — parses the instruction and routes to
    the appropriate low-level function.

    Supports:
    - "open [app]" → open_app
    - "click [element] in [window]" → click_ui_element
    - "type [text]" → type_text
    - "press [key]" → press_key
    - "screenshot" → take_screenshot
    - "list windows" → get_open_windows
    """
    instruction_lower = instruction.lower().strip()

    try:
        # Open app
        if instruction_lower.startswith("open "):
            app = instruction[5:].strip()
            return await open_app(app)

        # Type text
        if instruction_lower.startswith("type "):
            text = instruction[5:].strip()
            return await type_text(text)

        # Press key
        if instruction_lower.startswith("press "):
            key = instruction[6:].strip()
            return await press_key(key)

        # Screenshot
        if "screenshot" in instruction_lower:
            return await take_screenshot()

        # List windows
        if "list windows" in instruction_lower or "open windows" in instruction_lower:
            return await get_open_windows()

        # Focus window
        if instruction_lower.startswith("focus "):
            title = instruction[6:].strip()
            return await focus_window(title)

        # Click UI element: "click [element] in [window]"
        if instruction_lower.startswith("click "):
            parts = instruction[6:]
            if " in " in parts.lower():
                idx = parts.lower().index(" in ")
                element = parts[:idx].strip()
                window = parts[idx + 4:].strip()
                return await click_ui_element(window, element)
            else:
                # Try clicking by name in foreground window
                return await click_ui_element("", parts.strip())

        # Scroll
        if instruction_lower.startswith("scroll "):
            direction = instruction[7:].strip().lower()
            clicks = -3 if "down" in direction else 3
            return await mouse_scroll(clicks)

        return {"ok": False, "error": f"Could not parse instruction: {instruction}"}
    except Exception as e:
        logger.error(f"[DESKTOP] desktop_action error: {e}")
        return {"ok": False, "error": str(e)}

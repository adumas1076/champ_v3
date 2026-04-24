"""
Skill Change Detector — Watches .claude/skills/ for file changes
and hot-reloads skills without restart.

Harvested from: Claude Code source (skillChangeDetector.ts)
Pattern: File watcher (chokidar in JS, watchdog in Python) monitors
skill directories. When a SKILL.md changes, caches are cleared
and skills are reloaded automatically.

Our addition: Also watches for new skills created by skillify,
and notifies running operators that their skill set has changed.
"""

import logging
import threading
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger("cocreatiq.skills.change_detector")

# Directories to watch
WATCH_DIRS = [
    ".claude/skills",
    ".claude/commands",
]

# Debounce: wait for writes to stabilize before reloading
RELOAD_DEBOUNCE_SEC = 0.5

# Callbacks to notify when skills change
_listeners: list[Callable[[], None]] = []
_watcher_thread: Optional[threading.Thread] = None
_running = False


def subscribe(callback: Callable[[], None]) -> Callable[[], None]:
    """Subscribe to skill change notifications.

    Args:
        callback: Function to call when skills change.

    Returns:
        Unsubscribe function.
    """
    _listeners.append(callback)

    def unsubscribe():
        if callback in _listeners:
            _listeners.remove(callback)

    return unsubscribe


def _notify_listeners():
    """Notify all subscribers that skills changed."""
    for listener in _listeners:
        try:
            listener()
        except Exception as e:
            logger.warning(f"Skill change listener error: {e}")


def initialize(base_dir: str = ".") -> None:
    """Start watching skill directories for changes.

    Uses watchdog library if available, falls back to polling.

    Args:
        base_dir: Base directory containing .claude/skills/
    """
    global _watcher_thread, _running

    if _running:
        return

    _running = True

    try:
        _start_watchdog(base_dir)
    except ImportError:
        logger.info("watchdog not installed — using polling for skill changes")
        _start_polling(base_dir)


def _start_watchdog(base_dir: str) -> None:
    """Start file watching using watchdog library."""
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileModifiedEvent, FileCreatedEvent, FileDeletedEvent

    class SkillChangeHandler(FileSystemEventHandler):
        def __init__(self):
            self._timer = None

        def _schedule_reload(self):
            """Debounce rapid changes into a single reload."""
            if self._timer:
                self._timer.cancel()
            self._timer = threading.Timer(RELOAD_DEBOUNCE_SEC, self._do_reload)
            self._timer.start()

        def _do_reload(self):
            logger.info("[SKILL CHANGE] Detected skill file change — reloading")
            # Clear caches in skill_loader
            from .skill_loader import load_all_skills
            load_all_skills()  # Forces reload
            _notify_listeners()

        def on_modified(self, event):
            if event.src_path.endswith(".md"):
                self._schedule_reload()

        def on_created(self, event):
            if event.src_path.endswith(".md"):
                self._schedule_reload()

        def on_deleted(self, event):
            if event.src_path.endswith(".md"):
                self._schedule_reload()

    observer = Observer()
    handler = SkillChangeHandler()

    for watch_dir in WATCH_DIRS:
        dir_path = Path(base_dir) / watch_dir
        if dir_path.exists():
            observer.schedule(handler, str(dir_path), recursive=True)
            logger.info(f"[SKILL CHANGE] Watching {dir_path}")

    observer.daemon = True
    observer.start()


def _start_polling(base_dir: str) -> None:
    """Fallback: poll skill directories for changes every 2 seconds."""
    import time

    def poll_loop():
        last_mtimes: dict[str, float] = {}

        while _running:
            changed = False

            for watch_dir in WATCH_DIRS:
                dir_path = Path(base_dir) / watch_dir
                if not dir_path.exists():
                    continue

                for md_file in dir_path.rglob("*.md"):
                    mtime = md_file.stat().st_mtime
                    key = str(md_file)

                    if key in last_mtimes and last_mtimes[key] != mtime:
                        changed = True
                    last_mtimes[key] = mtime

            if changed:
                logger.info("[SKILL CHANGE] Detected skill file change (polling) — reloading")
                _notify_listeners()

            time.sleep(2)

    global _watcher_thread
    _watcher_thread = threading.Thread(target=poll_loop, daemon=True)
    _watcher_thread.start()


def dispose() -> None:
    """Stop watching for changes."""
    global _running
    _running = False
    _listeners.clear()

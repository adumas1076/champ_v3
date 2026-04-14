# ============================================
# CHAMP V3 — Cursor Telemetry Capture
# Harvested from: OpenScreen (siddharthvaddem)
#
# Captures cursor position at 100ms intervals
# during Self Mode execution. Stored alongside
# the screen recording for auto-zoom playback.
#
# Telemetry is normalized to 0-1 range relative
# to the capture area, enabling resolution-
# independent zoom targeting.
# ============================================

import json
import logging
import os
import time
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Sampling interval (ms) — matches OpenScreen's 100ms
CURSOR_SAMPLE_INTERVAL_MS = 100
CURSOR_SAMPLE_INTERVAL_S = CURSOR_SAMPLE_INTERVAL_MS / 1000.0

# Max recording duration: 60 hours (36K samples at 100ms = 1 hour)
MAX_SAMPLES = 36_000 * 60


@dataclass
class CursorSample:
    """A single cursor position sample."""
    time_ms: int       # Milliseconds since recording start
    cx: float          # Normalized X (0.0 - 1.0)
    cy: float          # Normalized Y (0.0 - 1.0)
    clicked: bool = False  # Was mouse clicked at this sample?


@dataclass
class CursorTelemetry:
    """Complete cursor telemetry for a recording session."""
    version: int = 1
    samples: list[dict] = field(default_factory=list)
    screen_width: int = 1920
    screen_height: int = 1080
    start_time: float = 0.0

    def add_sample(self, cx: float, cy: float, clicked: bool = False) -> None:
        if len(self.samples) >= MAX_SAMPLES:
            return
        elapsed_ms = int((time.time() - self.start_time) * 1000)
        self.samples.append({
            "timeMs": elapsed_ms,
            "cx": round(cx, 4),
            "cy": round(cy, 4),
            "clicked": clicked,
        })

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "screenWidth": self.screen_width,
            "screenHeight": self.screen_height,
            "sampleCount": len(self.samples),
            "durationMs": self.samples[-1]["timeMs"] if self.samples else 0,
            "samples": self.samples,
        }

    def save(self, filepath: str) -> bool:
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(self.to_dict(), f)
            logger.info(
                f"[CURSOR] Saved {len(self.samples)} samples to {filepath}"
            )
            return True
        except Exception as e:
            logger.error(f"[CURSOR] Save failed: {e}")
            return False


class CursorTracker:
    """
    Background cursor position tracker.

    Runs in a daemon thread, sampling cursor position at 100ms
    intervals. Uses platform-specific methods to get cursor pos.

    Usage:
        tracker = CursorTracker()
        tracker.start(screen_width=1920, screen_height=1080)
        # ... Self Mode runs ...
        telemetry = tracker.stop()
        telemetry.save("path/to/cursor.json")
    """

    def __init__(self):
        self._telemetry: Optional[CursorTelemetry] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False

    def start(
        self,
        screen_width: int = 1920,
        screen_height: int = 1080,
    ) -> None:
        """Start capturing cursor telemetry in background."""
        if self._running:
            logger.warning("[CURSOR] Already tracking")
            return

        self._telemetry = CursorTelemetry(
            screen_width=screen_width,
            screen_height=screen_height,
            start_time=time.time(),
        )
        self._running = True

        self._thread = threading.Thread(
            target=self._capture_loop,
            name="cursor-telemetry",
            daemon=True,
        )
        self._thread.start()
        logger.info(f"[CURSOR] Tracking started ({screen_width}x{screen_height})")

    def stop(self) -> Optional[CursorTelemetry]:
        """Stop tracking and return the telemetry data."""
        self._running = False

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

        telemetry = self._telemetry
        self._telemetry = None
        self._thread = None

        if telemetry:
            logger.info(
                f"[CURSOR] Tracking stopped: {len(telemetry.samples)} samples, "
                f"{telemetry.samples[-1]['timeMs'] / 1000:.1f}s" if telemetry.samples else "0s"
            )

        return telemetry

    @property
    def is_running(self) -> bool:
        return self._running

    def _capture_loop(self) -> None:
        """Background sampling loop."""
        while self._running:
            try:
                cx, cy, clicked = self._get_cursor_position()
                if self._telemetry:
                    # Normalize to 0-1
                    nx = cx / max(self._telemetry.screen_width, 1)
                    ny = cy / max(self._telemetry.screen_height, 1)
                    # Clamp to [0, 1]
                    nx = max(0.0, min(1.0, nx))
                    ny = max(0.0, min(1.0, ny))
                    self._telemetry.add_sample(nx, ny, clicked)
            except Exception:
                pass  # Never crash the capture loop

            time.sleep(CURSOR_SAMPLE_INTERVAL_S)

    def _get_cursor_position(self) -> tuple[int, int, bool]:
        """
        Get current cursor position. Platform-specific.
        Returns (x, y, is_clicking).
        """
        try:
            # Windows: use ctypes (no external dependency)
            import ctypes
            import ctypes.wintypes

            class POINT(ctypes.Structure):
                _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

            pt = POINT()
            ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))

            # Check if left mouse button is pressed
            clicked = bool(ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000)

            return pt.x, pt.y, clicked

        except Exception:
            pass

        try:
            # Fallback: pyautogui (cross-platform)
            import pyautogui
            pos = pyautogui.position()
            return pos.x, pos.y, False
        except ImportError:
            pass

        # Last resort: no cursor data
        return 0, 0, False

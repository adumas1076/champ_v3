# ============================================
# CHAMP V3 — Auto-Annotator
# Harvested from: OpenScreen (siddharthvaddem)
#
# Automatically generates annotations for
# proof-of-work recordings from Self Mode
# subtask lists. Each subtask becomes a
# timestamped label on the video.
#
# Annotation format matches OpenScreen's
# schema for future compatibility with their
# editor if we ever want visual editing.
# ============================================

import json
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class Annotation:
    """A single video annotation — text label at a timestamp."""
    id: str
    type: str = "text"      # text | step_marker | error_marker | success_marker
    text: str = ""
    start_ms: int = 0       # When to show
    end_ms: int = 0         # When to hide (0 = show for 5 seconds)
    position_x: float = 0.05  # % of canvas (0-1)
    position_y: float = 0.05  # % of canvas (0-1)
    style: str = "step"     # step | error | success | info


@dataclass
class AnnotationTrack:
    """Complete annotation track for a recording."""
    version: int = 1
    annotations: list[Annotation] = field(default_factory=list)
    run_id: str = ""
    goal_objective: str = ""

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "run_id": self.run_id,
            "goal_objective": self.goal_objective,
            "annotation_count": len(self.annotations),
            "annotations": [
                {
                    "id": a.id,
                    "type": a.type,
                    "text": a.text,
                    "startMs": a.start_ms,
                    "endMs": a.end_ms,
                    "position": {"x": a.position_x, "y": a.position_y},
                    "style": a.style,
                }
                for a in self.annotations
            ],
        }

    def save(self, filepath: str) -> bool:
        import os
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(self.to_dict(), f, indent=2)
            logger.info(
                f"[ANNOTATOR] Saved {len(self.annotations)} annotations to {filepath}"
            )
            return True
        except Exception as e:
            logger.error(f"[ANNOTATOR] Save failed: {e}")
            return False


class AutoAnnotator:
    """
    Generates annotations from Self Mode execution data.

    Takes the subtask list + timing data and produces
    timestamped labels that overlay on the proof recording.

    Each subtask gets:
    - A step marker at its start time ("Step 1: Research competitors")
    - A status marker at completion (green check or red X)
    - Error annotations for failed steps

    The goal objective gets a title card at 0:00.
    The final status gets an end card.
    """

    # Display duration for annotations (ms)
    STEP_DISPLAY_MS = 5000
    TITLE_DISPLAY_MS = 4000
    STATUS_DISPLAY_MS = 6000

    def generate(
        self,
        run_id: str,
        goal_objective: str,
        subtasks: list[dict],
        step_timestamps: list[dict],
        total_duration_ms: int,
    ) -> AnnotationTrack:
        """
        Generate annotations from execution data.

        Args:
            run_id: Self Mode run ID
            goal_objective: What the task was trying to achieve
            subtasks: List of SubTask.to_dict() results
            step_timestamps: [{subtask_id, start_ms, end_ms}] from proof recorder
            total_duration_ms: Total recording duration

        Returns:
            AnnotationTrack with all annotations
        """
        track = AnnotationTrack(
            run_id=run_id,
            goal_objective=goal_objective,
        )

        # 1. Title card at start
        track.annotations.append(Annotation(
            id=f"{run_id}-title",
            type="text",
            text=f"Self Mode: {goal_objective[:80]}",
            start_ms=0,
            end_ms=self.TITLE_DISPLAY_MS,
            position_x=0.05,
            position_y=0.05,
            style="info",
        ))

        # 2. Step markers from subtask timestamps
        timestamp_map = {
            ts["subtask_id"]: ts for ts in step_timestamps
        }

        for i, st in enumerate(subtasks):
            st_id = st.get("id", f"st-{i}")
            description = st.get("description", f"Step {i + 1}")
            status = st.get("status", "pending")
            error = st.get("error")

            # Get timing from timestamp map, or estimate from order
            ts = timestamp_map.get(st_id)
            if ts:
                start_ms = ts["start_ms"]
            else:
                # Estimate: distribute evenly across recording
                start_ms = int(
                    (i / max(len(subtasks), 1)) * total_duration_ms
                )

            # Step label
            step_num = i + 1
            track.annotations.append(Annotation(
                id=f"{run_id}-step-{step_num}",
                type="step_marker",
                text=f"Step {step_num}: {description[:60]}",
                start_ms=start_ms,
                end_ms=start_ms + self.STEP_DISPLAY_MS,
                position_x=0.05,
                position_y=0.90,  # Bottom of screen
                style="step",
            ))

            # Status marker
            if status == "completed":
                track.annotations.append(Annotation(
                    id=f"{run_id}-status-{step_num}",
                    type="success_marker",
                    text=f"Step {step_num} completed",
                    start_ms=ts["end_ms"] if ts else start_ms + self.STEP_DISPLAY_MS,
                    end_ms=(ts["end_ms"] if ts else start_ms + self.STEP_DISPLAY_MS) + 2000,
                    position_x=0.75,
                    position_y=0.05,
                    style="success",
                ))
            elif status == "failed":
                error_text = f"Step {step_num} failed"
                if error:
                    error_text += f": {error[:50]}"
                track.annotations.append(Annotation(
                    id=f"{run_id}-error-{step_num}",
                    type="error_marker",
                    text=error_text,
                    start_ms=ts["end_ms"] if ts else start_ms + self.STEP_DISPLAY_MS,
                    end_ms=(ts["end_ms"] if ts else start_ms + self.STEP_DISPLAY_MS) + 4000,
                    position_x=0.05,
                    position_y=0.85,
                    style="error",
                ))

        # 3. End card
        completed = sum(1 for st in subtasks if st.get("status") == "completed")
        total = len(subtasks)
        track.annotations.append(Annotation(
            id=f"{run_id}-end",
            type="text",
            text=f"Complete: {completed}/{total} steps passed",
            start_ms=max(0, total_duration_ms - self.STATUS_DISPLAY_MS),
            end_ms=total_duration_ms,
            position_x=0.3,
            position_y=0.45,
            style="success" if completed == total else "error",
        ))

        logger.info(
            f"[ANNOTATOR] Generated {len(track.annotations)} annotations "
            f"for {run_id}"
        )
        return track

"""
CHAMP Avatar — Body Compositor

Composites a face render from FlashHead onto a body template.
The body template provides shoulders, torso, hands, and gestures.

Architecture:
  1. Face region rendered by FlashHead (512x512)
  2. Body template selected by gesture class (pre-rendered or procedural)
  3. Face placed onto body using face landmarks for alignment
  4. Blended at boundaries for seamless composite

Body templates are stored as:
    avatar/body/templates/{gesture_class}/
        frame_000.png ... frame_N.png  (looping animation)

For now, uses a simple overlay approach:
  - Body template is a larger frame (e.g., 768x1024 or 1024x1024)
  - Face region mask defines where FlashHead output goes
  - Alpha blending at edges for smooth transition
"""

import logging
import os
from pathlib import Path
from typing import Optional

import numpy as np

from .. import config
from .gesture_predictor import GestureClass, GesturePrediction

logger = logging.getLogger("champ.avatar.body.compositor")

# Default composite output size (body frame)
COMPOSITE_WIDTH = 768
COMPOSITE_HEIGHT = 1024

# Face placement on the body template (normalized coordinates)
# These define where the face center sits in the composite
FACE_CENTER_X = 0.5     # Horizontally centered
FACE_CENTER_Y = 0.28    # Upper third (head position)
FACE_SCALE = 0.55       # Face width as fraction of composite width


class BodyTemplate:
    """
    A looping body animation for a specific gesture.
    Loads pre-rendered frames from disk or generates procedural ones.
    """

    def __init__(self, gesture: GestureClass, template_dir: Optional[str] = None):
        self.gesture = gesture
        self._frames: list[np.ndarray] = []
        self._frame_idx = 0

        if template_dir and os.path.isdir(template_dir):
            self._load_from_disk(template_dir)
        else:
            self._generate_procedural()

    def _load_from_disk(self, template_dir: str):
        """Load pre-rendered body template frames."""
        from PIL import Image

        frame_files = sorted(
            f for f in os.listdir(template_dir) if f.endswith(".png")
        )

        for ff in frame_files:
            img = Image.open(os.path.join(template_dir, ff)).convert("RGBA")
            img = img.resize((COMPOSITE_WIDTH, COMPOSITE_HEIGHT), Image.LANCZOS)
            self._frames.append(np.array(img))

        if self._frames:
            logger.debug(f"Loaded {len(self._frames)} frames for gesture '{self.gesture.value}'")

    def _generate_procedural(self):
        """Generate a simple procedural body template (placeholder)."""
        # Create a basic body silhouette frame
        frame = np.zeros((COMPOSITE_HEIGHT, COMPOSITE_WIDTH, 4), dtype=np.uint8)

        # Body color (neutral gray-blue)
        body_color = [60, 65, 75]

        # Draw simple torso rectangle
        torso_top = int(COMPOSITE_HEIGHT * 0.35)
        torso_bot = int(COMPOSITE_HEIGHT * 0.95)
        torso_left = int(COMPOSITE_WIDTH * 0.2)
        torso_right = int(COMPOSITE_WIDTH * 0.8)

        frame[torso_top:torso_bot, torso_left:torso_right, :3] = body_color
        frame[torso_top:torso_bot, torso_left:torso_right, 3] = 255

        # Draw shoulders (wider than torso)
        shoulder_top = int(COMPOSITE_HEIGHT * 0.3)
        shoulder_bot = torso_top
        shoulder_left = int(COMPOSITE_WIDTH * 0.1)
        shoulder_right = int(COMPOSITE_WIDTH * 0.9)

        frame[shoulder_top:shoulder_bot, shoulder_left:shoulder_right, :3] = body_color
        frame[shoulder_top:shoulder_bot, shoulder_left:shoulder_right, 3] = 255

        # Draw neck
        neck_top = int(COMPOSITE_HEIGHT * 0.25)
        neck_bot = shoulder_top
        neck_left = int(COMPOSITE_WIDTH * 0.38)
        neck_right = int(COMPOSITE_WIDTH * 0.62)

        skin_color = [180, 150, 130]
        frame[neck_top:neck_bot, neck_left:neck_right, :3] = skin_color
        frame[neck_top:neck_bot, neck_left:neck_right, 3] = 255

        # Single frame for now — no animation
        self._frames = [frame]

    def get_frame(self) -> np.ndarray:
        """Get the next frame in the looping animation."""
        if not self._frames:
            return np.zeros((COMPOSITE_HEIGHT, COMPOSITE_WIDTH, 4), dtype=np.uint8)

        frame = self._frames[self._frame_idx]
        self._frame_idx = (self._frame_idx + 1) % len(self._frames)
        return frame.copy()

    def reset(self):
        """Reset animation to first frame."""
        self._frame_idx = 0


class BodyCompositor:
    """
    Composites face renders onto body templates.

    Usage:
        compositor = BodyCompositor()
        full_frame = compositor.composite(face_frame, gesture_prediction)
    """

    def __init__(self, template_base_dir: Optional[str] = None):
        self._template_dir = template_base_dir
        self._templates: dict[GestureClass, BodyTemplate] = {}
        self._current_gesture = GestureClass.NEUTRAL

        # Pre-load neutral template at minimum
        self._get_template(GestureClass.NEUTRAL)

    def _get_template(self, gesture: GestureClass) -> BodyTemplate:
        """Get or create body template for a gesture."""
        if gesture not in self._templates:
            template_dir = None
            if self._template_dir:
                gesture_dir = os.path.join(self._template_dir, gesture.value)
                if os.path.isdir(gesture_dir):
                    template_dir = gesture_dir

            self._templates[gesture] = BodyTemplate(gesture, template_dir)

        return self._templates[gesture]

    def composite(
        self,
        face_frame: np.ndarray,
        gesture: Optional[GesturePrediction] = None,
        output_size: Optional[tuple[int, int]] = None,
    ) -> np.ndarray:
        """
        Composite face onto body template.

        Args:
            face_frame: RGBA uint8 face render from FlashHead (512x512)
            gesture: Optional gesture prediction for body animation
            output_size: Optional (width, height) for output. Default: COMPOSITE_WIDTH x COMPOSITE_HEIGHT

        Returns:
            RGBA uint8 composite frame
        """
        out_w = output_size[0] if output_size else COMPOSITE_WIDTH
        out_h = output_size[1] if output_size else COMPOSITE_HEIGHT

        # Get body template frame
        gesture_class = gesture.gesture if gesture else GestureClass.NEUTRAL
        template = self._get_template(gesture_class)
        body_frame = template.get_frame()

        # Resize body template if needed
        if body_frame.shape[1] != out_w or body_frame.shape[0] != out_h:
            from PIL import Image
            body_pil = Image.fromarray(body_frame)
            body_pil = body_pil.resize((out_w, out_h), Image.LANCZOS)
            body_frame = np.array(body_pil)

        # Calculate face placement
        face_h, face_w = face_frame.shape[:2]
        target_face_w = int(out_w * FACE_SCALE)
        target_face_h = int(target_face_w * face_h / face_w)  # Maintain aspect ratio

        # Resize face to target size
        from PIL import Image
        face_pil = Image.fromarray(face_frame)
        face_pil = face_pil.resize((target_face_w, target_face_h), Image.LANCZOS)
        face_resized = np.array(face_pil)

        # Calculate paste position (centered at face anchor point)
        paste_x = int(out_w * FACE_CENTER_X - target_face_w / 2)
        paste_y = int(out_h * FACE_CENTER_Y - target_face_h / 2)

        # Clamp to bounds
        paste_x = max(0, min(paste_x, out_w - target_face_w))
        paste_y = max(0, min(paste_y, out_h - target_face_h))

        # Create soft edge mask for blending (elliptical feather)
        mask = self._create_blend_mask(target_face_w, target_face_h)

        # Composite: body * (1-mask) + face * mask
        result = body_frame.copy()
        region = result[paste_y:paste_y+target_face_h, paste_x:paste_x+target_face_w]

        for c in range(3):  # RGB channels
            region[:, :, c] = (
                region[:, :, c].astype(np.float32) * (1.0 - mask) +
                face_resized[:, :, c].astype(np.float32) * mask
            ).astype(np.uint8)

        # Alpha channel: max of body and face
        region[:, :, 3] = np.maximum(region[:, :, 3], face_resized[:, :, 3])

        result[paste_y:paste_y+target_face_h, paste_x:paste_x+target_face_w] = region

        return result

    def _create_blend_mask(self, width: int, height: int, feather: float = 0.15) -> np.ndarray:
        """
        Create an elliptical feathered mask for face-body blending.
        Center = 1.0 (fully face), edges = 0.0 (fully body).
        """
        y_coords = np.linspace(-1, 1, height)
        x_coords = np.linspace(-1, 1, width)
        yy, xx = np.meshgrid(y_coords, x_coords, indexing="ij")

        # Elliptical distance
        dist = np.sqrt(xx**2 + yy**2)

        # Sigmoid-like falloff at edges
        edge_start = 1.0 - feather * 2
        mask = np.clip((1.0 - dist) / (1.0 - edge_start + 1e-6), 0, 1)

        # Smooth step
        mask = mask * mask * (3 - 2 * mask)

        return mask.astype(np.float32)

    def reset(self):
        """Reset all template animations."""
        for template in self._templates.values():
            template.reset()
        self._current_gesture = GestureClass.NEUTRAL

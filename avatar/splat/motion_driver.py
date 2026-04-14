"""
CHAMP Avatar — Gaussian Splat Motion Driver

Deforms a FLAME-rigged 3D Gaussian Splat using blendshape parameters.

The existing avatar/motion.py predicts 52 ARKit blendshapes + 3 head pose
from audio. This module maps those 55 parameters to FLAME deformations,
then applies them to the rigged Gaussians.

Flow:
  Audio → MotionPredictor (55 params) → SplatMotionDriver → deformed Gaussians
                                                            → serialize to DataChannel

The output is a compact MotionFrame (220 bytes) sent over WebRTC DataChannel
to the client browser, where gsplat.js applies the deformation and renders.

Wraps: FLAME mesh deformation from GaussianAvatars binding
"""

import logging
import struct
import time
from dataclasses import dataclass
from typing import Optional

import numpy as np

from .. import config

logger = logging.getLogger("champ.avatar.splat.motion_driver")


# ─── ARKit to FLAME Mapping ────────────────────────────────────────────────
# ARKit uses 52 blendshapes. FLAME uses 100 expression coefficients + 6 pose params.
# This mapping converts between the two systems.

# Key ARKit → FLAME expression mappings (indices into FLAME's 100-dim expression vector)
ARKIT_TO_FLAME_EXPRESSION = {
    # Jaw
    config.IDX_JAW_OPEN: [22, 23],          # jaw open → FLAME expr 22-23
    14: [20],                                 # jawForward → FLAME expr 20
    15: [21],                                 # jawLeft → FLAME expr 21
    16: [21],                                 # jawRight → FLAME expr 21 (negated)

    # Mouth
    config.IDX_MOUTH_FUNNEL: [26, 27],       # mouthFunnel → FLAME expr 26-27
    config.IDX_MOUTH_PUCKER: [28, 29],       # mouthPucker → FLAME expr 28-29
    config.IDX_MOUTH_SMILE_LEFT: [30],       # mouthSmileLeft → FLAME expr 30
    config.IDX_MOUTH_SMILE_RIGHT: [31],      # mouthSmileRight → FLAME expr 31
    25: [32],                                 # mouthFrownLeft → FLAME expr 32
    26: [33],                                 # mouthFrownRight → FLAME expr 33

    # Eyes
    config.IDX_EYE_BLINK_LEFT: [0, 1],      # eyeBlinkLeft → FLAME expr 0-1
    config.IDX_EYE_BLINK_RIGHT: [2, 3],     # eyeBlinkRight → FLAME expr 2-3

    # Brows
    config.IDX_BROW_INNER_UP: [10, 11],     # browInnerUp → FLAME expr 10-11
    config.IDX_BROW_OUTER_UP_LEFT: [12],    # browOuterUpLeft → FLAME expr 12
    config.IDX_BROW_OUTER_UP_RIGHT: [13],   # browOuterUpRight → FLAME expr 13
    41: [14],                                 # browDownLeft → FLAME expr 14
    42: [15],                                 # browDownRight → FLAME expr 15

    # Cheeks
    46: [40, 41],                             # cheekPuff → FLAME expr 40-41
    47: [42],                                 # cheekSquintLeft → FLAME expr 42
    48: [43],                                 # cheekSquintRight → FLAME expr 43

    # Nose
    49: [44],                                 # noseSneerLeft → FLAME expr 44
    50: [45],                                 # noseSneerRight → FLAME expr 45
}


@dataclass
class MotionFrame:
    """
    A single frame of motion data to send over WebRTC DataChannel.

    Total size: 55 floats × 4 bytes = 220 bytes per frame.
    At 25fps = 5,500 bytes/second = 5.4 KB/s (vs ~4 MB/s for video).
    """
    blendshapes: np.ndarray   # (52,) ARKit blendshape values [0, 1]
    head_pose: np.ndarray     # (3,) pitch, yaw, roll in degrees
    timestamp: float          # Server timestamp for sync
    gesture: str = ""         # Gesture class from body/gesture_predictor.py

    def to_bytes(self) -> bytes:
        """Serialize to compact binary for DataChannel transmission."""
        # 52 blendshapes + 3 head pose = 55 floats
        motion_data = np.concatenate([self.blendshapes, self.head_pose])
        # Pack: 55 floats (220 bytes) + timestamp (8 bytes) + gesture (1 byte index)
        gesture_idx = GESTURE_INDEX.get(self.gesture, 0)
        return (
            struct.pack(f"<{config.MOTION_DIM}f", *motion_data) +
            struct.pack("<d", self.timestamp) +
            struct.pack("<B", gesture_idx)
        )

    @classmethod
    def from_bytes(cls, data: bytes) -> "MotionFrame":
        """Deserialize from DataChannel binary."""
        float_size = config.MOTION_DIM * 4
        motion_data = np.array(
            struct.unpack(f"<{config.MOTION_DIM}f", data[:float_size]),
            dtype=np.float32,
        )
        timestamp = struct.unpack("<d", data[float_size:float_size + 8])[0]
        gesture_idx = struct.unpack("<B", data[float_size + 8:float_size + 9])[0]
        gesture = GESTURE_NAMES.get(gesture_idx, "")

        return cls(
            blendshapes=motion_data[:config.NUM_BLENDSHAPES],
            head_pose=motion_data[config.NUM_BLENDSHAPES:],
            timestamp=timestamp,
            gesture=gesture,
        )

    def to_dict(self) -> dict:
        """JSON-serializable dict (for debugging / WebSocket fallback)."""
        return {
            "blendshapes": self.blendshapes.tolist(),
            "head_pose": self.head_pose.tolist(),
            "timestamp": self.timestamp,
            "gesture": self.gesture,
        }

    @property
    def size_bytes(self) -> int:
        return config.MOTION_FRAME_BYTES + 8 + 1  # motion + timestamp + gesture


# Gesture encoding for compact binary serialization
GESTURE_INDEX = {
    "": 0, "neutral": 0,
    "nod": 1, "emphasis": 2, "thinking": 3,
    "shrug": 4, "point": 5, "wave": 6,
    "head_tilt": 7, "lean_forward": 8,
}
GESTURE_NAMES = {v: k for k, v in GESTURE_INDEX.items()}


class SplatMotionDriver:
    """
    Drives a FLAME-rigged 3DGS avatar using motion parameters.

    Takes the 55-dim motion vector from MotionPredictor and:
    1. Maps ARKit blendshapes → FLAME expression coefficients
    2. Maps head pose (pitch/yaw/roll) → FLAME pose parameters
    3. Computes vertex offsets on FLAME mesh
    4. Packages as MotionFrame for DataChannel transmission

    In server mode: outputs MotionFrame → WebRTC DataChannel → browser
    In local mode: can directly deform Gaussians (for testing/rendering)

    Usage:
        driver = SplatMotionDriver()
        driver.load_avatar("anthony")

        # From audio pipeline:
        motion_vec = motion_predictor.predict(audio_features)  # (55,)
        frame = driver.drive(motion_vec, gesture="emphasis")
        datachannel.send(frame.to_bytes())  # 229 bytes
    """

    def __init__(self):
        self._flame_model = None
        self._avatar_id = None
        self._splat_path = None
        self._flame_params = None  # Base FLAME shape for this avatar
        self._available = False

    def load_avatar(self, avatar_id: str, avatars_dir: str | None = None) -> bool:
        """
        Load avatar's FLAME rigging for motion driving.

        Loads:
          - Base FLAME shape parameters (identity)
          - FLAME model for expression deformation
          - Splat file path for client download

        Returns True if ready.
        """
        base_dir = avatars_dir or str(config.AVATARS_DIR)
        avatar_dir = config.AVATARS_DIR / avatar_id if not avatars_dir else \
            __import__("pathlib").Path(base_dir) / avatar_id
        splat_dir = avatar_dir / config.SPLAT_DIR_NAME

        # Load splat path
        splat_path = splat_dir / "splat.ply"
        if not splat_path.exists():
            logger.warning(f"Splat file not found: {splat_path}")
            # Still allow motion driving without splat (for testing)

        self._splat_path = str(splat_path)
        self._avatar_id = avatar_id

        # Load FLAME base parameters
        flame_params_path = splat_dir / "training_result.json"
        if flame_params_path.exists():
            import json
            with open(flame_params_path) as f:
                meta = json.load(f)
            logger.info(f"Loaded avatar '{avatar_id}' splat metadata")

        # Try to load FLAME model for expression mapping
        self._flame_model = self._load_flame_model()

        # Load base shape from training
        base_flame_path = avatar_dir / "flame_tracking" / "flame_params.npz"
        if base_flame_path.exists():
            data = np.load(base_flame_path)
            # Use mean shape across all training frames as identity
            self._flame_params = {
                "shape": data["shape"].mean(axis=0),
                "expression_mean": data["expression"].mean(axis=0),
            }
            logger.info(f"Loaded FLAME base shape for '{avatar_id}'")
        else:
            self._flame_params = {
                "shape": np.zeros(300, dtype=np.float32),
                "expression_mean": np.zeros(100, dtype=np.float32),
            }

        self._available = True
        logger.info(f"SplatMotionDriver loaded for avatar '{avatar_id}'")
        return True

    def _load_flame_model(self):
        """Load FLAME model for vertex deformation."""
        try:
            import pickle
            if config.FLAME_MODEL_PATH.exists():
                with open(config.FLAME_MODEL_PATH, "rb") as f:
                    flame_data = pickle.load(f, encoding="latin1")
                logger.info("FLAME model loaded")
                return flame_data
            else:
                logger.info("FLAME model not found, using direct blendshape mapping")
                return None
        except Exception as e:
            logger.info(f"FLAME model load failed ({e}), using direct mapping")
            return None

    def drive(
        self,
        motion_vector: np.ndarray,
        gesture: str = "",
        timestamp: Optional[float] = None,
    ) -> MotionFrame:
        """
        Convert 55-dim motion vector to a MotionFrame for transmission.

        Args:
            motion_vector: (55,) from MotionPredictor — 52 blendshapes + 3 head pose
            gesture: Gesture class from GesturePredictor
            timestamp: Server time (auto if None)

        Returns:
            MotionFrame ready for DataChannel serialization
        """
        if len(motion_vector) != config.MOTION_DIM:
            raise ValueError(
                f"Expected {config.MOTION_DIM}-dim motion vector, got {len(motion_vector)}"
            )

        blendshapes = motion_vector[:config.NUM_BLENDSHAPES]
        head_pose = motion_vector[config.NUM_BLENDSHAPES:]

        # Clamp blendshapes to [0, 1]
        blendshapes = np.clip(blendshapes, 0.0, 1.0)

        # Clamp head pose to reasonable range (degrees)
        head_pose = np.clip(head_pose, -30.0, 30.0)

        return MotionFrame(
            blendshapes=blendshapes,
            head_pose=head_pose,
            timestamp=timestamp or time.time(),
            gesture=gesture,
        )

    def arkit_to_flame_expression(self, blendshapes: np.ndarray) -> np.ndarray:
        """
        Convert 52 ARKit blendshapes to 100 FLAME expression coefficients.

        Used when driving GaussianAvatars directly (e.g., for offline rendering).
        For live calls, the client does this mapping in JavaScript.
        """
        expression = np.zeros(100, dtype=np.float32)

        for arkit_idx, flame_indices in ARKIT_TO_FLAME_EXPRESSION.items():
            if arkit_idx < len(blendshapes):
                value = blendshapes[arkit_idx]
                for flame_idx in flame_indices:
                    expression[flame_idx] += value * 0.5  # Scale factor

        # Add base expression offset for this avatar
        if self._flame_params:
            expression += self._flame_params["expression_mean"] * 0.1

        return expression

    def arkit_to_flame_pose(self, head_pose: np.ndarray) -> np.ndarray:
        """
        Convert 3-dim head pose (pitch, yaw, roll degrees) to FLAME 6-dim pose.

        FLAME pose: [global_rot_x, global_rot_y, global_rot_z, jaw_x, jaw_y, jaw_z]
        """
        flame_pose = np.zeros(6, dtype=np.float32)

        # Convert degrees to radians
        pitch_rad = np.radians(head_pose[0])
        yaw_rad = np.radians(head_pose[1])
        roll_rad = np.radians(head_pose[2])

        # Map to FLAME global rotation (first 3 dims)
        flame_pose[0] = pitch_rad
        flame_pose[1] = yaw_rad
        flame_pose[2] = roll_rad

        # Jaw pose is driven by jaw blendshapes, not head pose
        # (handled in expression mapping)

        return flame_pose

    def get_flame_deformation(self, motion_vector: np.ndarray) -> dict:
        """
        Full FLAME deformation parameters from motion vector.
        Used for server-side rendering (offline) or debugging.
        """
        blendshapes = motion_vector[:config.NUM_BLENDSHAPES]
        head_pose = motion_vector[config.NUM_BLENDSHAPES:]

        return {
            "expression": self.arkit_to_flame_expression(blendshapes),
            "pose": self.arkit_to_flame_pose(head_pose),
            "shape": self._flame_params["shape"] if self._flame_params else np.zeros(300),
        }

    @property
    def splat_path(self) -> Optional[str]:
        """Path to this avatar's .ply splat file (for client download)."""
        return self._splat_path

    @property
    def avatar_id(self) -> Optional[str]:
        return self._avatar_id

    @property
    def available(self) -> bool:
        return self._available

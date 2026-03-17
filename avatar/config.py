"""
CHAMP Avatar — Configuration
All settings in one place. Nothing hardcoded elsewhere.
"""

import os
from pathlib import Path

# ─── Paths ────────────────────────────────────────────────────────────────────

CHAMP_ROOT = Path(__file__).parent.parent
AVATAR_DIR = Path(__file__).parent
MODELS_DIR = CHAMP_ROOT / "models"
REFERENCE_IMAGE = CHAMP_ROOT / "frontend" / "public" / "operators" / "champ" / "champ_bio_01.png"

# Model paths
LIVEPORTRAIT_DIR = MODELS_DIR / "LivePortrait"
FLASHHEAD_DIR = MODELS_DIR / "SoulX-FlashHead-1_3B"
WAV2VEC2_DIR = MODELS_DIR / "wav2vec2-base-960h"

# ─── Video Output ─────────────────────────────────────────────────────────────

VIDEO_WIDTH = 512
VIDEO_HEIGHT = 512
VIDEO_FPS = 30.0
VIDEO_UPSCALE = False          # Set True + install Real-ESRGAN for 1080p output
VIDEO_UPSCALE_WIDTH = 1280
VIDEO_UPSCALE_HEIGHT = 720

# ─── Audio Input ──────────────────────────────────────────────────────────────

# OpenAI Realtime outputs 24kHz int16 PCM
AUDIO_INPUT_SAMPLE_RATE = 24000
AUDIO_INPUT_CHANNELS = 1
AUDIO_INPUT_DTYPE = "int16"

# wav2vec2 expects 16kHz float32
AUDIO_MODEL_SAMPLE_RATE = 16000
AUDIO_MODEL_DTYPE = "float32"

# Audio context window for feature extraction (seconds)
AUDIO_CONTEXT_SECONDS = 0.5    # 500ms sliding window — enough for per-frame features

# ─── Motion Smoothing ─────────────────────────────────────────────────────────

# EMA alpha per state (higher = more responsive, lower = smoother)
SMOOTHING_ALPHA_SPEAKING = 0.7
SMOOTHING_ALPHA_LISTENING = 0.3
SMOOTHING_ALPHA_IDLE = 0.2

# State transition blend durations (seconds)
TRANSITION_SPEAKING_TO_IDLE = 0.3        # 300ms ease out after speaking ends
TRANSITION_SPEAKING_TO_LISTENING = 0.15  # 150ms quick transition on interrupt
TRANSITION_IDLE_TO_SPEAKING = 0.05       # 50ms — anticipatory mouth opening
TRANSITION_LISTENING_TO_SPEAKING = 0.05

# Anticipatory motion: mouth begins opening N seconds before audio plays
ANTICIPATORY_OFFSET_SEC = 0.05  # 50ms pre-opening

# ─── Idle Animation (procedural) ─────────────────────────────────────────────

BLINK_INTERVAL_MIN = 2.5       # Seconds between blinks (randomized)
BLINK_INTERVAL_MAX = 5.0
BLINK_DURATION = 0.15          # How long a blink takes (seconds)

BREATHING_RATE = 0.25          # Hz (one breath every 4 seconds)
BREATHING_AMPLITUDE = 0.02     # Subtle shoulder/chest movement

HEAD_SWAY_SPEED = 0.1          # Perlin noise speed for idle head drift
HEAD_SWAY_AMPLITUDE = 0.03     # Very subtle

# Listening state adds these on top of idle
LISTENING_NOD_PROBABILITY = 0.15   # Per-second chance of a nod
LISTENING_NOD_DURATION = 0.6       # Seconds per nod
LISTENING_BROW_RAISE_PROB = 0.08   # Per-second chance of brow raise

# ─── Blendshape Indices (ARKit 52 standard) ──────────────────────────────────
# These map to the 52 ARKit blendshape standard used by FlashHead/LivePortrait

BLENDSHAPE_NAMES = [
    "eyeBlinkLeft", "eyeLookDownLeft", "eyeLookInLeft", "eyeLookOutLeft",
    "eyeLookUpLeft", "eyeSquintLeft", "eyeWideLeft",
    "eyeBlinkRight", "eyeLookDownRight", "eyeLookInRight", "eyeLookOutRight",
    "eyeLookUpRight", "eyeSquintRight", "eyeWideRight",
    "jawForward", "jawLeft", "jawRight", "jawOpen",
    "mouthClose", "mouthFunnel", "mouthPucker", "mouthLeft", "mouthRight",
    "mouthSmileLeft", "mouthSmileRight", "mouthFrownLeft", "mouthFrownRight",
    "mouthDimpleLeft", "mouthDimpleRight", "mouthStretchLeft", "mouthStretchRight",
    "mouthRollLower", "mouthRollUpper", "mouthShrugLower", "mouthShrugUpper",
    "mouthPressLeft", "mouthPressRight", "mouthLowerDownLeft", "mouthLowerDownRight",
    "mouthUpperUpLeft", "mouthUpperUpRight",
    "browDownLeft", "browDownRight", "browInnerUp", "browOuterUpLeft", "browOuterUpRight",
    "cheekPuff", "cheekSquintLeft", "cheekSquintRight",
    "noseSneerLeft", "noseSneerRight",
    "tongueOut",
]

NUM_BLENDSHAPES = len(BLENDSHAPE_NAMES)  # 52

# Head pose: pitch, yaw, roll (degrees)
HEAD_POSE_DIM = 3

# Total motion vector dimension
MOTION_DIM = NUM_BLENDSHAPES + HEAD_POSE_DIM  # 55

# ─── Key blendshape indices for quick access ──────────────────────────────────

IDX_EYE_BLINK_LEFT = 0
IDX_EYE_BLINK_RIGHT = 7
IDX_JAW_OPEN = 17
IDX_MOUTH_CLOSE = 18
IDX_MOUTH_FUNNEL = 19
IDX_MOUTH_PUCKER = 20
IDX_MOUTH_SMILE_LEFT = 23
IDX_MOUTH_SMILE_RIGHT = 24
IDX_BROW_INNER_UP = 43
IDX_BROW_OUTER_UP_LEFT = 44
IDX_BROW_OUTER_UP_RIGHT = 45

# Head pose indices (appended after 52 blendshapes)
IDX_HEAD_PITCH = 52
IDX_HEAD_YAW = 53
IDX_HEAD_ROLL = 54

# ─── GPU / Device ─────────────────────────────────────────────────────────────

DEVICE = os.getenv("CHAMP_AVATAR_DEVICE", "cuda")  # "cuda" or "cpu"
DTYPE = "float16"  # Use fp16 on GPU for speed

# ─── Feature Flags ────────────────────────────────────────────────────────────

AVATAR_ENABLED = os.getenv("CHAMP_AVATAR_ENABLED", "false").lower() == "true"
PLACEHOLDER_MODE = os.getenv("CHAMP_AVATAR_PLACEHOLDER", "true").lower() == "true"

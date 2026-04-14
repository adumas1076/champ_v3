"""
CHAMP Avatar — Configuration
All settings in one place. Nothing hardcoded elsewhere.
"""

import os
from enum import Enum
from pathlib import Path


class RenderMode(Enum):
    """Which rendering pipeline to use for speaking frames."""
    GAUSSIAN_SPLAT = "gaussian_splat"    # 3DGS client-rendered (Phase 7, best for live)
    PERSONALIVE = "personalive"          # Zero-training instant avatar (Phase 7, single photo)
    FLASHHEAD_FULL = "flashhead_full"    # Full diffusion pipeline (best quality async)
    SPLIT_PIPELINE = "split_pipeline"    # LivePortrait warp + FlashHead MLP (legacy)
    PLACEHOLDER = "placeholder"          # Procedural pixel effects (no GPU needed)


# ─── Paths ────────────────────────────────────────────────────────────────────

CHAMP_ROOT = Path(__file__).parent.parent
AVATAR_DIR = Path(__file__).parent
MODELS_DIR = CHAMP_ROOT / "models"
REFERENCE_IMAGE = CHAMP_ROOT / "frontend" / "public" / "operators" / "champ" / "champ_bio_01.png"
REFERENCE_VIDEO = os.getenv("CHAMP_AVATAR_REFERENCE_VIDEO", None)  # 2-min video (overrides image)

# Model paths
LIVEPORTRAIT_DIR = MODELS_DIR / "LivePortrait"
FLASHHEAD_DIR = MODELS_DIR / "SoulX-FlashHead-1_3B"
WAV2VEC2_DIR = MODELS_DIR / "wav2vec2-base-960h"

# FlashHead source code (cloned repo for inference imports)
FLASHHEAD_SRC_DIR = CHAMP_ROOT / "SoulX-FlashHead"

# Avatar storage (multi-reference keyframes from 2-min videos)
AVATARS_DIR = MODELS_DIR / "avatars"

# ─── Render Mode ─────────────────────────────────────────────────────────────

_render_mode_str = os.getenv("CHAMP_AVATAR_RENDER_MODE", "flashhead_full")
RENDER_MODE = RenderMode(_render_mode_str) if _render_mode_str in [m.value for m in RenderMode] else RenderMode.PLACEHOLDER

# ─── Video Output ─────────────────────────────────────────────────────────────

VIDEO_WIDTH = 512
VIDEO_HEIGHT = 512
VIDEO_FPS = 25.0               # Match FlashHead native FPS (was 30)
VIDEO_UPSCALE = False          # Set True + install Real-ESRGAN for 4K output
VIDEO_UPSCALE_FACTOR = 4       # 2x or 4x
VIDEO_UPSCALE_WIDTH = 2048     # 512 * 4
VIDEO_UPSCALE_HEIGHT = 2048    # 512 * 4

# ─── FlashHead Full Pipeline ────────────────────────────────────────────────

FLASHHEAD_MODEL_TYPE = os.getenv("CHAMP_FLASHHEAD_MODEL", "lite")  # "lite" or "pro"
FLASHHEAD_CHUNK_FRAMES = 33             # Total frames per diffusion chunk
FLASHHEAD_MOTION_FRAMES_LATENT = 2      # Latent frames carried for continuity
FLASHHEAD_CACHED_AUDIO_DURATION = 8     # Seconds of audio context in sliding deque
FLASHHEAD_SAMPLE_SHIFT = 5              # Audio window size for context
FLASHHEAD_COLOR_CORRECTION = 1.0        # Color correction strength (0=off, 1=full)
FLASHHEAD_USE_FACE_CROP = True          # Auto-detect and crop face from reference
FLASHHEAD_SEED = 42                     # Reproducibility seed

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

# GPU backend: "auto" (try local, fall back to modal), "local", or "modal"
GPU_BACKEND = os.getenv("CHAMP_GPU_BACKEND", "auto")

# ─── Feature Flags ────────────────────────────────────────────────────────────

AVATAR_ENABLED = os.getenv("CHAMP_AVATAR_ENABLED", "false").lower() == "true"
PLACEHOLDER_MODE = RENDER_MODE == RenderMode.PLACEHOLDER

# ─── Derived Constants ───────────────────────────────────────────────────────

# Usable new frames per FlashHead chunk (total minus continuity overlap)
# Pro model: motion_frames_num ≈ 5, Lite: ≈ 9 → actual usable varies
# Conservative estimate based on FlashHead inference code
FLASHHEAD_USABLE_FRAMES = FLASHHEAD_CHUNK_FRAMES - 5  # ~28 frames

# Audio samples needed per chunk (at 16kHz, 25fps)
FLASHHEAD_CHUNK_AUDIO_SAMPLES = int(
    FLASHHEAD_USABLE_FRAMES * AUDIO_MODEL_SAMPLE_RATE / VIDEO_FPS
)  # ~17920 samples ≈ 1.12 seconds of audio

# Chunk generation cadence in seconds
FLASHHEAD_CHUNK_DURATION_SEC = FLASHHEAD_USABLE_FRAMES / VIDEO_FPS  # ~1.12s

# ─── Gaussian Splat (Phase 7) ───────────────────────────────────────────────

# Splat storage per avatar: models/avatars/{avatar_id}/splat/
SPLAT_DIR_NAME = "splat"

# GaussianAvatars training
SPLAT_TRAIN_ITERATIONS = int(os.getenv("CHAMP_SPLAT_TRAIN_ITERS", "30000"))
SPLAT_SH_DEGREE = 3                        # Spherical harmonics degree
SPLAT_RESOLUTION = 512                     # Training image resolution
SPLAT_DENSIFY_UNTIL = 15000                # Densify Gaussians until this iteration
SPLAT_LAMBDA_DSSIM = 0.2                   # SSIM loss weight
SPLAT_FLAME_MODEL = "FLAME2020"            # FLAME model version
SPLAT_NUM_GAUSSIANS_PER_TRIANGLE = 6       # Gaussians per FLAME mesh triangle

# Virtual Capture Studio
VCS_NUM_VIEWS = 96                         # Virtual camera views to generate
VCS_EXPRESSION_VARIANTS = ["neutral", "smile", "talk", "think"]
VCS_IDENTITY_THRESHOLD = 0.65             # InsightFace cosine similarity min
VCS_UPSCALE_VIEWS = True                   # Upscale synthetic views to 4K

# Instant Preview (FastAvatar / FaceLift)
INSTANT_PREVIEW_TIMEOUT_SEC = 30           # Max time for instant preview generation

# Client rendering
SPLAT_MAX_FILE_SIZE_MB = 200               # Max .ply file size for browser delivery
SPLAT_COMPRESSED_FORMAT = "splat"           # Export format: "ply" or "splat" (compressed)

# Motion data channel (WebRTC DataChannel)
MOTION_FRAME_RATE = 25                     # Motion params per second
MOTION_FRAME_BYTES = MOTION_DIM * 4        # 55 floats × 4 bytes = 220 bytes
MOTION_BANDWIDTH_KBS = MOTION_FRAME_BYTES * MOTION_FRAME_RATE / 1024  # ~5.4 KB/s

# Reference repos (cloned to avatar/reference/)
REFERENCE_DIR = AVATAR_DIR / "reference"
GAUSSIAN_TALKER_DIR = REFERENCE_DIR / "GaussianTalker"
GAUSSIAN_AVATARS_DIR = REFERENCE_DIR / "GaussianAvatars"
FACELIFT_DIR = REFERENCE_DIR / "FaceLift"
PERSONALIVE_DIR = REFERENCE_DIR / "PersonaLive"

# FLAME model path
FLAME_MODEL_PATH = MODELS_DIR / "flame" / "generic_model.pkl"
FLAME_LANDMARK_PATH = MODELS_DIR / "flame" / "landmark_embedding.npy"

# ─── PersonaLive (Zero-Training Instant Avatar) ─────────────────────────────

# PersonaLive: real-time streaming diffusion — single photo, no per-identity training
# Wraps: https://github.com/GVCLab/PersonaLive (Apache 2.0, CVPR 2026)

PERSONALIVE_CONFIG = PERSONALIVE_DIR / "configs" / "prompts" / "personalive_online.yaml"
PERSONALIVE_WEIGHTS_DIR = PERSONALIVE_DIR / "pretrained_weights"

# Streaming parameters (from PersonaLive defaults)
PERSONALIVE_TEMPORAL_WINDOW = 4        # Frames per diffusion batch
PERSONALIVE_TEMPORAL_STEP = 4          # Sliding window stride
PERSONALIVE_DDIM_STEPS = 4            # Denoising steps (fixed: 999, 666, 333, 0)
PERSONALIVE_RESOLUTION = 512           # Output resolution
PERSONALIVE_DTYPE = "fp16"             # Inference precision
PERSONALIVE_FPS = 16                   # Default output FPS (adaptive 10-30)

# Adaptive keyframe injection (drift prevention)
PERSONALIVE_MOTION_BANK_THRESHOLD = 17.0  # Euclidean distance for novel motion detection
PERSONALIVE_MAX_KEYFRAME_INJECTIONS = 3   # Max re-fusions before stopping

# Model weight files (6 pretrained components)
PERSONALIVE_WEIGHT_FILES = [
    "personalive/reference_unet.pth",
    "personalive/denoising_unet.pth",
    "personalive/pose_guider.pth",
    "personalive/motion_encoder.pth",
    "personalive/temporal_module.pth",
    "personalive/motion_extractor.pth",
]

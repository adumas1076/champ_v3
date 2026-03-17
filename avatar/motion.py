"""
CHAMP Avatar — Audio-to-Motion Predictor
Takes wav2vec2 audio features and predicts facial motion parameters.

Uses FlashHead's motion prediction head (lightweight MLP) to convert
768-dim audio embeddings → 52 blendshapes + 3 head pose per frame.

Falls back to PlaceholderMotionPredictor for testing without GPU/models.
"""

import numpy as np
from . import config

# Lazy imports
_torch = None
_motion_model = None


def _ensure_torch():
    global _torch
    if _torch is None:
        import torch
        _torch = torch
    return _torch


def _ensure_motion_model():
    """Load FlashHead's motion prediction MLP."""
    global _motion_model
    if _motion_model is None:
        try:
            torch = _ensure_torch()
            from flash_head.models import MotionPredictor as FHMotionPredictor
            _motion_model = FHMotionPredictor.from_pretrained(
                str(config.FLASHHEAD_DIR)
            )
            _motion_model.eval()
            if config.DEVICE == "cuda" and torch.cuda.is_available():
                _motion_model = _motion_model.to(config.DEVICE)
                if config.DTYPE == "float16":
                    _motion_model = _motion_model.half()
            print("[avatar/motion] FlashHead motion predictor loaded")
        except Exception as e:
            print(f"[avatar/motion] FlashHead not available ({e}), using placeholder")
            _motion_model = "placeholder"

    return _motion_model


class MotionPredictor:
    """
    Predicts facial motion from audio features using FlashHead's MLP.

    Input: 768-dim wav2vec2 feature vector + previous 3 motion frames (context)
    Output: 55-dim motion vector (52 blendshapes + 3 head pose)

    The context window (previous frames) makes predictions temporally coherent
    and the model autoregressive — each frame depends on recent history.
    """

    def __init__(self):
        self._model = None
        self._context: list[np.ndarray] = []  # Last N motion frames
        self._context_size = 3

    def _get_model(self):
        if self._model is None:
            self._model = _ensure_motion_model()
        return self._model

    def predict(self, audio_features: np.ndarray) -> np.ndarray:
        """
        Predict motion parameters from audio features.

        Args:
            audio_features: wav2vec2 output, shape (768,)

        Returns:
            motion vector, shape (55,) — 52 blendshapes + 3 head pose
        """
        model = self._get_model()

        if model == "placeholder":
            return self._predict_placeholder(audio_features)

        torch = _ensure_torch()

        # Build context tensor from recent frames
        context = np.zeros((self._context_size, config.MOTION_DIM), dtype=np.float32)
        for i, frame in enumerate(self._context[-self._context_size:]):
            idx = self._context_size - len(self._context[-self._context_size:]) + i
            context[idx] = frame

        with torch.no_grad():
            audio_t = torch.from_numpy(audio_features).unsqueeze(0).to(config.DEVICE)
            context_t = torch.from_numpy(context).unsqueeze(0).to(config.DEVICE)

            if config.DTYPE == "float16" and config.DEVICE == "cuda":
                audio_t = audio_t.half()
                context_t = context_t.half()

            motion_t = model(audio_t, context_t)
            motion = motion_t.float().cpu().squeeze().numpy()

        # Update context
        self._context.append(motion.copy())
        if len(self._context) > self._context_size * 2:
            self._context = self._context[-self._context_size:]

        return motion

    def _predict_placeholder(self, audio_features: np.ndarray) -> np.ndarray:
        """
        Placeholder motion prediction for testing without FlashHead.
        Maps audio energy to basic mouth/jaw movement.
        """
        motion = np.zeros(config.MOTION_DIM, dtype=np.float32)

        # Use audio feature energy as a proxy for speech intensity
        energy = np.abs(audio_features).mean()
        energy_norm = min(1.0, energy / 0.5)  # Normalize to 0-1 range

        # Jaw opens proportional to energy
        motion[config.IDX_JAW_OPEN] = energy_norm * 0.6

        # Mouth shapes vary with different parts of the feature vector
        motion[config.IDX_MOUTH_FUNNEL] = np.abs(audio_features[100:200]).mean() * 0.3
        motion[config.IDX_MOUTH_PUCKER] = np.abs(audio_features[200:300]).mean() * 0.2

        # Slight head movement correlated with speech
        motion[config.IDX_HEAD_PITCH] = audio_features[0] * 0.02
        motion[config.IDX_HEAD_YAW] = audio_features[1] * 0.02

        # Brow movement correlated with emphasis
        brow_energy = np.abs(audio_features[500:600]).mean()
        motion[config.IDX_BROW_INNER_UP] = brow_energy * 0.1

        # Update context
        self._context.append(motion.copy())
        if len(self._context) > self._context_size * 2:
            self._context = self._context[-self._context_size:]

        return motion

    def clear_context(self) -> None:
        """Clear motion context (on interrupt/state change)."""
        self._context.clear()
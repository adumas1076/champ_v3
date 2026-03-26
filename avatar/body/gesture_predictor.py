"""
CHAMP Avatar — Gesture Predictor

Maps audio prosody (energy, pitch, speech rate) to gesture classes.
Gestures are selected per-chunk and drive the body template animation.

Gesture Classes:
  - NEUTRAL: hands resting, minimal movement
  - EMPHASIS: one hand raised slightly, making a point
  - OPEN_PALMS: both hands open, explaining broadly
  - POINTING: one hand extended, directing attention
  - THINKING: hand near chin, contemplative
  - COUNTING: fingers counting, listing items
  - SHRUG: shoulders raised, palms up, uncertainty
  - NOD: head nod with slight body lean (agreement)

The predictor is intentionally simple — rule-based on audio features.
Can be upgraded to ML-based (e.g., speech2gesture model) later.
"""

import logging
from enum import Enum
from dataclasses import dataclass

import numpy as np

from .. import config

logger = logging.getLogger("champ.avatar.body.gesture")


class GestureClass(Enum):
    NEUTRAL = "neutral"
    EMPHASIS = "emphasis"
    OPEN_PALMS = "open_palms"
    POINTING = "pointing"
    THINKING = "thinking"
    COUNTING = "counting"
    SHRUG = "shrug"
    NOD = "nod"


@dataclass
class GesturePrediction:
    gesture: GestureClass
    intensity: float      # 0.0 = subtle, 1.0 = full
    confidence: float     # 0.0 = random, 1.0 = certain
    duration_sec: float   # How long this gesture should play


# Audio feature thresholds for gesture classification
ENERGY_HIGH = 0.15       # RMS above this = energetic speech
ENERGY_LOW = 0.03        # RMS below this = quiet/pausing
PITCH_RISE = 0.1         # Pitch delta indicating question/emphasis
SPEECH_RATE_FAST = 0.7   # Fraction of frames with audio above threshold


class GesturePredictor:
    """
    Predicts body gestures from audio chunk features.

    Input: raw audio array (16kHz float32, ~1.1s chunk)
    Output: GesturePrediction for the chunk

    Algorithm:
      1. Compute audio energy (RMS) over the chunk
      2. Compute energy variance (dynamic vs monotone)
      3. Detect energy peaks (emphasis points)
      4. Map features to gesture class via rules
    """

    def __init__(self):
        self._prev_gesture = GestureClass.NEUTRAL
        self._gesture_hold_frames = 0
        self._min_hold = 3  # Minimum chunks to hold a gesture before switching

    def predict(self, audio_chunk: np.ndarray) -> GesturePrediction:
        """
        Predict gesture for an audio chunk.

        Args:
            audio_chunk: float32 numpy array at 16kHz (~1.1 seconds)

        Returns:
            GesturePrediction with gesture class, intensity, confidence
        """
        if len(audio_chunk) < 160:  # Less than 10ms
            return GesturePrediction(
                gesture=GestureClass.NEUTRAL,
                intensity=0.0,
                confidence=0.0,
                duration_sec=config.FLASHHEAD_CHUNK_DURATION_SEC,
            )

        # Extract audio features
        features = self._extract_features(audio_chunk)

        # Classify gesture
        gesture, confidence = self._classify(features)

        # Apply hold logic (don't switch gestures too fast)
        if gesture != self._prev_gesture:
            self._gesture_hold_frames += 1
            if self._gesture_hold_frames < self._min_hold:
                gesture = self._prev_gesture
                confidence *= 0.5  # Lower confidence during hold
            else:
                self._prev_gesture = gesture
                self._gesture_hold_frames = 0
        else:
            self._gesture_hold_frames = 0

        # Intensity from energy
        intensity = min(1.0, features["energy_rms"] / ENERGY_HIGH)

        return GesturePrediction(
            gesture=gesture,
            intensity=intensity,
            confidence=confidence,
            duration_sec=config.FLASHHEAD_CHUNK_DURATION_SEC,
        )

    def _extract_features(self, audio: np.ndarray) -> dict:
        """Extract prosody features from audio chunk."""
        # RMS energy
        energy_rms = float(np.sqrt(np.mean(audio ** 2)))

        # Energy variance (how dynamic the speech is)
        frame_size = len(audio) // 10
        if frame_size > 0:
            frame_energies = [
                np.sqrt(np.mean(audio[i:i+frame_size] ** 2))
                for i in range(0, len(audio) - frame_size, frame_size)
            ]
            energy_var = float(np.var(frame_energies)) if frame_energies else 0.0
        else:
            energy_var = 0.0

        # Peak detection (emphasis moments)
        abs_audio = np.abs(audio)
        threshold = energy_rms * 2
        peaks = np.sum(abs_audio > threshold)
        peak_ratio = peaks / len(audio) if len(audio) > 0 else 0.0

        # Zero crossing rate (rough speech rate proxy)
        zero_crossings = np.sum(np.abs(np.diff(np.sign(audio))) > 0)
        zcr = zero_crossings / len(audio) if len(audio) > 0 else 0.0

        # Speech activity ratio (how much of the chunk has audible speech)
        voiced_frames = np.sum(abs_audio > ENERGY_LOW)
        speech_ratio = voiced_frames / len(audio) if len(audio) > 0 else 0.0

        return {
            "energy_rms": energy_rms,
            "energy_var": energy_var,
            "peak_ratio": peak_ratio,
            "zcr": zcr,
            "speech_ratio": speech_ratio,
        }

    def _classify(self, features: dict) -> tuple[GestureClass, float]:
        """
        Rule-based gesture classification from audio features.
        Returns (gesture_class, confidence).
        """
        energy = features["energy_rms"]
        variance = features["energy_var"]
        peaks = features["peak_ratio"]
        zcr = features["zcr"]
        speech = features["speech_ratio"]

        # Silence or very quiet -> neutral
        if energy < ENERGY_LOW:
            return GestureClass.NEUTRAL, 0.9

        # Very energetic with high variance -> emphasis
        if energy > ENERGY_HIGH and variance > 0.001:
            return GestureClass.EMPHASIS, 0.8

        # High energy, low variance -> open palms (sustained explanation)
        if energy > ENERGY_HIGH * 0.7 and variance < 0.0005:
            return GestureClass.OPEN_PALMS, 0.7

        # Lots of peaks -> counting/listing
        if peaks > 0.05 and speech > SPEECH_RATE_FAST:
            return GestureClass.COUNTING, 0.6

        # Low energy with speech -> thinking
        if ENERGY_LOW < energy < ENERGY_HIGH * 0.5 and speech > 0.3:
            return GestureClass.THINKING, 0.5

        # Brief pause after speech -> nod
        if speech < 0.4 and energy > ENERGY_LOW:
            return GestureClass.NOD, 0.6

        # Default
        return GestureClass.NEUTRAL, 0.4

    def reset(self):
        """Reset state on interrupt."""
        self._prev_gesture = GestureClass.NEUTRAL
        self._gesture_hold_frames = 0

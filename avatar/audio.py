"""
CHAMP Avatar — Audio Processing

Three modes:
  1. ChunkAudioAccumulator  — For FlashHead full pipeline (RENDER_MODE=flashhead_full)
     Accumulates raw 16kHz audio in a sliding deque. Signals when enough audio
     for one FlashHead chunk (~1.1s) has arrived. FlashHead's own wav2vec2
     handles feature extraction internally.

  2. AudioFeatureExtractor  — For split pipeline (RENDER_MODE=split_pipeline)
     Per-frame wav2vec2 feature extraction. Legacy path.

  3. PlaceholderAudioExtractor — For placeholder mode (no GPU)
     Returns random features for testing.
"""

import collections
import logging
import numpy as np
from . import config

logger = logging.getLogger("champ.avatar.audio")

# Lazy imports for GPU-dependent libs
_torch = None
_wav2vec2_model = None
_wav2vec2_processor = None
_resampler = None


def _ensure_torch():
    global _torch
    if _torch is None:
        import torch
        _torch = torch
    return _torch


def _ensure_resampler():
    """High-quality sinc resampler: 24kHz → 16kHz."""
    global _resampler
    if _resampler is None:
        torch = _ensure_torch()
        import torchaudio
        _resampler = torchaudio.transforms.Resample(
            orig_freq=config.AUDIO_INPUT_SAMPLE_RATE,
            new_freq=config.AUDIO_MODEL_SAMPLE_RATE,
            lowpass_filter_width=64,
            dtype=torch.float32,
        )
        if config.DEVICE == "cuda" and torch.cuda.is_available():
            _resampler = _resampler.to(config.DEVICE)
    return _resampler


def _ensure_wav2vec2():
    """Load wav2vec2 model for audio feature extraction."""
    global _wav2vec2_model, _wav2vec2_processor
    if _wav2vec2_model is None:
        torch = _ensure_torch()
        from transformers import Wav2Vec2Processor, Wav2Vec2Model

        model_path = str(config.WAV2VEC2_DIR)
        _wav2vec2_processor = Wav2Vec2Processor.from_pretrained(model_path)
        _wav2vec2_model = Wav2Vec2Model.from_pretrained(model_path)
        _wav2vec2_model.eval()

        if config.DEVICE == "cuda" and torch.cuda.is_available():
            _wav2vec2_model = _wav2vec2_model.to(config.DEVICE)
            if config.DTYPE == "float16":
                _wav2vec2_model = _wav2vec2_model.half()

    return _wav2vec2_model, _wav2vec2_processor


class AudioFeatureExtractor:
    """
    Streaming audio feature extractor.

    Takes raw audio frames (24kHz int16 from OpenAI Realtime),
    resamples to 16kHz float32, maintains a sliding context window,
    and extracts wav2vec2 features per-frame.

    Usage:
        extractor = AudioFeatureExtractor()
        extractor.push_audio(raw_bytes)  # from TTS
        features = extractor.extract()    # wav2vec2 embeddings
    """

    def __init__(self):
        # Sliding window of resampled audio (16kHz float32)
        window_samples = int(config.AUDIO_CONTEXT_SECONDS * config.AUDIO_MODEL_SAMPLE_RATE)
        self._buffer = collections.deque(maxlen=window_samples)
        self._has_audio = False

    def push_audio(self, raw_bytes: bytes) -> None:
        """
        Push raw audio from OpenAI Realtime (24kHz int16 PCM).
        Resamples to 16kHz float32 and appends to sliding window.
        """
        torch = _ensure_torch()

        # Convert raw bytes → int16 numpy → float32 tensor
        audio_int16 = np.frombuffer(raw_bytes, dtype=np.int16)
        audio_f32 = audio_int16.astype(np.float32) / 32768.0
        tensor = torch.from_numpy(audio_f32)

        # Move to device if needed
        if config.DEVICE == "cuda" and torch.cuda.is_available():
            tensor = tensor.to(config.DEVICE)

        # Resample 24kHz → 16kHz
        resampler = _ensure_resampler()
        resampled = resampler(tensor)

        # Append to sliding window
        samples = resampled.cpu().numpy()
        self._buffer.extend(samples.tolist())
        self._has_audio = True

    def extract(self) -> np.ndarray | None:
        """
        Extract wav2vec2 features from current audio window.
        Returns feature vector (768-dim) or None if no audio.
        """
        if not self._has_audio or len(self._buffer) < 160:  # Need at least 10ms
            return None

        torch = _ensure_torch()
        model, processor = _ensure_wav2vec2()

        # Get current window as numpy array
        audio_window = np.array(list(self._buffer), dtype=np.float32)

        # Process through wav2vec2
        with torch.no_grad():
            inputs = processor(
                audio_window,
                sampling_rate=config.AUDIO_MODEL_SAMPLE_RATE,
                return_tensors="pt",
                padding=True,
            )
            input_values = inputs.input_values.to(config.DEVICE)

            if config.DTYPE == "float16" and config.DEVICE == "cuda":
                input_values = input_values.half()

            outputs = model(input_values)
            # Take mean of hidden states across time → single 768-dim vector
            features = outputs.last_hidden_state.mean(dim=1).squeeze()

        return features.float().cpu().numpy()

    def clear(self) -> None:
        """Clear the audio buffer (on interrupt)."""
        self._buffer.clear()
        self._has_audio = False

    @property
    def has_audio(self) -> bool:
        return self._has_audio and len(self._buffer) > 0

    @property
    def buffer_duration_sec(self) -> float:
        """Current buffer duration in seconds."""
        return len(self._buffer) / config.AUDIO_MODEL_SAMPLE_RATE


class PlaceholderAudioExtractor:
    """
    Fake audio extractor for testing without GPU/models.
    Returns random feature vectors when audio is pushed.
    """

    def __init__(self):
        self._has_audio = False
        self._buffer_len = 0

    def push_audio(self, raw_bytes: bytes) -> None:
        self._has_audio = True
        self._buffer_len += len(raw_bytes) // 2  # int16 = 2 bytes per sample

    def extract(self) -> np.ndarray | None:
        if not self._has_audio:
            return None
        # Return random 768-dim vector (same shape as wav2vec2 output)
        return np.random.randn(768).astype(np.float32) * 0.1

    def clear(self) -> None:
        self._has_audio = False
        self._buffer_len = 0

    @property
    def has_audio(self) -> bool:
        return self._has_audio

    @property
    def buffer_duration_sec(self) -> float:
        return self._buffer_len / config.AUDIO_INPUT_SAMPLE_RATE


class ChunkAudioAccumulator:
    """
    Audio accumulator for FlashHead full pipeline.

    Collects raw audio from TTS (24kHz int16), resamples to 16kHz float32,
    and stores in a sliding deque matching FlashHead's streaming pattern.
    Signals when enough audio for one chunk (~1.1s) has accumulated.

    FlashHead's pipeline handles its own wav2vec2 extraction internally —
    we just feed it raw 16kHz float32 audio arrays.

    Pattern from: SoulX-FlashHead/gradio_app_streaming.py
    """

    def __init__(self):
        # Sliding deque of 16kHz float32 samples (8 seconds max context)
        max_samples = config.FLASHHEAD_CACHED_AUDIO_DURATION * config.AUDIO_MODEL_SAMPLE_RATE
        self._audio_deque = collections.deque(maxlen=max_samples)

        # Track new samples since last chunk was consumed
        self._new_samples = 0
        self._total_samples_pushed = 0
        self._has_audio = False

    def push_audio(self, raw_bytes: bytes) -> None:
        """
        Push raw audio from TTS (24kHz int16 PCM).
        Resamples to 16kHz float32 and appends to sliding deque.
        """
        # Convert bytes → int16 → float32 normalized
        audio_int16 = np.frombuffer(raw_bytes, dtype=np.int16)
        audio_f32 = audio_int16.astype(np.float32) / 32768.0

        # Resample 24kHz → 16kHz (simple decimation for speed)
        # Ratio: 16000/24000 = 2/3 — take every 3rd sample pair
        # For production quality, use torchaudio sinc resampler
        try:
            torch = _ensure_torch()
            resampler = _ensure_resampler()
            tensor = torch.from_numpy(audio_f32)
            resampled = resampler(tensor).numpy()
        except Exception:
            # Fallback: linear interpolation resample
            ratio = config.AUDIO_MODEL_SAMPLE_RATE / config.AUDIO_INPUT_SAMPLE_RATE
            n_out = int(len(audio_f32) * ratio)
            indices = np.linspace(0, len(audio_f32) - 1, n_out)
            resampled = np.interp(indices, np.arange(len(audio_f32)), audio_f32)

        self._audio_deque.extend(resampled.tolist())
        self._new_samples += len(resampled)
        self._total_samples_pushed += len(resampled)
        self._has_audio = True

    def has_chunk_ready(self) -> bool:
        """True when enough new audio has arrived for one FlashHead chunk."""
        return self._new_samples >= config.FLASHHEAD_CHUNK_AUDIO_SAMPLES

    def consume_chunk(self) -> np.ndarray:
        """
        Return the full audio context as a numpy array for FlashHead.
        Resets the new-sample counter so has_chunk_ready() goes False
        until enough new audio arrives for the next chunk.

        Returns:
            float32 numpy array of the entire deque (up to 8s of audio context).
            FlashHead's get_audio_embedding() handles windowing internally.
        """
        self._new_samples = 0
        return np.array(list(self._audio_deque), dtype=np.float32)

    def clear(self) -> None:
        """Clear all audio (on interrupt)."""
        self._audio_deque.clear()
        self._new_samples = 0
        self._total_samples_pushed = 0
        self._has_audio = False
        logger.debug("ChunkAudioAccumulator cleared")

    @property
    def has_audio(self) -> bool:
        return self._has_audio and len(self._audio_deque) > 0

    @property
    def buffer_duration_sec(self) -> float:
        """Current buffer duration in seconds."""
        return len(self._audio_deque) / config.AUDIO_MODEL_SAMPLE_RATE

    @property
    def new_audio_duration_sec(self) -> float:
        """Duration of new (unconsumed) audio in seconds."""
        return self._new_samples / config.AUDIO_MODEL_SAMPLE_RATE
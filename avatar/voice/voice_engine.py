"""
CHAMP Avatar — Dual-Engine Voice Router

Routes voice synthesis to the best engine for each request:

  English + emotion needed  → Orpheus TTS (25ms, <laugh>/<sigh> tags)
  English + clone           → Qwen3-TTS ICL (97ms, 0.95+ SECS)
  Multilingual + clone      → Qwen3-TTS ICL (97ms, 10 languages)
  Designed voice            → Qwen3-TTS VoiceDesign
  Fallback                  → Placeholder (testing)

Both engines implement the same interface:
  synthesize(text, voice_profile) → WAV path

Implements VoiceInterface from avatar/studio/render_job.py
so it can be used directly for async video rendering.
"""

import logging
import os
import tempfile
import time
from enum import Enum
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

from .. import config

logger = logging.getLogger("champ.avatar.voice.engine")


class VoiceMode(Enum):
    """Which voice engine to use."""
    CLONE = "clone"       # Cloned from real person (Qwen3-TTS ICL)
    DESIGN = "design"     # AI-designed voice (Qwen3-TTS VoiceDesign)
    EMOTION = "emotion"   # Emotional English (Orpheus TTS)
    AUTO = "auto"         # Automatic routing based on profile


@dataclass
class VoiceEngineConfig:
    """Configuration for the dual-engine voice system."""
    # Qwen3-TTS settings
    qwen_model: str = "Qwen/Qwen3-TTS-12Hz-1.7B-Base"
    qwen_temperature: float = 0.3
    qwen_best_of_n: int = 12       # ClipCannon best-of-N selection
    qwen_sample_rate: int = 16000

    # Orpheus settings
    orpheus_model: str = "canopylabs/orpheus-tts-0.1-finetune-prod"
    orpheus_sample_rate: int = 24000

    # Shared settings
    output_format: str = "wav"      # WAV 16-bit PCM
    output_sample_rate: int = 16000  # Avatar pipeline expects 16kHz
    max_text_length: int = 5000     # Max characters per synthesis call

    # Quality gates (ClipCannon pattern)
    secs_threshold: float = 0.85    # Min speaker similarity score
    wer_threshold: float = 0.15     # Max word error rate
    duration_ratio_range: tuple = (0.8, 1.5)  # Expected vs actual duration


class VoiceEngine:
    """
    Dual-engine voice synthesizer for Live Creatiq Operators.

    Implements VoiceInterface so it can be passed directly to RenderJob
    for async video rendering, AND used in live calls via LiveKit.

    Usage:
        engine = VoiceEngine()

        # Load a voice profile
        from avatar.voice import VoiceRegistry
        registry = VoiceRegistry()
        profile = registry.get_profile("anthony")

        # Synthesize (auto-routes to best engine)
        wav_path = engine.synthesize("Hello, welcome!", profile)

        # Synthesize with emotion (Orpheus)
        wav_path = engine.synthesize(
            "That's <laugh> amazing news!",
            profile,
            mode=VoiceMode.EMOTION,
        )

        # Streaming synthesis (for live calls)
        async for chunk in engine.synthesize_stream("Hello!", profile):
            livekit_audio_track.push(chunk)
    """

    def __init__(self, engine_config: Optional[VoiceEngineConfig] = None):
        self._config = engine_config or VoiceEngineConfig()
        self._qwen_model = None
        self._orpheus_model = None
        self._qwen_available = False
        self._orpheus_available = False

    def synthesize(
        self,
        text: str,
        voice_profile: "VoiceProfile",
        mode: VoiceMode = VoiceMode.AUTO,
        output_path: Optional[str] = None,
    ) -> str:
        """
        Synthesize speech from text using the appropriate engine.

        This is the VoiceInterface-compatible method:
          synthesize(text, voice_config) → path to WAV file

        Args:
            text: Text to speak
            voice_profile: Operator's voice profile (from VoiceRegistry)
            mode: Force a specific engine, or AUTO for routing
            output_path: Where to save WAV (auto-generated if None)

        Returns:
            Path to output WAV file (16kHz mono 16-bit PCM)
        """
        if not text.strip():
            raise ValueError("Empty text")

        if len(text) > self._config.max_text_length:
            logger.warning(f"Text truncated from {len(text)} to {self._config.max_text_length}")
            text = text[:self._config.max_text_length]

        # Route to engine
        engine = self._route(text, voice_profile, mode)

        # Generate output path
        if output_path is None:
            fd, output_path = tempfile.mkstemp(suffix=".wav")
            os.close(fd)

        start_time = time.time()

        if engine == "orpheus":
            self._synthesize_orpheus(text, voice_profile, output_path)
        elif engine == "qwen3":
            self._synthesize_qwen(text, voice_profile, output_path)
        else:
            self._synthesize_placeholder(text, voice_profile, output_path)

        elapsed = time.time() - start_time
        logger.info(
            f"Synthesized ({engine}): {len(text)} chars → {output_path} "
            f"in {elapsed:.2f}s"
        )

        return output_path

    async def synthesize_stream(
        self,
        text: str,
        voice_profile: "VoiceProfile",
        mode: VoiceMode = VoiceMode.AUTO,
    ):
        """
        Streaming synthesis — yields audio chunks as they're generated.

        For live calls: feed chunks directly to LiveKit audio track.
        Latency: first chunk in 25-97ms depending on engine.

        Yields:
            numpy arrays of int16 PCM audio at 16kHz
        """
        engine = self._route(text, voice_profile, mode)

        if engine == "orpheus":
            async for chunk in self._stream_orpheus(text, voice_profile):
                yield chunk
        elif engine == "qwen3":
            async for chunk in self._stream_qwen(text, voice_profile):
                yield chunk
        else:
            # Placeholder: generate full audio then yield in chunks
            fd, tmp_path = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
            self._synthesize_placeholder(text, voice_profile, tmp_path)

            import wave
            with wave.open(tmp_path, "r") as wf:
                chunk_size = 4000  # ~250ms at 16kHz
                while True:
                    frames = wf.readframes(chunk_size)
                    if not frames:
                        break
                    yield np.frombuffer(frames, dtype=np.int16)

            os.unlink(tmp_path)

    def _route(self, text: str, voice_profile, mode: VoiceMode) -> str:
        """Route to the best engine based on profile and mode."""
        if mode == VoiceMode.EMOTION:
            if self._ensure_orpheus():
                return "orpheus"
            logger.info("Orpheus unavailable, falling back to Qwen3")

        if mode == VoiceMode.CLONE or mode == VoiceMode.DESIGN:
            if self._ensure_qwen():
                return "qwen3"

        if mode == VoiceMode.AUTO:
            # Auto-routing logic
            profile_mode = getattr(voice_profile, "mode", "clone")
            language = getattr(voice_profile, "language", "en")
            engine_pref = getattr(voice_profile, "engine", "auto")

            # Explicit engine preference
            if engine_pref == "orpheus" and language == "en":
                if self._ensure_orpheus():
                    return "orpheus"

            if engine_pref == "qwen3":
                if self._ensure_qwen():
                    return "qwen3"

            # Auto: emotion tags in text → Orpheus (English only)
            if language == "en" and self._has_emotion_tags(text):
                if self._ensure_orpheus():
                    return "orpheus"

            # Auto: clone/design → Qwen3
            if self._ensure_qwen():
                return "qwen3"

            # Fallback: Orpheus for English if Qwen unavailable
            if language == "en" and self._ensure_orpheus():
                return "orpheus"

        return "placeholder"

    def _has_emotion_tags(self, text: str) -> bool:
        """Check if text contains Orpheus emotion tags."""
        tags = ["<laugh>", "<sigh>", "<chuckle>", "<gasp>", "<cough>",
                "<sniffle>", "<groan>", "<yawn>", "<hmm>"]
        return any(tag in text.lower() for tag in tags)

    # ─── Qwen3-TTS Engine ───────────────────────────────────────────────

    def _ensure_qwen(self) -> bool:
        """Lazy-load Qwen3-TTS model."""
        if self._qwen_available:
            return True

        try:
            from qwen_tts import QwenTTS
            self._qwen_model = QwenTTS.from_pretrained(self._config.qwen_model)
            self._qwen_available = True
            logger.info(f"Qwen3-TTS loaded: {self._config.qwen_model}")
            return True
        except ImportError:
            logger.info("qwen-tts package not installed (pip install qwen-tts)")
            return False
        except Exception as e:
            logger.warning(f"Qwen3-TTS load failed: {e}")
            return False

    def _synthesize_qwen(self, text: str, voice_profile, output_path: str):
        """Synthesize using Qwen3-TTS with ClipCannon scoring."""
        ref_audio = getattr(voice_profile, "reference_audio", None)
        design_prompt = getattr(voice_profile, "design_prompt", None)

        if design_prompt and not ref_audio:
            # Design mode — voice from description
            self._qwen_model.synthesize(
                text=text,
                voice_design=design_prompt,
                output_path=output_path,
            )
        elif ref_audio:
            # Clone mode — ICL with reference audio
            # ClipCannon: best-of-N selection
            best_path = None
            best_score = -1.0

            for i in range(self._config.qwen_best_of_n):
                candidate_path = output_path + f".candidate_{i}.wav"
                self._qwen_model.synthesize(
                    text=text,
                    reference_audio=ref_audio,
                    output_path=candidate_path,
                    temperature=self._config.qwen_temperature,
                )

                score = self._score_candidate(candidate_path, voice_profile)
                if score > best_score:
                    best_score = score
                    best_path = candidate_path

            # Copy best candidate to output
            import shutil
            if best_path:
                shutil.move(best_path, output_path)

            # Clean up other candidates
            for i in range(self._config.qwen_best_of_n):
                candidate_path = output_path + f".candidate_{i}.wav"
                if os.path.exists(candidate_path):
                    os.unlink(candidate_path)
        else:
            # No reference — use default voice
            self._qwen_model.synthesize(
                text=text,
                output_path=output_path,
            )

    async def _stream_qwen(self, text: str, voice_profile):
        """Streaming Qwen3-TTS synthesis."""
        ref_audio = getattr(voice_profile, "reference_audio", None)

        try:
            stream = self._qwen_model.synthesize_stream(
                text=text,
                reference_audio=ref_audio,
                temperature=self._config.qwen_temperature,
            )

            for chunk in stream:
                yield chunk

        except Exception as e:
            logger.warning(f"Qwen3 streaming failed ({e}), falling back to batch")
            fd, tmp = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
            self._synthesize_qwen(text, voice_profile, tmp)

            import wave
            with wave.open(tmp, "r") as wf:
                while True:
                    frames = wf.readframes(4000)
                    if not frames:
                        break
                    yield np.frombuffer(frames, dtype=np.int16)
            os.unlink(tmp)

    # ─── Orpheus TTS Engine ──────────────────────────────────────────────

    def _ensure_orpheus(self) -> bool:
        """Lazy-load Orpheus TTS model."""
        if self._orpheus_available:
            return True

        try:
            from orpheus_speech import OrpheusModel
            self._orpheus_model = OrpheusModel(model_name=self._config.orpheus_model)
            self._orpheus_available = True
            logger.info(f"Orpheus TTS loaded: {self._config.orpheus_model}")
            return True
        except ImportError:
            logger.info("orpheus-speech package not installed (pip install orpheus-speech)")
            return False
        except Exception as e:
            logger.warning(f"Orpheus TTS load failed: {e}")
            return False

    def _synthesize_orpheus(self, text: str, voice_profile, output_path: str):
        """Synthesize using Orpheus TTS with emotion support."""
        import wave

        # Orpheus generates audio with emotion tags inline
        audio_chunks = self._orpheus_model.generate(text=text)

        # Concatenate chunks and save as WAV
        all_audio = np.concatenate(list(audio_chunks))

        with wave.open(output_path, "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self._config.orpheus_sample_rate)
            wf.writeframes(all_audio.astype(np.int16).tobytes())

        # Resample to 16kHz if needed
        if self._config.orpheus_sample_rate != self._config.output_sample_rate:
            self._resample_wav(output_path, self._config.output_sample_rate)

    async def _stream_orpheus(self, text: str, voice_profile):
        """Streaming Orpheus TTS synthesis."""
        try:
            stream = self._orpheus_model.generate_stream(text=text)
            for chunk in stream:
                yield chunk.astype(np.int16)
        except Exception as e:
            logger.warning(f"Orpheus streaming failed ({e})")

    # ─── Quality Scoring (ClipCannon) ────────────────────────────────────

    def _score_candidate(self, candidate_path: str, voice_profile) -> float:
        """
        Score a TTS candidate using WavLM speaker similarity.
        ClipCannon pattern: higher score = closer to reference voice.
        """
        centroid_path = getattr(voice_profile, "centroid_path", None)
        if not centroid_path or not os.path.exists(centroid_path):
            return np.random.random()  # Random score if no centroid

        try:
            import torch
            import torchaudio
            from transformers import Wav2Vec2FeatureExtractor, WavLMForXVector

            centroid = np.load(centroid_path)

            model_name = "microsoft/wavlm-base-plus-sv"
            feature_extractor = Wav2Vec2FeatureExtractor.from_pretrained(model_name)
            model = WavLMForXVector.from_pretrained(model_name)
            model.eval()

            waveform, sr = torchaudio.load(candidate_path)
            if sr != 16000:
                waveform = torchaudio.functional.resample(waveform, sr, 16000)

            inputs = feature_extractor(
                waveform.squeeze().numpy(),
                sampling_rate=16000,
                return_tensors="pt",
            )

            with torch.no_grad():
                embedding = model(**inputs).embeddings.cpu().numpy().flatten()
                embedding = embedding / (np.linalg.norm(embedding) + 1e-8)

            return float(np.dot(embedding, centroid))

        except Exception as e:
            logger.debug(f"WavLM scoring failed: {e}")
            return np.random.random()

    # ─── Utilities ───────────────────────────────────────────────────────

    def _resample_wav(self, wav_path: str, target_sr: int):
        """Resample WAV file to target sample rate."""
        try:
            import torchaudio
            waveform, sr = torchaudio.load(wav_path)
            if sr != target_sr:
                waveform = torchaudio.functional.resample(waveform, sr, target_sr)
                torchaudio.save(wav_path, waveform, target_sr)
        except ImportError:
            # Fallback: use scipy
            try:
                from scipy.io import wavfile
                from scipy.signal import resample

                sr, data = wavfile.read(wav_path)
                if sr != target_sr:
                    ratio = target_sr / sr
                    new_length = int(len(data) * ratio)
                    resampled = resample(data, new_length).astype(np.int16)
                    wavfile.write(wav_path, target_sr, resampled)
            except ImportError:
                logger.warning("Cannot resample — no torchaudio or scipy")

    def _synthesize_placeholder(self, text: str, voice_profile, output_path: str):
        """Placeholder synthesis for testing without TTS models."""
        import wave

        sample_rate = self._config.output_sample_rate
        # ~100ms per word
        words = len(text.split())
        duration_sec = max(1.0, words * 0.1)
        num_samples = int(sample_rate * duration_sec)

        # Generate simple sine wave at ~200Hz (rough voice pitch)
        t = np.linspace(0, duration_sec, num_samples, dtype=np.float32)
        frequency = 200 + hash(text) % 100  # Slight variation per text
        audio = np.sin(2 * np.pi * frequency * t) * 3000

        # Add slight noise for realism
        audio += np.random.randn(num_samples) * 100

        audio = audio.astype(np.int16)

        with wave.open(output_path, "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(audio.tobytes())

    @property
    def available_engines(self) -> list[str]:
        """List currently available engines."""
        engines = ["placeholder"]
        if self._qwen_available:
            engines.append("qwen3")
        if self._orpheus_available:
            engines.append("orpheus")
        return engines

    @property
    def stats(self) -> dict:
        return {
            "qwen3_available": self._qwen_available,
            "orpheus_available": self._orpheus_available,
            "qwen_model": self._config.qwen_model,
            "orpheus_model": self._config.orpheus_model,
            "best_of_n": self._config.qwen_best_of_n,
            "output_sample_rate": self._config.output_sample_rate,
        }

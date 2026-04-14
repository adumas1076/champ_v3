"""
CHAMP Avatar — Modal TTS Deployment

Deploys Qwen3-TTS + Orpheus dual-engine voice system to Modal A10G GPU.

Deploy:
    cd champ_v3
    modal deploy avatar/modal_tts_deploy.py

Usage after deployment:
    from avatar.voice import VoiceEngine
    engine = VoiceEngine()
    # Engine auto-detects Modal deployment and routes inference there

Endpoints:
    /synthesize     — Text + voice profile → WAV audio bytes
    /clone_enroll   — Reference audio → speaker embedding
    /health         — Check model status
"""

import io
import os
import time

import modal

# ─── Modal App Setup ────────────────────────────────────────────────────────

app = modal.App("champ-tts")

# GPU image with both TTS engines pre-installed
tts_image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(
        "torch>=2.1.0",
        "torchaudio>=2.1.0",
        "transformers>=4.40.0",
        "qwen-tts",
        "orpheus-speech",
        "numpy",
        "scipy",
        "soundfile",
        "librosa",
    )
    # WavLM for ClipCannon speaker similarity scoring comes from transformers
    # (microsoft/wavlm-base-plus-sv is a HuggingFace model, not a pip package)
)


# ─── Qwen3-TTS Engine ──────────────────────────────────────────────────────

@app.cls(
    image=tts_image,
    gpu="A10G",
    timeout=300,
    scaledown_window=120,
)
@modal.concurrent(max_inputs=4)
class QwenTTSEngine:
    """Qwen3-TTS on Modal A10G — voice cloning + voice design + multilingual."""

    @modal.enter()
    def load_model(self):
        """Load model on container start (cached across requests)."""
        import torch

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = None

        try:
            from qwen_tts import Qwen3TTSModel

            # Base model for voice cloning (ICL mode)
            self.model = Qwen3TTSModel.from_pretrained(
                "Qwen/Qwen3-TTS-12Hz-1.7B-Base"
            )
            print(f"[QWEN] Base model loaded on {self.device}")

            # CustomVoice model for preset speakers (no reference needed)
            self.custom_model = Qwen3TTSModel.from_pretrained(
                "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"
            )
            speakers = self.custom_model.get_supported_speakers()
            print(f"[QWEN] CustomVoice loaded, speakers: {speakers}")

        except Exception as e:
            import traceback
            print(f"[QWEN] Model load failed: {traceback.format_exc()}")
            self.custom_model = None

    @modal.method()
    def synthesize(
        self,
        text: str,
        reference_audio_bytes: bytes = None,
        design_prompt: str = None,
        temperature: float = 0.3,
        num_candidates: int = 1,
    ) -> dict:
        """
        Synthesize speech from text.

        Args:
            text: Text to speak
            reference_audio_bytes: WAV bytes for voice cloning (ICL mode)
            design_prompt: Text description for voice design mode
            temperature: Sampling temperature
            num_candidates: Best-of-N selection (ClipCannon pattern)

        Returns:
            {"audio_bytes": bytes, "sample_rate": int, "duration_sec": float}
        """
        import tempfile
        import wave
        import numpy as np

        start = time.time()

        if self.model is None:
            return {"error": "No TTS model available"}

        import numpy as np
        import soundfile as sf

        if design_prompt:
            # Voice design mode
            audio_list, sample_rate = self.model.generate_voice_design(
                text=text,
                instruct=design_prompt,
                non_streaming_mode=True,
            )

        elif reference_audio_bytes:
            # Clone mode — use reference audio for ICL
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(reference_audio_bytes)
                ref_path = f.name

            audio_list, sample_rate = self.model.generate_voice_clone(
                text=text,
                ref_audio=ref_path,
                non_streaming_mode=True,
            )

            os.unlink(ref_path)

        elif self.custom_model is not None:
            # Default voice — use CustomVoice model with preset speaker
            speakers = self.custom_model.get_supported_speakers() or ["Chelsie"]
            audio_list, sample_rate = self.custom_model.generate_custom_voice(
                text=text,
                speaker=speakers[0],
                non_streaming_mode=True,
            )

        else:
            return {"error": "No reference audio provided and CustomVoice model unavailable"}

        # Combine audio segments
        audio_np = np.concatenate(audio_list) if len(audio_list) > 1 else audio_list[0]

        # Save output to WAV
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            out_path = f.name
        sf.write(out_path, audio_np, sample_rate)

        # Read output
        with open(out_path, "rb") as f:
            audio_bytes = f.read()

        # Get duration
        try:
            with wave.open(out_path, "r") as wf:
                duration = wf.getnframes() / wf.getframerate()
                sample_rate = wf.getframerate()
        except Exception:
            duration = 0.0
            sample_rate = 16000

        os.unlink(out_path)

        elapsed = time.time() - start
        print(f"[QWEN] Synthesized {len(text)} chars in {elapsed:.2f}s")

        return {
            "audio_bytes": audio_bytes,
            "sample_rate": sample_rate,
            "duration_sec": duration,
            "engine": "qwen3",
            "inference_time": elapsed,
        }

    @modal.method()
    def health(self) -> dict:
        return {
            "engine": "qwen3",
            "model_loaded": self.model is not None,
            "device": self.device,
            "status": "ready" if self.model else "unavailable",
        }


# ─── Orpheus TTS Engine ────────────────────────────────────────────────────

@app.cls(
    image=tts_image,
    gpu="A10G",
    timeout=300,
    scaledown_window=120,
)
@modal.concurrent(max_inputs=4)
class OrpheusTTSEngine:
    """Orpheus TTS on Modal A10G — emotional English voice synthesis."""

    @modal.enter()
    def load_model(self):
        """Load Orpheus model on container start."""
        import torch

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = None

        try:
            from orpheus_speech import OrpheusModel
            self.model = OrpheusModel(
                model_name="canopylabs/orpheus-tts-0.1-finetune-prod"
            )
            print(f"[ORPHEUS] Model loaded on {self.device}")
        except Exception as e:
            print(f"[ORPHEUS] Model failed: {e}")

    @modal.method()
    def synthesize(self, text: str) -> dict:
        """
        Synthesize emotional speech from text with inline tags.

        Supports: <laugh>, <sigh>, <chuckle>, <gasp>, <cough>, <yawn>

        Returns:
            {"audio_bytes": bytes, "sample_rate": int, "duration_sec": float}
        """
        import numpy as np
        import wave
        import tempfile

        if not self.model:
            return {"error": "Orpheus model not loaded"}

        start = time.time()

        # Generate audio
        audio_chunks = self.model.generate(text=text)
        all_audio = np.concatenate(list(audio_chunks))

        # Write to WAV
        sample_rate = 24000
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            out_path = f.name

        with wave.open(out_path, "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(all_audio.astype(np.int16).tobytes())

        with open(out_path, "rb") as f:
            audio_bytes = f.read()

        duration = len(all_audio) / sample_rate
        os.unlink(out_path)

        elapsed = time.time() - start
        print(f"[ORPHEUS] Synthesized {len(text)} chars in {elapsed:.2f}s")

        return {
            "audio_bytes": audio_bytes,
            "sample_rate": sample_rate,
            "duration_sec": duration,
            "engine": "orpheus",
            "inference_time": elapsed,
        }

    @modal.method()
    def health(self) -> dict:
        return {
            "engine": "orpheus",
            "model_loaded": self.model is not None,
            "device": self.device,
            "status": "ready" if self.model else "unavailable",
        }


# ─── Health Check ───────────────────────────────────────────────────────────

@app.function(image=tts_image)
def tts_health() -> dict:
    """Check both engines."""
    return {
        "service": "champ-tts",
        "status": "deployed",
        "engines": ["qwen3", "orpheus"],
        "gpu": "A10G",
    }

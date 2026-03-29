"""
CHAMP Avatar Studio — Render Job

Orchestrates async video generation:
  Script text + avatar_id + voice config -> rendered MP4

Pipeline:
  1. Load avatar reference (multi-ref keyframes + optional LoRA)
  2. Generate audio from script (via pluggable voice interface)
  3. Chunk audio into FlashHead segments
  4. Generate video frames per chunk via GPU backend
  5. Optionally upscale frames (Real-ESRGAN)
  6. Optionally composite with body template
  7. Assemble frames + audio into final MP4

Usage:
    job = RenderJob(
        script="Hello, welcome to our product demo.",
        avatar_id="anthony",
    )
    result = await job.run()
    print(result.video_path)  # "renders/job_abc123/final.mp4"
"""

import asyncio
import json
import logging
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Optional, Callable

import numpy as np

from .. import config
from ..gpu_backend import GPUBackend, create_backend
from ..upscale import FrameUpscaler
from ..body.gesture_predictor import GesturePredictor
from ..body.body_compositor import BodyCompositor
from .video_assembler import VideoAssembler, AssemblyConfig

logger = logging.getLogger("champ.avatar.studio.render")


class RenderStatus(Enum):
    PENDING = "pending"
    GENERATING_AUDIO = "generating_audio"
    RENDERING_FRAMES = "rendering_frames"
    UPSCALING = "upscaling"
    COMPOSITING = "compositing"
    ASSEMBLING = "assembling"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class RenderConfig:
    """Configuration for a render job."""
    # Video
    width: int = config.VIDEO_WIDTH                  # 512 base
    height: int = config.VIDEO_HEIGHT                # 512 base
    fps: float = config.VIDEO_FPS                    # 25
    upscale: bool = False                            # Real-ESRGAN upscale
    upscale_factor: int = config.VIDEO_UPSCALE_FACTOR  # 2 or 4
    # Body
    include_body: bool = False                       # Composite with body template
    # Assembly
    video_codec: str = "libx264"
    crf: int = 18
    # Output
    output_format: str = "mp4"


@dataclass
class RenderResult:
    """Result of a completed render job."""
    job_id: str
    video_path: str
    thumbnail_path: Optional[str]
    duration_sec: float
    frame_count: int
    resolution: str                                  # e.g. "2048x2048"
    file_size_bytes: int
    render_time_sec: float
    status: RenderStatus


@dataclass
class RenderProgress:
    """Progress update for a render job."""
    status: RenderStatus
    progress: float                                  # 0.0 to 1.0
    message: str
    frames_rendered: int = 0
    total_frames: int = 0


class VoiceInterface:
    """
    Pluggable voice synthesis interface.

    The main session implements the actual TTS (Qwen3-TTS, OpenAI, etc).
    This class defines the contract the render job expects.

    To use: subclass and implement synthesize(), or pass a callable.
    """

    def synthesize(self, text: str, voice_config: dict) -> str:
        """
        Synthesize speech from text.

        Args:
            text: Script text to speak
            voice_config: Voice parameters (voice_id, speed, pitch, etc.)

        Returns:
            Path to generated WAV file (16kHz mono float32)
        """
        raise NotImplementedError(
            "VoiceInterface.synthesize() must be implemented. "
            "The main session should provide a TTS implementation. "
            "See avatar/voice_spec.py for the interface contract."
        )


class FallbackVoice(VoiceInterface):
    """
    Generates silence as audio — for testing renders without a real TTS.
    Produces a WAV of the right duration based on estimated speaking speed.
    """

    def __init__(self, words_per_minute: float = 150):
        self.wpm = words_per_minute

    def synthesize(self, text: str, voice_config: dict) -> str:
        """Generate silent WAV of estimated duration."""
        import tempfile
        import wave

        word_count = len(text.split())
        duration_sec = max(1.0, (word_count / self.wpm) * 60)
        sample_rate = config.AUDIO_MODEL_SAMPLE_RATE
        n_samples = int(duration_sec * sample_rate)

        # Generate very low-level noise (not pure silence, so FlashHead has something)
        audio = np.random.randn(n_samples).astype(np.float32) * 0.001
        audio_int16 = (audio * 32767).astype(np.int16)

        filepath = tempfile.mktemp(suffix=".wav", prefix="champ_tts_")
        with wave.open(filepath, "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(audio_int16.tobytes())

        logger.debug(f"FallbackVoice: {duration_sec:.1f}s silence for {word_count} words")
        return filepath


class RenderJob:
    """
    Orchestrates a complete async video render.

    Usage:
        job = RenderJob(script="Hello world", avatar_id="anthony")
        result = await job.run()
    """

    def __init__(
        self,
        script: str,
        avatar_id: str,
        voice: Optional[VoiceInterface] = None,
        voice_config: Optional[dict] = None,
        render_config: Optional[RenderConfig] = None,
        output_dir: Optional[str] = None,
        on_progress: Optional[Callable[[RenderProgress], None]] = None,
    ):
        self.job_id = str(uuid.uuid4())[:8]
        self.script = script
        self.avatar_id = avatar_id
        self.voice = voice or FallbackVoice()
        self.voice_config = voice_config or {}
        self.render_config = render_config or RenderConfig()
        self.output_dir = Path(output_dir) if output_dir else Path("renders") / f"job_{self.job_id}"
        self.on_progress = on_progress

        self._status = RenderStatus.PENDING
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="render")

    def _update_progress(self, status: RenderStatus, progress: float, message: str, **kwargs):
        self._status = status
        if self.on_progress:
            self.on_progress(RenderProgress(
                status=status, progress=progress, message=message, **kwargs
            ))
        logger.info(f"  [{self.job_id}] {status.value}: {message} ({progress*100:.0f}%)")

    async def run(self) -> RenderResult:
        """Run the full render pipeline."""
        t_start = time.monotonic()
        self.output_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Step 1: Generate audio from script
            self._update_progress(RenderStatus.GENERATING_AUDIO, 0.05, "Synthesizing voice...")
            audio_path = await self._generate_audio()

            # Step 2: Load audio and chunk it
            audio_array = self._load_audio(audio_path)
            chunks = self._chunk_audio(audio_array)
            total_frames_est = len(chunks) * config.FLASHHEAD_USABLE_FRAMES

            # Step 3: Initialize GPU backend
            self._update_progress(RenderStatus.RENDERING_FRAMES, 0.10, "Loading avatar model...")
            gpu_backend = create_backend(mode=config.GPU_BACKEND)

            # Get reference path from registry
            from ..training.avatar_registry import AvatarRegistry
            registry = AvatarRegistry()
            reference_path = registry.get_reference_path(self.avatar_id)

            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(
                self._executor,
                gpu_backend.initialize,
                reference_path,
                self.avatar_id,
            )

            if not success:
                raise RuntimeError("GPU backend failed to initialize")

            # Step 4: Render frames chunk by chunk
            all_frames = []
            frames_dir = self.output_dir / "frames"
            frames_dir.mkdir(exist_ok=True)

            for i, audio_chunk in enumerate(chunks):
                progress = 0.10 + (0.60 * (i / len(chunks)))
                self._update_progress(
                    RenderStatus.RENDERING_FRAMES, progress,
                    f"Rendering chunk {i+1}/{len(chunks)}...",
                    frames_rendered=len(all_frames),
                    total_frames=total_frames_est,
                )

                frames = await loop.run_in_executor(
                    self._executor,
                    gpu_backend.generate_chunk,
                    audio_chunk,
                )
                all_frames.extend(frames)

            gpu_backend.close()

            # Step 5: Upscale if requested
            if self.render_config.upscale:
                self._update_progress(RenderStatus.UPSCALING, 0.72, "Upscaling frames...")
                upscaler = FrameUpscaler(scale=self.render_config.upscale_factor)
                await loop.run_in_executor(self._executor, upscaler.load)
                all_frames = [upscaler.upscale(f) for f in all_frames]

            # Step 6: Body composite if requested
            if self.render_config.include_body:
                self._update_progress(RenderStatus.COMPOSITING, 0.80, "Adding body...")
                predictor = GesturePredictor()
                compositor = BodyCompositor()

                composited = []
                for i, frame in enumerate(all_frames):
                    # Predict gesture from corresponding audio chunk
                    chunk_idx = min(i // config.FLASHHEAD_USABLE_FRAMES, len(chunks) - 1)
                    gesture = predictor.predict(chunks[chunk_idx])
                    composited.append(compositor.composite(frame, gesture=gesture))
                all_frames = composited

            # Step 7: Save frames to disk
            self._update_progress(RenderStatus.ASSEMBLING, 0.85, "Saving frames...")
            from PIL import Image
            for i, frame in enumerate(all_frames):
                if frame.shape[2] == 4:
                    img = Image.fromarray(frame, "RGBA").convert("RGB")
                else:
                    img = Image.fromarray(frame, "RGB")
                img.save(str(frames_dir / f"frame_{i:03d}.png"))

            # Step 8: Assemble MP4
            self._update_progress(RenderStatus.ASSEMBLING, 0.90, "Encoding MP4...")
            output_path = str(self.output_dir / f"video.{self.render_config.output_format}")

            assembly_cfg = AssemblyConfig(
                fps=self.render_config.fps,
                video_codec=self.render_config.video_codec,
                crf=self.render_config.crf,
            )

            if self.render_config.upscale:
                assembly_cfg.output_width = config.VIDEO_WIDTH * self.render_config.upscale_factor
                assembly_cfg.output_height = config.VIDEO_HEIGHT * self.render_config.upscale_factor

            assembler = VideoAssembler(assembly_cfg)
            video_path = assembler.assemble(
                frames_dir=str(frames_dir),
                audio_path=audio_path,
                output_path=output_path,
            )

            # Step 9: Extract thumbnail
            thumb_path = str(self.output_dir / "thumbnail.jpg")
            try:
                assembler.extract_thumbnail(video_path, thumb_path)
            except Exception:
                thumb_path = None

            # Step 10: Save job metadata
            render_time = time.monotonic() - t_start
            frame_h, frame_w = all_frames[0].shape[:2] if all_frames else (0, 0)

            result = RenderResult(
                job_id=self.job_id,
                video_path=video_path,
                thumbnail_path=thumb_path,
                duration_sec=len(all_frames) / self.render_config.fps,
                frame_count=len(all_frames),
                resolution=f"{frame_w}x{frame_h}",
                file_size_bytes=os.path.getsize(video_path) if os.path.exists(video_path) else 0,
                render_time_sec=render_time,
                status=RenderStatus.COMPLETE,
            )

            # Save metadata
            meta_path = self.output_dir / "metadata.json"
            with open(meta_path, "w") as f:
                meta = asdict(result)
                meta["status"] = result.status.value
                meta["script"] = self.script
                meta["avatar_id"] = self.avatar_id
                json.dump(meta, f, indent=2)

            self._update_progress(RenderStatus.COMPLETE, 1.0,
                                  f"Done! {len(all_frames)} frames, {render_time:.1f}s render time")

            return result

        except Exception as e:
            self._update_progress(RenderStatus.FAILED, 0.0, f"Failed: {e}")
            raise

        finally:
            self._executor.shutdown(wait=False)

    async def _generate_audio(self) -> str:
        """Generate TTS audio from script."""
        audio_path = str(self.output_dir / "audio.wav")

        # Voice synthesis (may be async in real implementation)
        if asyncio.iscoroutinefunction(getattr(self.voice, 'synthesize', None)):
            result = await self.voice.synthesize(self.script, self.voice_config)
        else:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self._executor,
                self.voice.synthesize,
                self.script,
                self.voice_config,
            )

        # Copy or move to output dir if needed
        if result != audio_path:
            import shutil
            shutil.copy2(result, audio_path)

        return audio_path

    def _load_audio(self, audio_path: str) -> np.ndarray:
        """Load audio as float32 numpy array at 16kHz."""
        import wave
        with wave.open(audio_path, "r") as wf:
            n_frames = wf.getnframes()
            raw = wf.readframes(n_frames)
            audio_int16 = np.frombuffer(raw, dtype=np.int16)
            return audio_int16.astype(np.float32) / 32768.0

    def _chunk_audio(self, audio_array: np.ndarray) -> list[np.ndarray]:
        """Split audio into FlashHead-sized chunks."""
        chunk_samples = config.FLASHHEAD_CHUNK_AUDIO_SAMPLES
        chunks = []

        for start in range(0, len(audio_array), chunk_samples):
            chunk = audio_array[start:start + chunk_samples]
            if len(chunk) < chunk_samples // 2:
                break  # Skip very short tail chunk
            # Pad if needed
            if len(chunk) < chunk_samples:
                chunk = np.pad(chunk, (0, chunk_samples - len(chunk)))
            chunks.append(chunk)

        return chunks


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Render avatar video from script")
    parser.add_argument("--script", required=True, help="Text script for the video")
    parser.add_argument("--avatar-id", required=True, help="Avatar identifier")
    parser.add_argument("--output", default=None, help="Output directory")
    parser.add_argument("--upscale", action="store_true", help="Enable 4K upscaling")
    parser.add_argument("--body", action="store_true", help="Include body composite")
    args = parser.parse_args()

    render_config = RenderConfig(
        upscale=args.upscale,
        include_body=args.body,
    )

    job = RenderJob(
        script=args.script,
        avatar_id=args.avatar_id,
        render_config=render_config,
        output_dir=args.output,
    )

    result = asyncio.run(job.run())
    print(f"\nRender complete:")
    print(f"  Video: {result.video_path}")
    print(f"  Duration: {result.duration_sec:.1f}s")
    print(f"  Frames: {result.frame_count}")
    print(f"  Resolution: {result.resolution}")
    print(f"  Render time: {result.render_time_sec:.1f}s")

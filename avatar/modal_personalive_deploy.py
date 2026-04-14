"""
CHAMP Avatar — PersonaLive Modal Deployment

Deploys PersonaLive streaming diffusion to Modal A10G GPU.
Single photo → real animated video frames → WebSocket to browser.

Deploy:
    modal deploy avatar/modal_personalive_deploy.py

Then call:
    POST /animate  — reference image + driving frame → animated output frame
    POST /init     — load reference identity (run once per session)
    GET  /health   — check status
"""

import io
import os
import time
import base64

import modal

app = modal.App("champ-personalive")

# Build image with PersonaLive dependencies
personalive_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg", "libgl1-mesa-glx", "libglib2.0-0", "git")
    .pip_install(
        "torch==2.1.0",
        "torchvision==0.16.0",
        "diffusers==0.27.0",
        "transformers==4.36.2",
        "accelerate==1.12.0",
        "einops==0.8.1",
        "omegaconf==2.3.0",
        "mediapipe==0.10.11",
        "opencv-python-headless==4.10.0.84",
        "Pillow",
        "numpy==1.26.3",
        "safetensors==0.7.0",
        "scikit-image==0.22.0",
        "huggingface-hub==0.25.1",
        "peft==0.10.0",
        "decord==0.6.0",
        "pydantic",
        "av",
    )
    .run_commands(
        # Download PersonaLive repo
        "cd /root && git clone --depth 1 https://github.com/GVCLab/PersonaLive.git",
        # Download all pretrained weights
        "cd /root/PersonaLive && python tools/download_weights.py",
    )
)


@app.cls(
    image=personalive_image,
    gpu="A100",  # A10G (24GB) times out loading 6 neural nets — A100 (40GB) loads them fine
    timeout=600,
    scaledown_window=300,
    memory=32768,
)
@modal.concurrent(max_inputs=1)  # One session at a time per container
class PersonaLiveEngine:
    """PersonaLive on Modal A10G — real-time streaming avatar from single photo."""

    @modal.enter()
    def setup(self):
        """Minimal setup on container start — models load on first request."""
        self.device = "cuda"
        self.pipeline = None
        self.initialized = False
        self.load_error = None
        self._loaded = False
        print("[PERSONALIVE] Container ready, models will load on first request")

    def _ensure_loaded(self):
        """Lazy-load PersonaLive pipeline on first actual request."""
        if self._loaded:
            return self.pipeline is not None

        self._loaded = True
        import sys
        import torch

        try:
            sys.path.insert(0, "/root/PersonaLive")
            os.chdir("/root/PersonaLive")

            from src.wrapper import PersonaLive

            class PLArgs:
                config_path = "./configs/prompts/personalive_online.yaml"

            self.pipeline = PersonaLive(PLArgs(), device=self.device)
            print(f"[PERSONALIVE] Pipeline loaded on {self.device}")
            return True

        except Exception as e:
            import traceback
            self.load_error = traceback.format_exc()
            print(f"[PERSONALIVE] Load failed: {self.load_error}")
            return False

    @modal.method()
    def init_reference(self, image_bytes: bytes) -> dict:
        """
        Initialize with a reference identity image.
        Run once per session — encodes identity via CLIP + Reference UNet.

        Args:
            image_bytes: PNG/JPG bytes of the reference portrait

        Returns:
            {"status": "ready", "init_time": float}
        """
        self._ensure_loaded()
        if self.pipeline is None:
            return {"status": "error", "error": f"Pipeline not loaded: {self.load_error[-300:] if self.load_error else 'unknown'}"}

        from PIL import Image

        start = time.time()

        ref_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        ref_image = ref_image.resize((512, 512), Image.LANCZOS)

        self.pipeline.reset()
        self.pipeline.fuse_reference(ref_image)
        self.initialized = True

        elapsed = time.time() - start
        print(f"[PERSONALIVE] Reference fused in {elapsed:.2f}s")

        return {"status": "ready", "init_time": elapsed}

    @modal.method()
    def animate_frame(self, driving_frame_bytes: bytes) -> dict:
        """
        Generate one animated output frame from a driving frame.

        Args:
            driving_frame_bytes: PNG/JPG bytes of driving frame (webcam or synthetic)

        Returns:
            {"frame_bytes": bytes (PNG), "inference_time": float}
        """
        self._ensure_loaded()
        if not self.initialized or self.pipeline is None:
            return {"error": "Not initialized. Call init_reference first."}

        import torch
        import numpy as np
        from PIL import Image
        import torch.nn.functional as F

        start = time.time()

        # Decode driving frame
        driving_img = Image.open(io.BytesIO(driving_frame_bytes)).convert("RGB")
        driving_np = np.array(driving_img).astype(np.float32) / 255.0
        driving_tensor = torch.from_numpy(driving_np).permute(2, 0, 1).unsqueeze(0)
        driving_tensor = driving_tensor * 2.0 - 1.0
        driving_tensor = driving_tensor.to(device=self.pipeline.device, dtype=self.pipeline.dtype)

        # Resize to 256x256 (PersonaLive's motion encoder input)
        if driving_tensor.shape[-2:] != (256, 256):
            driving_tensor = F.interpolate(
                driving_tensor, size=(256, 256), mode="bilinear", align_corners=False
            )

        # Accumulate frames (PersonaLive processes in batches of 4)
        if not hasattr(self, "_frame_buffer"):
            self._frame_buffer = []

        self._frame_buffer.append(driving_tensor)

        if len(self._frame_buffer) >= self.pipeline.temporal_window_size:
            # Process batch
            batch = torch.cat(self._frame_buffer[:self.pipeline.temporal_window_size], dim=0)
            self._frame_buffer = self._frame_buffer[self.pipeline.temporal_window_size:]

            output = self.pipeline.process_input(batch)
            # output: (B, H, W, C) numpy in [0, 1]

            last_frame = output[-1]
            last_frame = (last_frame * 255).clip(0, 255).astype(np.uint8)
        else:
            # Not enough frames yet — return reference with slight blend
            elapsed = time.time() - start
            return {
                "frame_bytes": driving_frame_bytes,  # Pass through until buffer fills
                "buffering": True,
                "buffer_count": len(self._frame_buffer),
                "needed": self.pipeline.temporal_window_size,
                "inference_time": elapsed,
            }

        # Encode output as PNG
        output_img = Image.fromarray(last_frame)
        buf = io.BytesIO()
        output_img.save(buf, format="PNG")
        frame_bytes = buf.getvalue()

        elapsed = time.time() - start
        print(f"[PERSONALIVE] Frame generated in {elapsed:.3f}s")

        return {
            "frame_bytes": frame_bytes,
            "buffering": False,
            "inference_time": elapsed,
        }

    @modal.method()
    def generate_static_avatar(self, image_bytes: bytes, num_frames: int = 8) -> dict:
        """
        Generate a short animated clip from a single photo.
        Uses the reference image as BOTH identity AND driving source.
        Creates subtle motion (breathing, blinking simulation).

        This is the simplest demo — one photo in, animated frames out.

        Returns:
            {"frames": [PNG bytes], "fps": int}
        """
        self._ensure_loaded()
        if self.pipeline is None:
            return {"error": f"Pipeline not loaded: {self.load_error[-300:] if self.load_error else 'unknown'}"}

        import torch
        import numpy as np
        from PIL import Image
        import torch.nn.functional as F

        start = time.time()

        # Load and init reference
        ref_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        ref_image = ref_image.resize((512, 512), Image.LANCZOS)

        self.pipeline.reset()
        self.pipeline.fuse_reference(ref_image)
        self.initialized = True

        # Create driving frames from the reference with slight variations
        ref_np = np.array(ref_image).astype(np.float32) / 255.0
        ref_tensor = torch.from_numpy(ref_np).permute(2, 0, 1).unsqueeze(0)
        ref_tensor = ref_tensor * 2.0 - 1.0
        ref_tensor = ref_tensor.to(device=self.pipeline.device, dtype=self.pipeline.dtype)
        ref_256 = F.interpolate(ref_tensor, size=(256, 256), mode="bilinear", align_corners=False)

        # Generate enough frames to fill the temporal buffer + output
        total_needed = self.pipeline.temporal_window_size * 2 + num_frames
        all_driving = []
        for i in range(total_needed):
            # Add subtle variation to simulate micro-motion
            noise = torch.randn_like(ref_256) * 0.005 * (i / total_needed)
            varied = ref_256 + noise
            all_driving.append(varied)

        # Process all frames
        output_frames = []
        buffer = []
        for driving in all_driving:
            buffer.append(driving)
            if len(buffer) >= self.pipeline.temporal_window_size:
                batch = torch.cat(buffer[:self.pipeline.temporal_window_size], dim=0)
                buffer = buffer[self.pipeline.temporal_window_size:]

                output = self.pipeline.process_input(batch)
                for frame in output:
                    frame_uint8 = (frame * 255).clip(0, 255).astype(np.uint8)
                    img = Image.fromarray(frame_uint8)
                    buf = io.BytesIO()
                    img.save(buf, format="PNG")
                    output_frames.append(buf.getvalue())

        # Return last N frames
        result_frames = output_frames[-num_frames:] if len(output_frames) >= num_frames else output_frames

        elapsed = time.time() - start
        print(f"[PERSONALIVE] Generated {len(result_frames)} frames in {elapsed:.1f}s")

        return {
            "frames": result_frames,
            "num_frames": len(result_frames),
            "fps": 16,
            "inference_time": elapsed,
        }

    @modal.method()
    def health(self) -> dict:
        return {
            "engine": "personalive",
            "pipeline_loaded": self.pipeline is not None,
            "initialized": self.initialized,
            "device": self.device,
            "status": "ready" if self.pipeline else "unavailable",
            "load_error": self.load_error[-500:] if self.load_error else None,
        }

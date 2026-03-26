"""
CHAMP Avatar — Modal Serverless GPU Deployment

Deploys FlashHead inference as a Modal serverless function on NVIDIA A10G GPUs.
Pay per second of compute. Auto-scales to handle concurrent avatar sessions.

Deploy:
    modal deploy avatar/modal_deploy.py

Test:
    modal run avatar/modal_deploy.py

Pattern from: Antonio's Resonance repo (chatterbox_tts.py)

Architecture:
    Client (ModalGPUBackend) → Modal Function (this file) → FlashHead on A10G
    Audio bytes sent → Video frame bytes returned
"""

import modal

# ── Modal App Configuration ──────────────────────────────────────────────────

app = modal.App("champ-avatar")

# Docker image with all FlashHead dependencies
flashhead_image = (
    modal.Image.debian_slim(python_version="3.10")
    .pip_install(
        "torch==2.7.1",
        "torchvision==0.22.1",
        "torchaudio",
        "transformers",
        "librosa",
        "imageio",
        "numpy",
        "Pillow",
        "mediapipe",
        "peft",
        extra_index_url="https://download.pytorch.org/whl/cu128",
    )
    .pip_install("flash_attn==2.8.0.post2", extra_options="--no-build-isolation")
    .run_commands("apt-get update && apt-get install -y ffmpeg")
)

# Model volume — persistent storage for model weights
model_volume = modal.Volume.from_name("champ-avatar-models", create_if_missing=True)

MODEL_DIR = "/models"
FLASHHEAD_CKPT = f"{MODEL_DIR}/SoulX-FlashHead-1_3B"
WAV2VEC_DIR = f"{MODEL_DIR}/wav2vec2-base-960h"


# ── Model Download (runs once) ──────────────────────────────────────────────

@app.function(
    image=flashhead_image,
    volumes={MODEL_DIR: model_volume},
    timeout=1800,
)
def download_models():
    """Download FlashHead + wav2vec2 models to persistent volume."""
    import subprocess
    import os

    models = [
        ("Soul-AILab/SoulX-FlashHead-1_3B", FLASHHEAD_CKPT),
        ("facebook/wav2vec2-base-960h", WAV2VEC_DIR),
    ]

    for repo, local_dir in models:
        if os.path.isdir(local_dir) and os.listdir(local_dir):
            print(f"[OK] {repo} already downloaded")
            continue

        print(f"[DOWNLOADING] {repo}...")
        subprocess.run(
            ["python", "-m", "huggingface_hub", "download", repo, "--local-dir", local_dir],
            check=True,
        )
        print(f"[OK] {repo} downloaded to {local_dir}")

    model_volume.commit()
    print("All models ready on volume.")


# ── FlashHead Inference Function ─────────────────────────────────────────────

@app.cls(
    image=flashhead_image,
    gpu="A10G",
    volumes={MODEL_DIR: model_volume},
    timeout=300,
    container_idle_timeout=120,  # Keep warm for 2 minutes between requests
    allow_concurrent_inputs=3,   # Up to 3 concurrent sessions per container
)
class AvatarInference:
    """
    Stateful Modal class for FlashHead inference.
    Pipeline is loaded once per container, reused across requests.
    """

    @modal.enter()
    def setup(self):
        """Load FlashHead pipeline on container startup."""
        import sys
        import torch

        # Add FlashHead source to path
        # (FlashHead repo is bundled with the deployment)
        sys.path.insert(0, "/app/SoulX-FlashHead")

        from flash_head.inference import get_pipeline, get_base_data, get_infer_params

        print(f"Loading FlashHead (lite) on {torch.cuda.get_device_name(0)}...")

        self.pipeline = get_pipeline(
            world_size=1,
            ckpt_dir=FLASHHEAD_CKPT,
            model_type="lite",
            wav2vec_dir=WAV2VEC_DIR,
        )
        self.infer_params = get_infer_params()
        self._get_base_data = get_base_data
        self._prepared_images = {}  # Cache prepared images by path

        print(f"FlashHead ready. GPU: {torch.cuda.get_device_name(0)}, "
              f"VRAM: {torch.cuda.get_device_properties(0).total_mem / 1024**3:.1f}GB")

    @modal.method()
    def generate_avatar_chunk(
        self,
        audio_bytes: bytes,
        audio_dtype: str,
        audio_len: int,
        reference_image: str,
        avatar_id: str | None = None,
    ) -> dict:
        """
        Generate one chunk of avatar video frames from audio.

        Args:
            audio_bytes: Raw audio as bytes (float32 at 16kHz)
            audio_dtype: Numpy dtype string
            audio_len: Number of audio samples
            reference_image: Path to reference image (on volume or URL)
            avatar_id: Optional avatar ID for LoRA loading

        Returns:
            dict with "frames": list of (frame_bytes, height, width) tuples
        """
        import numpy as np
        import torch
        from flash_head.inference import get_audio_embedding, run_pipeline

        # Reconstruct audio array
        audio_array = np.frombuffer(audio_bytes, dtype=audio_dtype)[:audio_len]

        # Prepare reference image (cached per image path)
        if reference_image not in self._prepared_images:
            self._get_base_data(
                self.pipeline,
                cond_image_path_or_dir=reference_image,
                base_seed=42,
                use_face_crop=True,
            )
            self._prepared_images[reference_image] = True

        # Load LoRA if available
        if avatar_id:
            lora_dir = f"{MODEL_DIR}/avatars/{avatar_id}/lora"
            import os
            if os.path.isdir(lora_dir):
                try:
                    from peft import PeftModel
                    if not isinstance(self.pipeline.model, PeftModel):
                        self.pipeline.model = PeftModel.from_pretrained(
                            self.pipeline.model, lora_dir
                        )
                        self.pipeline.model.eval()
                except Exception:
                    pass

        # Generate audio embedding
        audio_emb = get_audio_embedding(self.pipeline, audio_array)

        # Run diffusion pipeline
        frames_tensor = run_pipeline(self.pipeline, audio_emb)

        # Convert to serializable format
        motion_frames_num = self.infer_params.get("motion_frames_num", 5)
        frames_out = []

        for i in range(motion_frames_num, frames_tensor.shape[0]):
            frame_rgb = frames_tensor[i].cpu().numpy().astype(np.uint8)
            # Add alpha channel
            h, w = frame_rgb.shape[:2]
            alpha = np.full((h, w, 1), 255, dtype=np.uint8)
            frame_rgba = np.concatenate([frame_rgb, alpha], axis=2)
            frames_out.append((frame_rgba.tobytes(), h, w))

        return {"frames": frames_out}


# ── Entrypoint for testing ───────────────────────────────────────────────────

@app.local_entrypoint()
def main():
    """Test the deployed function locally."""
    import numpy as np

    print("Testing Modal avatar inference...")

    # Generate 1 second of silence as test audio
    test_audio = np.zeros(16000, dtype=np.float32)

    inference = AvatarInference()
    result = inference.generate_avatar_chunk.remote(
        audio_bytes=test_audio.tobytes(),
        audio_dtype="float32",
        audio_len=len(test_audio),
        reference_image="/models/test_reference.png",
        avatar_id=None,
    )

    print(f"Generated {len(result['frames'])} frames")
    if result["frames"]:
        _, h, w = result["frames"][0]
        print(f"Frame size: {w}x{h}")
    print("Modal avatar inference OK!")

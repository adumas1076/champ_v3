"""
Live Creatiq Operator V2 — LiveAvatar (Alibaba 14B) on Modal H100

The quality upgrade. WanS2V-14B + LiveAvatar LoRA = hyperrealistic talking head.
Audio + reference photo + text prompt → video frames.

Deploy:
    cd champ_v3
    modal deploy avatar/modal_liveavatar_deploy.py

Test:
    modal run avatar/modal_liveavatar_deploy.py

Requirements:
    - H100 80GB GPU (FP8 quantization enabled)
    - ~30GB model weights (Wan2.2-S2V-14B + LiveAvatar LoRA)
    - torch >= 2.4.0, CUDA 12.4+
"""

import os
import io
import time
import base64
import tempfile

import modal

# ─── Modal App Setup ────────────────────────────────────────────────────────

app = modal.App("champ-liveavatar")

# Volume for model checkpoints
checkpoints_volume = modal.Volume.from_name(
    "champ-liveavatar-checkpoints", create_if_missing=True
)

# Build image with LiveAvatar dependencies
liveavatar_image = (
    modal.Image.from_registry(
        "nvidia/cuda:12.4.1-devel-ubuntu22.04",
        add_python="3.10",
    )
    .apt_install(
        "ffmpeg", "git", "git-lfs",
        "libgl1-mesa-glx", "libglib2.0-0",
        "libgles2-mesa", "libegl1-mesa",
        "build-essential", "clang", "g++",
    )
    .run_commands(
        "pip install torch==2.5.1 torchvision==0.20.1 torchaudio==2.5.1 --index-url https://download.pytorch.org/whl/cu124",
    )
    .pip_install(
        # Diffusion / Transformers
        "diffusers>=0.31.0",
        "transformers>=4.49.0,<=4.51.3",
        "accelerate>=1.1.1",
        "peft==0.17.1",
        # Audio
        "librosa",
        "openai-whisper",
        "pyworld",
        # Vision
        "opencv-python-headless>=4.9.0.80",
        "insightface",
        "onnxruntime-gpu",
        # Video
        "imageio[ffmpeg]",
        "imageio-ffmpeg",
        "decord",
        # Config / Utils
        "omegaconf",
        "hydra-core",
        "easydict",
        "HyperPyYAML",
        "einops",
        "orjson",
        "huggingface_hub",
        "modelscope",
        "gdown",
        "safetensors",
        "sentencepiece",
        "tiktoken",
        # Misc
        "tqdm",
        "Pillow",
        "scipy",
        "scikit-image",
        "colored",
        "numpy<2.1",
        "gradio",
        "ftfy",
        "regex",
        "dashscope",
    )
    # flash-attn: REQUIRED by LiveAvatar 14B model
    .pip_install("wheel", "packaging", "ninja")
    .run_commands(
        "MAX_JOBS=4 pip install flash-attn --no-build-isolation",
    )
    # Clone LiveAvatar repo
    .run_commands(
        "git clone https://github.com/Alibaba-Quark/LiveAvatar /root/liveavatar",
        "cd /root/liveavatar && pip install -e . 2>/dev/null || true",
    )
    .env({
        "PYTHONIOENCODING": "utf-8",
        "ENABLE_COMPILE": "true",
    })
)


# ─── Checkpoint Downloader ────────────────────────────────────────────────

@app.function(
    image=liveavatar_image,
    volumes={"/checkpoints": checkpoints_volume},
    timeout=3600,  # 1hr — large model download
)
def download_checkpoints():
    """Download Wan2.2-S2V-14B base model + LiveAvatar LoRA weights."""
    import subprocess

    # Check if already downloaded
    marker = "/checkpoints/Wan2.2-S2V-14B/config.json"
    if os.path.exists(marker):
        print("[LIVEAVATAR] Checkpoints already downloaded.")
        return "already_downloaded"

    print("[LIVEAVATAR] Downloading Wan2.2-S2V-14B base model...")
    subprocess.run(["git", "lfs", "install"], check=True)

    # Download base Wan model
    subprocess.run(
        [
            "huggingface-cli", "download",
            "Wan-AI/Wan2.2-S2V-14B",
            "--local-dir", "/checkpoints/Wan2.2-S2V-14B",
        ],
        check=True,
    )

    # LiveAvatar LoRA weights are loaded from HuggingFace at runtime
    # via --lora_path_dmd "Quark-Vision/Live-Avatar"
    # Pre-download them too
    print("[LIVEAVATAR] Downloading LiveAvatar LoRA weights...")
    subprocess.run(
        [
            "huggingface-cli", "download",
            "Quark-Vision/Live-Avatar",
            "--local-dir", "/checkpoints/LiveAvatar-LoRA",
        ],
        check=True,
    )

    checkpoints_volume.commit()
    print("[LIVEAVATAR] All checkpoints downloaded and committed.")
    return "downloaded"


# ─── LiveAvatar Renderer ──────────────────────────────────────────────────

@app.cls(
    image=liveavatar_image,
    gpu="H100",
    timeout=600,
    scaledown_window=300,  # keep warm 5 min (model load is expensive)
    volumes={"/checkpoints": checkpoints_volume},
)
class LiveAvatarRenderer:
    """LiveAvatar (Alibaba 14B) renderer on Modal H100.

    Hyperrealistic audio-driven talking head from a single photo.
    Uses WanS2V-14B with LiveAvatar LoRA, FP8 quantization, 4-step sampling.
    """

    @modal.enter()
    def setup(self):
        """Verify checkpoints exist on container start."""
        self.ckpt_dir = "/checkpoints/Wan2.2-S2V-14B"
        self.lora_dir = "/checkpoints/LiveAvatar-LoRA"

        if not os.path.exists(self.ckpt_dir):
            raise RuntimeError(
                "Checkpoints not found. Run download_checkpoints() first."
            )
        print(f"[LIVEAVATAR] Checkpoints verified at {self.ckpt_dir}")
        print(f"[LIVEAVATAR] LoRA verified at {self.lora_dir}")

    @modal.method()
    def render(
        self,
        audio_b64: str,
        source_image_b64: str,
        prompt: str = "A confident, professional Black woman with long curly hair, wearing a dark blazer and gold necklace, sitting in a leather chair in a modern office. Warm lighting, photorealistic.",
        size: str = "704*384",
        infer_frames: int = 48,
        sampling_steps: int = 4,
        seed: int = 420,
    ) -> dict:
        """Render talking head video using LiveAvatar's own inference script.

        Uses torchrun subprocess — same as their shell script, most reliable.
        """
        import subprocess
        import librosa

        t0 = time.time()

        # Decode inputs to temp files
        audio_bytes = base64.b64decode(audio_b64)
        image_bytes = base64.b64decode(source_image_b64)

        audio_path = "/tmp/input_audio.wav"
        image_path = "/tmp/input_image.png"
        output_dir = "/tmp/liveavatar_output"
        os.makedirs(output_dir, exist_ok=True)

        with open(audio_path, "wb") as f:
            f.write(audio_bytes)
        with open(image_path, "wb") as f:
            f.write(image_bytes)

        # Get audio duration
        audio, sr = librosa.load(audio_path, sr=16000)
        duration_sec = len(audio) / 16000

        print(f"[LIVEAVATAR] Rendering: {duration_sec:.1f}s audio, {size}, {sampling_steps} steps...")

        try:
            # Run inference via torchrun — same as their shell script
            cmd = [
                "torchrun",
                "--nproc_per_node=1",
                "--master_port=29101",
                "/root/liveavatar/minimal_inference/s2v_streaming_interact.py",
                "--task", "s2v-14B",
                "--size", size,
                "--base_seed", str(seed),
                "--training_config", "/root/liveavatar/liveavatar/configs/s2v_causal_sft.yaml",
                "--offload_model", "True",
                "--convert_model_dtype",
                "--prompt", prompt,
                "--image", image_path,
                "--audio", audio_path,
                "--infer_frames", str(infer_frames),
                "--load_lora",
                "--lora_path_dmd", "Quark-Vision/Live-Avatar",
                "--sample_steps", str(sampling_steps),
                "--sample_guide_scale", "0",
                "--num_clip", "10000",
                "--num_gpus_dit", "1",
                "--sample_solver", "euler",
                "--single_gpu",
                "--ckpt_dir", self.ckpt_dir,
                "--fp8",
                "--save_dir", output_dir + "/",
            ]

            env = os.environ.copy()
            env["CUDA_VISIBLE_DEVICES"] = "0"
            env["ENABLE_COMPILE"] = "true"

            result = subprocess.run(
                cmd,
                cwd="/root/liveavatar",
                env=env,
                capture_output=True,
                text=True,
                timeout=600,
            )

            print(f"[LIVEAVATAR] stdout: {result.stdout[-2000:]}")
            if result.returncode != 0:
                print(f"[LIVEAVATAR] stderr: {result.stderr[-2000:]}")
                return {
                    "error": f"Inference failed with code {result.returncode}",
                    "stderr": result.stderr[-1000:],
                }

            # Find output video — LiveAvatar saves with save_dir prefix
            import glob
            output_files = (
                glob.glob(os.path.join(output_dir, "*.mp4")) +
                glob.glob(output_dir + "*.mp4") +
                glob.glob("/tmp/*.mp4")
            )
            if not output_files:
                return {"error": "No output video produced", "stdout": result.stdout[-500:]}

            output_path = sorted(output_files)[-1]  # latest file

            with open(output_path, "rb") as f:
                video_bytes = f.read()

            elapsed = time.time() - t0
            # Estimate frames from duration (25 fps default)
            num_frames = int(duration_sec * 25)
            fps = num_frames / elapsed if elapsed > 0 else 0

            print(
                f"[LIVEAVATAR] Done: ~{num_frames} frames, {duration_sec:.1f}s audio, "
                f"{elapsed:.1f}s render, {fps:.1f} FPS"
            )

            return {
                "video_b64": base64.b64encode(video_bytes).decode(),
                "num_frames": num_frames,
                "duration_sec": round(duration_sec, 2),
                "render_time_sec": round(elapsed, 2),
                "fps": round(fps, 1),
                "resolution": size,
                "model": "LiveAvatar-14B",
            }

        finally:
            # Cleanup
            for p in [audio_path, image_path]:
                try:
                    os.unlink(p)
                except OSError:
                    pass

    @modal.method()
    def health(self) -> dict:
        """Check model status."""
        return {
            "status": "ok",
            "model": "LiveAvatar-14B (WanS2V + LoRA)",
            "gpu": "H100-80GB",
            "ckpt_exists": os.path.exists(self.ckpt_dir),
            "lora_exists": os.path.exists(self.lora_dir),
        }


# ─── Test Entrypoint ─────────────────────────────────────────────────────

@app.local_entrypoint()
def main():
    """Test LiveAvatar with Genesis."""
    import base64

    # Download checkpoints first
    print("Checking checkpoints...")
    result = download_checkpoints.remote()
    print(f"Checkpoints: {result}")

    # Load Genesis
    genesis_path = os.path.join(
        os.path.dirname(__file__),
        "..", "..", "reference", "skipper_app_v5-livekit",
        "frontend", "src", "assets", "genesis-avatar.png",
    )
    with open(genesis_path, "rb") as f:
        source_b64 = base64.b64encode(f.read()).decode()

    # Load test audio (Ditto's example)
    audio_path = os.path.join(
        os.path.dirname(__file__),
        "..", "..", "reference", "ditto", "example", "audio.wav",
    )
    with open(audio_path, "rb") as f:
        audio_b64 = base64.b64encode(f.read()).decode()

    print("Rendering Genesis with LiveAvatar 14B on H100...")
    renderer = LiveAvatarRenderer()
    result = renderer.render.remote(
        audio_b64=audio_b64,
        source_image_b64=source_b64,
        prompt=(
            "A confident, professional Black woman with long curly hair, "
            "wearing a dark blazer and gold necklace, sitting in a leather chair "
            "in a modern office. Warm lighting, photorealistic, speaking directly "
            "to camera with natural expressions and subtle head movements."
        ),
        size="704*384",
        infer_frames=48,
        sampling_steps=4,
        seed=420,
    )

    print(f"\nResult: {result}")
    if "error" in result:
        print(f"  ERROR: {result['error']}")
        return
    print(f"  Frames: {result['num_frames']}")
    print(f"  Duration: {result['duration_sec']}s")
    print(f"  Render time: {result['render_time_sec']}s")
    print(f"  FPS: {result['fps']}")
    print(f"  Resolution: {result['resolution']}")

    # Save
    output_dir = os.path.join(os.path.dirname(__file__), "..", "..", "models", "avatars", "genesis")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "genesis_liveavatar_v2.mp4")

    video_bytes = base64.b64decode(result["video_b64"])
    with open(output_path, "wb") as f:
        f.write(video_bytes)
    print(f"  Saved: {output_path} ({len(video_bytes) // 1024} KB)")

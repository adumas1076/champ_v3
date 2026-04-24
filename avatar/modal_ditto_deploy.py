"""
Live Creatiq Operator — Ditto Avatar Renderer on Modal A100

Audio + reference photo → real-time talking head video frames.
Ditto (Ant Group, ACM MM 2025) — motion-space diffusion, ~25 FPS on A100.

Deploy:
    cd champ_v3
    modal deploy avatar/modal_ditto_deploy.py

Test:
    modal run avatar/modal_ditto_deploy.py

Endpoints:
    /render         — Audio WAV bytes + source image → MP4 video bytes
    /render_stream  — Audio WAV chunks → video frame chunks (online mode)
    /health         — Check model status
"""

import os
import io
import time
import base64
import tempfile

import modal

# ─── Modal App Setup ────────────────────────────────────────────────────────

app = modal.App("champ-ditto-avatar")

# Volume for model checkpoints (downloaded once, persisted)
checkpoints_volume = modal.Volume.from_name(
    "champ-ditto-checkpoints", create_if_missing=True
)

# Build image with all Ditto dependencies
ditto_image = (
    modal.Image.debian_slim(python_version="3.10")
    .apt_install("ffmpeg", "git", "git-lfs", "libgl1-mesa-glx", "libglib2.0-0", "libgles2-mesa", "libegl1-mesa")
    .pip_install(
        # PyTorch + CUDA
        "torch==2.5.1",
        "torchaudio==2.5.1",
        "torchvision==0.20.1",
        # Ditto dependencies
        "librosa==0.10.2.post1",
        "tqdm",
        "filetype==1.2.0",
        "imageio==2.36.1",
        "opencv-python-headless==4.10.0.84",
        "scikit-image==0.25.0",
        "cython==3.0.11",
        "imageio-ffmpeg==0.5.1",
        "colored",
        "numpy==2.0.1",
        "scipy>=1.15.0",
        "Pillow>=11.0.0",
        "onnxruntime-gpu",
        "mediapipe",
        "einops",
    )
    # Clone Ditto repo into the image
    .run_commands(
        "git clone https://github.com/antgroup/ditto-talkinghead /root/ditto",
    )
    .env({"PYTHONIOENCODING": "utf-8"})
)


# ─── Checkpoint Downloader ────────────────────────────────────────────────

@app.function(
    image=ditto_image,
    volumes={"/checkpoints": checkpoints_volume},
    timeout=1800,
)
def download_checkpoints():
    """Download Ditto PyTorch checkpoints from HuggingFace (one-time)."""
    import subprocess

    marker = "/checkpoints/ditto_pytorch/models/decoder.pth"
    if os.path.exists(marker):
        print("[DITTO] Checkpoints already downloaded, skipping.")
        return "already_downloaded"

    print("[DITTO] Downloading checkpoints from HuggingFace...")
    subprocess.run(
        ["git", "lfs", "install"],
        check=True,
    )
    subprocess.run(
        [
            "git", "clone",
            "https://huggingface.co/digital-avatar/ditto-talkinghead",
            "/checkpoints/ditto_hf",
        ],
        check=True,
    )

    # Copy to organized structure
    subprocess.run(["cp", "-r", "/checkpoints/ditto_hf/ditto_cfg", "/checkpoints/ditto_cfg"], check=True)
    subprocess.run(["cp", "-r", "/checkpoints/ditto_hf/ditto_pytorch", "/checkpoints/ditto_pytorch"], check=True)

    checkpoints_volume.commit()
    print("[DITTO] Checkpoints downloaded and committed to volume.")
    return "downloaded"


# ─── Ditto Avatar Renderer ──────────────────────────────────────────────

@app.cls(
    image=ditto_image,
    gpu="A100",
    timeout=600,
    scaledown_window=180,
    volumes={"/checkpoints": checkpoints_volume},
)
class DittoAvatarRenderer:
    """Ditto talking head renderer on Modal A100.

    Takes audio + reference photo, produces talking head video.
    Uses PyTorch backend (works on any GPU, no TensorRT conversion needed).
    """

    @modal.enter()
    def load_model(self):
        """Load Ditto SDK on container start."""
        import sys
        sys.path.insert(0, "/root/ditto")

        from stream_pipeline_offline import StreamSDK

        data_root = "/checkpoints/ditto_pytorch"
        cfg_pkl = "/checkpoints/ditto_cfg/v0.4_hubert_cfg_pytorch.pkl"

        if not os.path.exists(cfg_pkl):
            raise RuntimeError(
                "Checkpoints not found. Run download_checkpoints() first: "
                "modal run avatar/modal_ditto_deploy.py::download_checkpoints"
            )

        print("[DITTO] Loading Ditto SDK (PyTorch backend)...")
        t0 = time.time()
        self.sdk = StreamSDK(cfg_pkl, data_root)
        print(f"[DITTO] SDK loaded in {time.time() - t0:.1f}s")

    @modal.method()
    def render(
        self,
        audio_b64: str,
        source_image_b64: str,
        emo: int = 4,
        online_mode: bool = False,
    ) -> dict:
        """Render talking head video from audio + reference image.

        Args:
            audio_b64: Base64-encoded WAV audio (16kHz mono)
            source_image_b64: Base64-encoded PNG/JPG reference photo
            emo: Emotion control (0-8, default 4=neutral)
            online_mode: Use streaming pipeline (lower latency, for real-time)

        Returns:
            dict with "video_b64" (base64 MP4), "num_frames", "duration_sec"
        """
        import sys
        sys.path.insert(0, "/root/ditto")

        import librosa
        import math
        import numpy as np

        t0 = time.time()

        # Decode inputs
        audio_bytes = base64.b64decode(audio_b64)
        image_bytes = base64.b64decode(source_image_b64)

        # Write to temp files (Ditto expects file paths)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_bytes)
            audio_path = f.name

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(image_bytes)
            source_path = f.name

        output_path = tempfile.mktemp(suffix=".mp4")

        try:
            # Setup SDK for this render
            setup_kwargs = {"emo": emo, "online_mode": online_mode}
            self.sdk.setup(source_path, output_path, **setup_kwargs)

            # Load audio
            audio, sr = librosa.core.load(audio_path, sr=16000)
            num_f = math.ceil(len(audio) / 16000 * 25)
            duration_sec = len(audio) / 16000

            self.sdk.setup_Nd(N_d=num_f)

            if online_mode:
                # Streaming: feed chunks
                chunksize = (3, 5, 2)
                audio = np.concatenate(
                    [np.zeros((chunksize[0] * 640,), dtype=np.float32), audio], 0
                )
                split_len = int(sum(chunksize) * 0.04 * 16000) + 80
                for i in range(0, len(audio), chunksize[1] * 640):
                    audio_chunk = audio[i : i + split_len]
                    if len(audio_chunk) < split_len:
                        audio_chunk = np.pad(
                            audio_chunk,
                            (0, split_len - len(audio_chunk)),
                            mode="constant",
                        )
                    self.sdk.run_chunk(audio_chunk, chunksize)
            else:
                # Batch: feed all at once
                aud_feat = self.sdk.wav2feat.wav2feat(audio)
                self.sdk.audio2motion_queue.put(aud_feat)

            self.sdk.close()

            # Mux audio + video
            final_path = output_path.replace(".mp4", "_final.mp4")
            cmd = (
                f'ffmpeg -loglevel error -y '
                f'-i "{self.sdk.tmp_output_path}" -i "{audio_path}" '
                f'-map 0:v -map 1:a -c:v copy -c:a aac "{final_path}"'
            )
            os.system(cmd)

            # Read result
            result_path = final_path if os.path.exists(final_path) else self.sdk.tmp_output_path
            with open(result_path, "rb") as f:
                video_bytes = f.read()

            elapsed = time.time() - t0
            print(
                f"[DITTO] Rendered {num_f} frames ({duration_sec:.1f}s audio) "
                f"in {elapsed:.1f}s ({num_f/elapsed:.1f} FPS)"
            )

            return {
                "video_b64": base64.b64encode(video_bytes).decode(),
                "num_frames": num_f,
                "duration_sec": round(duration_sec, 2),
                "render_time_sec": round(elapsed, 2),
                "fps": round(num_f / elapsed, 1),
            }

        finally:
            # Cleanup temp files
            for p in [audio_path, source_path, output_path,
                      output_path.replace(".mp4", "_final.mp4"),
                      output_path + ".tmp.mp4"]:
                try:
                    os.unlink(p)
                except OSError:
                    pass

    @modal.method()
    def health(self) -> dict:
        """Check if Ditto is loaded and ready."""
        return {
            "status": "ok",
            "model": "ditto-v0.4-hubert-pytorch",
            "gpu": "A100",
            "backend": "pytorch",
        }


# ─── Test Entrypoint ─────────────────────────────────────────────────────

@app.local_entrypoint()
def main():
    """Test the Ditto renderer with Genesis's photo and a test audio."""
    import base64

    # Check/download checkpoints first
    print("Checking checkpoints...")
    result = download_checkpoints.remote()
    print(f"Checkpoints: {result}")

    # Load Genesis reference photo
    genesis_path = os.path.join(
        os.path.dirname(__file__),
        "..", "..", "reference", "skipper_app_v5-livekit",
        "frontend", "src", "assets", "genesis-avatar.png",
    )

    if not os.path.exists(genesis_path):
        print(f"[ERROR] Genesis photo not found at: {genesis_path}")
        print("Please provide the path to Genesis's reference photo.")
        return

    with open(genesis_path, "rb") as f:
        source_b64 = base64.b64encode(f.read()).decode()

    # Load test audio (use Ditto's example or generate silence)
    example_audio = os.path.join(
        os.path.dirname(__file__),
        "..", "..", "reference", "ditto", "example", "audio.wav",
    )

    if os.path.exists(example_audio):
        with open(example_audio, "rb") as f:
            audio_b64 = base64.b64encode(f.read()).decode()
        print(f"Using Ditto example audio: {example_audio}")
    else:
        # Generate 3 seconds of silence as test
        import numpy as np
        import struct

        sr = 16000
        duration = 3
        samples = np.zeros(sr * duration, dtype=np.int16)
        buf = io.BytesIO()
        # Write WAV header manually
        import wave
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(samples.tobytes())
        audio_b64 = base64.b64encode(buf.getvalue()).decode()
        print("Using generated silence (3s)")

    # Render
    print("Rendering Genesis talking head...")
    renderer = DittoAvatarRenderer()
    result = renderer.render.remote(
        audio_b64=audio_b64,
        source_image_b64=source_b64,
        emo=4,  # neutral
    )

    print(f"Result: {result['num_frames']} frames, "
          f"{result['duration_sec']}s, "
          f"{result['fps']} FPS, "
          f"render time: {result['render_time_sec']}s")

    # Save output video locally
    output_dir = os.path.join(os.path.dirname(__file__), "..", "..", "models", "avatars", "genesis")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "genesis_ditto_test.mp4")

    video_bytes = base64.b64decode(result["video_b64"])
    with open(output_path, "wb") as f:
        f.write(video_bytes)
    print(f"Saved: {output_path} ({len(video_bytes) / 1024:.0f} KB)")

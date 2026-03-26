"""
CHAMP Avatar — Model Setup Script
Downloads all required models for the avatar pipeline.

Usage:
    cd champ_v3
    python -m avatar.setup

Models downloaded:
    1. LivePortrait — appearance encoder + warp decoder
    2. wav2vec2-base-960h — audio feature extraction
    3. SoulX-FlashHead — audio-to-motion prediction head

Requirements:
    pip install huggingface_hub[cli]
"""

import os
import sys
import subprocess


MODELS = {
    "LivePortrait": {
        "repo": "KwaiVGI/LivePortrait",
        "local_dir": "models/LivePortrait",
        "description": "Appearance encoder + warp decoder (per-frame rendering)",
    },
    "wav2vec2-base-960h": {
        "repo": "facebook/wav2vec2-base-960h",
        "local_dir": "models/wav2vec2-base-960h",
        "description": "Audio feature extraction (768-dim embeddings)",
    },
    "SoulX-FlashHead-1_3B": {
        "repo": "Soul-AILab/SoulX-FlashHead-1_3B",
        "local_dir": "models/SoulX-FlashHead-1_3B",
        "description": "Audio-to-motion prediction (52 blendshapes + head pose)",
    },
}

REPOS = {
    "LivePortrait": "https://github.com/KwaiVGI/LivePortrait.git",
    "SoulX-FlashHead": "https://github.com/Soul-AILab/SoulX-FlashHead.git",
}


def download_models():
    """Download all required model weights from HuggingFace."""
    print("=" * 60)
    print("CHAMP Avatar — Model Setup")
    print("=" * 60)

    os.makedirs("models", exist_ok=True)

    for name, cfg in MODELS.items():
        local_dir = cfg["local_dir"]
        if os.path.isdir(local_dir) and os.listdir(local_dir):
            print(f"\n  [OK] {name} — already at {local_dir}")
            continue

        print(f"\n  [DOWNLOADING] {name}")
        print(f"    {cfg['description']}")
        print(f"    From: huggingface.co/{cfg['repo']}")
        print(f"    To:   {local_dir}")

        try:
            subprocess.run(
                [
                    sys.executable, "-m", "huggingface_hub", "download",
                    cfg["repo"],
                    "--local-dir", local_dir,
                ],
                check=True,
            )
            print(f"    [OK] Downloaded")
        except subprocess.CalledProcessError as e:
            print(f"    [FAIL] {e}")
            print(f"    Manual: huggingface-cli download {cfg['repo']} --local-dir {local_dir}")
        except FileNotFoundError:
            print("    [FAIL] huggingface_hub not installed")
            print("    Install: pip install huggingface_hub[cli]")
            return


def clone_repos():
    """Clone source repos for inference code."""
    for name, url in REPOS.items():
        if os.path.isdir(name):
            print(f"\n  [OK] {name} repo already cloned")
            continue

        print(f"\n  [CLONING] {name}...")
        try:
            subprocess.run(["git", "clone", url], check=True)
            print(f"    [OK] Cloned")
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"    [FAIL] {e}")
            print(f"    Manual: git clone {url}")


def check_gpu():
    """Check for CUDA GPU availability."""
    print("\n  [GPU CHECK]")
    try:
        import torch
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            gpu_mem = torch.cuda.get_device_properties(0).total_mem / (1024**3)
            print(f"    GPU: {gpu_name} ({gpu_mem:.1f} GB)")
            if gpu_mem >= 20:
                print("    [OK] Sufficient VRAM for full pipeline")
            else:
                print("    [WARN] <24GB VRAM — may need to use placeholder mode")
        else:
            print("    [WARN] No CUDA GPU — avatar runs in placeholder mode")
            print("    Voice pipeline still works, just no animated video")
    except ImportError:
        print("    [INFO] PyTorch not installed — that's fine for local dev")
        print("    Avatar will run in placeholder mode")
        print("    Install for GPU: pip install torch --index-url https://download.pytorch.org/whl/cu128")


def check_dependencies():
    """Check Python package availability."""
    print("\n  [DEPENDENCIES]")
    deps = {
        "livekit": "livekit-agents SDK",
        "PIL": "Pillow (image processing)",
        "numpy": "NumPy (array operations)",
        "torch": "PyTorch (GPU inference)",
        "torchaudio": "TorchAudio (audio resampling)",
        "transformers": "HuggingFace Transformers (wav2vec2)",
        "librosa": "Librosa (audio loading — FlashHead)",
        "imageio": "ImageIO (video frame I/O — FlashHead)",
        "flash_attn": "FlashAttention 2.8 (FlashHead acceleration)",
    }
    for module, desc in deps.items():
        try:
            __import__(module)
            print(f"    [OK] {desc}")
        except ImportError:
            print(f"    [--] {desc} (not installed, optional for placeholder mode)")


def check_flashhead_pipeline():
    """Check FlashHead full pipeline can be imported."""
    print("\n  [FLASHHEAD PIPELINE]")
    flashhead_src = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "SoulX-FlashHead")
    if os.path.isdir(flashhead_src):
        print(f"    [OK] FlashHead source: {flashhead_src}")
        sys.path.insert(0, flashhead_src)
        try:
            from flash_head.inference import get_pipeline
            print("    [OK] flash_head.inference importable")
        except ImportError as e:
            print(f"    [--] flash_head.inference import failed: {e}")
            print("         FlashHead full pipeline unavailable — will use placeholder")
    else:
        print(f"    [--] FlashHead source not found at {flashhead_src}")
        print("         Clone: git clone https://github.com/Soul-AILab/SoulX-FlashHead.git")


def print_summary():
    """Print setup status summary."""
    print("\n" + "=" * 60)
    print("Setup Summary")
    print("=" * 60)

    checks = {
        "LivePortrait model": os.path.isdir("models/LivePortrait"),
        "wav2vec2 model": os.path.isdir("models/wav2vec2-base-960h"),
        "FlashHead model": os.path.isdir("models/SoulX-FlashHead-1_3B"),
        "LivePortrait code": os.path.isdir("LivePortrait"),
        "FlashHead code": os.path.isdir("SoulX-FlashHead") or os.path.isdir("flash_head"),
        "Real-ESRGAN (4x)": os.path.isfile("models/realesrgan/RealESRGAN_x4plus.pth"),
        "Real-ESRGAN (2x)": os.path.isfile("models/realesrgan/RealESRGAN_x2plus.pth"),
    }

    all_good = True
    for name, ok in checks.items():
        status = "[OK]" if ok else "[--]"
        print(f"  {status} {name}")
        if not ok:
            all_good = False

    if all_good:
        print("\n  All models ready! Avatar will use full GPU pipeline.")
    else:
        print("\n  Some models missing — avatar runs in placeholder mode.")
        print("  Voice pipeline works normally. Animated face needs GPU + models.")

    print(f"\n  To run Avatar Lab:")
    print(f"    cd champ_v3")
    print(f"    python avatar/agent_avatar.py dev")
    print(f"    Open http://localhost:3000/avatar-lab")
    print()


if __name__ == "__main__":
    check_gpu()
    check_dependencies()
    check_flashhead_pipeline()
    clone_repos()
    download_models()
    print_summary()
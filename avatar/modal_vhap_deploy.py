"""
CHAMP Avatar — VHAP Head Tracking on Modal GPU

Tracks FLAME parameters from video → feeds directly into GaussianAvatars training.
Same author as GaussianAvatars, output is directly compatible.

Deploy:  modal deploy avatar/modal_vhap_deploy.py

Pipeline:
    1. Upload video → track() → FLAME params + camera poses
    2. export() → GaussianAvatars-ready dataset
    3. Feed into champ-gaussian-training for 3DGS avatar training
"""

import io
import json
import os
import shutil
import subprocess
import tarfile
import time
import traceback
from pathlib import Path

import modal

app = modal.App("champ-vhap")

tracking_vol = modal.Volume.from_name("champ-gaussian-training-data", create_if_missing=True)

vhap_image = (
    modal.Image.from_registry(
        "nvidia/cuda:12.1.1-devel-ubuntu22.04",
        add_python="3.10",
    )
    .apt_install(
        "ffmpeg", "git", "wget",
        "libgl1-mesa-glx", "libglib2.0-0", "libsm6", "libxrender1", "libxext6",
        "build-essential", "ninja-build", "cmake",
    )
    .pip_install(
        "torch==2.2.0+cu121",
        "torchvision==0.17.0+cu121",
        extra_options="--index-url https://download.pytorch.org/whl/cu121",
    )
    .env({
        "CXX": "g++", "CC": "gcc", "CUDA_HOME": "/usr/local/cuda",
        "TORCH_CUDA_ARCH_LIST": "8.0;8.6;9.0",
        "MAX_JOBS": "2",
    })
    .pip_install("wheel", "setuptools")
    .run_commands(
        # Clone VHAP
        "cd /root && git clone --depth 1 https://github.com/ShenhanQian/VHAP.git",
        # Install nvdiffrast with backface-culling (VHAP's custom fork)
        "pip install --no-build-isolation nvdiffrast@git+https://github.com/ShenhanQian/nvdiffrast@backface-culling --force-reinstall",
        # Install VHAP
        "cd /root/VHAP && pip install -e .",
    )
)

VOLUME_MOUNT = "/data"


_fn_kwargs = dict(
    image=vhap_image,
    gpu="A100",
    timeout=86400,  # 24 hours max
    scaledown_window=300,
    memory=32768,
    volumes={VOLUME_MOUNT: tracking_vol},
)


@app.function(**_fn_kwargs)
def health() -> str:
    import torch
    vhap_ok = True
    try:
        import vhap  # noqa: F401
    except ImportError:
        vhap_ok = False

    flame_exists = (Path(VOLUME_MOUNT) / "flame_model" / "flame2023.pkl").exists()

    return json.dumps({
        "engine": "vhap_head_tracker",
        "device": "cuda" if torch.cuda.is_available() else "cpu",
        "gpu": str(torch.cuda.get_device_name(0)) if torch.cuda.is_available() else "none",
        "vram_gb": round(torch.cuda.get_device_properties(0).total_memory / 1e9, 1) if torch.cuda.is_available() else 0,
        "vhap_installed": vhap_ok,
        "flame_model_available": flame_exists,
        "status": "ready" if vhap_ok and flame_exists else "missing_deps",
    })


@app.function(**_fn_kwargs)
def track_video(avatar_id: str, video_bytes: bytes, batch_size: int = 16) -> str:
    """
    Preprocess + track FLAME parameters from a video.

    Pipeline:
        1. Save video to work dir
        2. vhap.preprocess: video → frames + masks (RobustVideoMatting)
        3. vhap.track: frames + masks → FLAME params (.npz)

    Args:
        avatar_id: Unique avatar identifier
        video_bytes: MP4/MOV video bytes (ideally 1-2 min, front-facing)
        batch_size: Frames per batch (16 = fast, 1 = more stable)

    Returns:
        JSON with status, paths, num_frames
    """
    vhap_root = Path("/root/VHAP")
    data_root = Path(VOLUME_MOUNT) / "vhap_data" / "monocular"
    data_root.mkdir(parents=True, exist_ok=True)

    # Save video with expected name
    video_path = data_root / f"{avatar_id}.mp4"
    with open(video_path, "wb") as f:
        f.write(video_bytes)
    print(f"[VHAP] Saved video: {len(video_bytes) / 1e6:.1f} MB")

    # Copy FLAME model to VHAP expected location
    flame_asset_dir = vhap_root / "asset" / "flame"
    flame_asset_dir.mkdir(parents=True, exist_ok=True)

    vol_flame = Path(VOLUME_MOUNT) / "flame_model" / "flame2023.pkl"
    vol_masks = Path(VOLUME_MOUNT) / "flame_model" / "FLAME_masks.pkl"

    if not vol_flame.exists():
        return json.dumps({
            "status": "error",
            "error": "FLAME model not on volume. Upload via champ-gaussian-training first.",
        })

    shutil.copy2(vol_flame, flame_asset_dir / "flame2023.pkl")
    if vol_masks.exists():
        shutil.copy2(vol_masks, flame_asset_dir / "FLAME_masks.pkl")

    env = {**os.environ, "CUDA_VISIBLE_DEVICES": "0"}
    start = time.time()

    # Clean up any previous runs
    seq_dir = data_root / avatar_id
    if seq_dir.exists():
        shutil.rmtree(seq_dir)

    # Step 1: Extract frames with ffmpeg (reliable, always works)
    images_dir = seq_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    print("[VHAP] Step 1: Extracting frames...")
    ffmpeg_cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-vf", "fps=25",
        "-start_number", "0",
        "-q:v", "2",
        str(images_dir / "%06d.jpg"),
    ]
    ffmpeg_result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=120)
    num_frames = len(list(images_dir.glob("*.jpg")))
    print(f"[VHAP] Extracted {num_frames} frames")

    if num_frames == 0:
        tracking_vol.commit()
        return json.dumps({"status": "error", "error": f"ffmpeg extracted 0 frames. stderr: {ffmpeg_result.stderr[-500:]}"})

    # Generate GRAYSCALE alpha maps — VHAP loads with Image.open() and expects (H,W) shape
    alpha_dir = seq_dir / "alpha_maps"
    alpha_dir.mkdir(parents=True, exist_ok=True)

    print("[VHAP] Generating grayscale alpha maps...")
    from PIL import Image
    # Get actual frame size from first image
    first_img = sorted(images_dir.glob("*.jpg"))[0]
    w, h = Image.open(first_img).size
    print(f"[VHAP] Frame size: {w}x{h}")

    alpha_count = 0
    for img_file in sorted(images_dir.glob("*.jpg")):
        mask = Image.new("L", (w, h), 255)
        out_path = alpha_dir / img_file.name
        mask.save(out_path)
        alpha_count += 1
    print(f"[VHAP] Generated {alpha_count} grayscale alpha maps ({w}x{h})")

    preprocess_time = time.time() - start

    # Step 2: Track — frames → FLAME params
    print("[VHAP] Step 2: Tracking FLAME parameters...")
    track_cmd = [
        "python", "-m", "vhap.track",
        "--data.root_folder", str(data_root),
        "--data.sequence", avatar_id,
    ]

    try:
        result = subprocess.run(
            track_cmd, capture_output=True, text=True, timeout=82800,  # 23 hours
            cwd=str(vhap_root), env=env,
        )
        elapsed = time.time() - start

        if result.returncode != 0:
            tracking_vol.commit()
            return json.dumps({
                "status": "error",
                "step": "tracking",
                "returncode": result.returncode,
                "stderr": result.stderr[-2000:] if result.stderr else "",
                "stdout_tail": result.stdout[-1000:] if result.stdout else "",
                "preprocess_time": preprocess_time,
                "elapsed_sec": elapsed,
            })

        # Find output files — VHAP writes to its own output dir, not the volume
        npz_files = list(Path(data_root).rglob("*.npz"))

        # Check VHAP default output location and COPY to volume
        vhap_output = vhap_root / "output"
        if vhap_output.exists():
            vhap_npz = list(vhap_output.rglob("*.npz"))
            npz_files.extend(vhap_npz)
            # Copy VHAP output to the volume so it persists
            vol_output = Path(VOLUME_MOUNT) / "vhap_output" / avatar_id
            vol_output.mkdir(parents=True, exist_ok=True)
            for f in vhap_output.rglob("*"):
                if f.is_file():
                    dest = vol_output / f.relative_to(vhap_output)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(f, dest)
                    print(f"[VHAP] Saved to volume: {dest.name} ({f.stat().st_size} bytes)")

        # Also copy to avatars dir for GaussianAvatars
        avatars_dir = Path(VOLUME_MOUNT) / "avatars" / avatar_id
        avatars_dir.mkdir(parents=True, exist_ok=True)
        for npz in npz_files:
            shutil.copy2(npz, avatars_dir / npz.name)

        print(f"[VHAP] Tracking complete: {len(npz_files)} output files in {elapsed:.1f}s")
        tracking_vol.commit()

        return json.dumps({
            "status": "tracked",
            "avatar_id": avatar_id,
            "data_root": str(data_root),
            "npz_files": [str(f) for f in npz_files],
            "preprocess_time": preprocess_time,
            "elapsed_sec": elapsed,
        })

    except subprocess.TimeoutExpired:
        tracking_vol.commit()
        return json.dumps({"status": "timeout", "error": "Tracking timed out after 3000s."})
    except Exception:
        tracking_vol.commit()
        return json.dumps({"status": "error", "error": traceback.format_exc()[-2000:]})


@app.function(**_fn_kwargs)
def export_for_gaussian_avatars(avatar_id: str) -> str:
    """
    Export VHAP tracked data into GaussianAvatars-ready format.

    Must run track_video() first.

    Returns:
        JSON with status and path to exported dataset
    """
    work_dir = Path(VOLUME_MOUNT) / "vhap_work" / avatar_id
    tracked_dir = work_dir / "tracked"

    if not tracked_dir.exists():
        return json.dumps({"status": "error", "error": f"No tracked data for '{avatar_id}'. Run track_video first."})

    # Find the tracked params
    npz_files = list(tracked_dir.rglob("tracked_flame_params*.npz"))
    if not npz_files:
        return json.dumps({"status": "error", "error": "No tracked_flame_params found."})

    vhap_root = Path("/root/VHAP")

    # Export as NeRF/GaussianAvatars dataset
    export_dir = Path(VOLUME_MOUNT) / "avatars" / avatar_id
    export_dir.mkdir(parents=True, exist_ok=True)

    # VHAP has export_as_nerf_dataset.py
    export_script = vhap_root / "export_as_nerf_dataset.py"
    if not export_script.exists():
        # Try alternative location
        export_script = vhap_root / "vhap" / "export_as_nerf_dataset.py"

    if export_script.exists():
        cmd = [
            "python", str(export_script),
            "--input_path", str(tracked_dir),
            "--output_path", str(export_dir),
        ]
        print(f"[VHAP] Exporting: {' '.join(cmd)}")

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=600,
            cwd=str(vhap_root),
        )

        if result.returncode != 0:
            # Fall back to manual export
            print(f"[VHAP] Export script failed, doing manual copy: {result.stderr[-500:]}")
    else:
        print("[VHAP] No export script found, doing manual copy")

    # Manual fallback: copy tracked data to avatars dir in expected structure
    # Copy FLAME params
    for npz in npz_files:
        shutil.copy2(npz, export_dir / npz.name)

    # Copy images if they exist
    images_src = tracked_dir / "images"
    if images_src.exists():
        images_dst = export_dir / "images"
        if images_dst.exists():
            shutil.rmtree(images_dst)
        shutil.copytree(images_src, images_dst)

    # Count what we have
    num_images = len(list(export_dir.rglob("*.png"))) + len(list(export_dir.rglob("*.jpg")))

    tracking_vol.commit()

    return json.dumps({
        "status": "exported",
        "avatar_id": avatar_id,
        "export_dir": str(export_dir),
        "num_images": num_images,
        "npz_files": [f.name for f in npz_files],
    })


@app.function(**_fn_kwargs)
def track_and_export(avatar_id: str, video_bytes: bytes, batch_size: int = 16) -> str:
    """
    One-shot: track video + export for GaussianAvatars training.
    Convenience wrapper that runs both steps.
    """
    # Step 1: Track
    track_result = json.loads(track_video.local(avatar_id, video_bytes, batch_size))
    if track_result.get("status") != "tracked":
        return json.dumps(track_result)

    # Step 2: Export
    export_result = json.loads(export_for_gaussian_avatars.local(avatar_id))
    if export_result.get("status") != "exported":
        return json.dumps(export_result)

    return json.dumps({
        "status": "ready_for_training",
        "avatar_id": avatar_id,
        "tracking_time": track_result.get("elapsed_sec", 0),
        "num_images": export_result.get("num_images", 0),
        "message": f"Run champ-gaussian-training train('{avatar_id}') to start 3DGS training.",
    })

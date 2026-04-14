"""
CHAMP Avatar — GaussianAvatars Training on Modal GPU

Trains a FLAME-rigged 3D Gaussian Splat from preprocessed head data.

Deploy:  modal deploy avatar/modal_gaussian_training_deploy.py
"""

import io
import json
import os
import re
import shutil
import subprocess
import tarfile
import time
import traceback
from pathlib import Path

import modal

app = modal.App("champ-gaussian-training")

training_vol = modal.Volume.from_name("champ-gaussian-training-data", create_if_missing=True)

ga_image = (
    modal.Image.from_registry(
        "nvidia/cuda:12.1.1-devel-ubuntu22.04",
        add_python="3.10",
    )
    .apt_install(
        "ffmpeg", "git", "wget", "colmap",
        "libgl1-mesa-glx", "libglib2.0-0", "libsm6", "libxrender1", "libxext6",
        "build-essential", "ninja-build",
    )
    .pip_install(
        "torch==2.2.0+cu121",
        "torchvision==0.17.0+cu121",
        extra_options="--index-url https://download.pytorch.org/whl/cu121",
    )
    .pip_install(
        "tqdm", "numpy==1.26.3", "matplotlib", "scipy", "tensorboard",
        "fvcore", "iopath", "plyfile", "tyro", "roma", "Pillow",
        "opencv-python-headless", "scikit-image", "lpips",
    )
    .env({
        "CXX": "g++", "CC": "gcc", "CUDA_HOME": "/usr/local/cuda",
        "TORCH_CUDA_ARCH_LIST": "8.0;8.6;9.0",
        "MAX_JOBS": "2",
    })
    .run_commands(
        "cd /root && git clone --recursive --depth 1 https://github.com/ShenhanQian/GaussianAvatars.git",
        "pip install wheel setuptools pip",
        "pip install --no-build-isolation chumpy",
        # Patch chumpy for numpy >= 1.24 (np.bool removed)
        "sed -i 's/from numpy import bool, int, float, complex, object, unicode, str, nan, inf/from numpy import nan, inf/' /usr/local/lib/python3.10/site-packages/chumpy/__init__.py",
        "pip install --no-build-isolation git+https://github.com/NVlabs/nvdiffrast",
        "cd /root/GaussianAvatars/submodules/diff-gaussian-rasterization && pip install .",
        "cd /root/GaussianAvatars/submodules/simple-knn && pip install .",
    )
)

VOLUME_MOUNT = "/data"
GA_ROOT = "/root/GaussianAvatars"

_fn_kwargs = dict(
    image=ga_image,
    gpu="A100",
    timeout=7200,
    scaledown_window=600,
    memory=65536,
    volumes={VOLUME_MOUNT: training_vol},
)


@app.function(**_fn_kwargs)
def health() -> str:
    import torch
    extensions_ok = True
    try:
        import diff_gaussian_rasterization  # noqa: F401
        import simple_knn  # noqa: F401
    except ImportError:
        extensions_ok = False

    flame_exists = (Path(VOLUME_MOUNT) / "flame_model" / "flame2023.pkl").exists()

    return json.dumps({
        "engine": "gaussian_avatars_trainer",
        "device": "cuda" if torch.cuda.is_available() else "cpu",
        "gpu": str(torch.cuda.get_device_name(0)) if torch.cuda.is_available() else "none",
        "vram_gb": round(torch.cuda.get_device_properties(0).total_memory / 1e9, 1) if torch.cuda.is_available() else 0,
        "cuda_extensions_compiled": extensions_ok,
        "flame_model_uploaded": flame_exists,
        "pytorch_version": str(torch.__version__),
        "cuda_version": str(torch.version.cuda),
        "status": "ready" if extensions_ok else "extensions_missing",
    })


@app.function(**_fn_kwargs)
def prepare_vhap_for_training(avatar_id: str) -> str:
    """Convert VHAP output to GaussianAvatars expected format."""
    import numpy as np
    import math

    vhap_dir = Path(VOLUME_MOUNT) / "vhap_data" / "monocular" / avatar_id
    avatars_dir = Path(VOLUME_MOUNT) / "avatars" / avatar_id
    output_dir = Path(VOLUME_MOUNT) / "ga_dataset" / avatar_id

    # Load tracked FLAME params
    params_path = avatars_dir / "tracked_flame_params_30.npz"
    if not params_path.exists():
        return json.dumps({"status": "error", "error": f"No tracked_flame_params_30.npz in {avatars_dir}"})

    params = dict(np.load(str(params_path), allow_pickle=True))
    # n_processed_frames can be 0 (VHAP quirk), use rotation array length instead
    n_frames = params["rotation"].shape[0]
    print(f"[PREPARE] DEBUG: rotation shape={params['rotation'].shape}, n_frames={n_frames}")
    focal_length = float(params["focal_length"][0])
    image_size = params["image_size"]  # [H, W]
    h, w = int(image_size[0]), int(image_size[1])

    print(f"[PREPARE] {n_frames} frames, {w}x{h}, focal={focal_length:.1f}")

    # Create output directory structure
    output_dir.mkdir(parents=True, exist_ok=True)
    images_out = output_dir / "images"
    images_out.mkdir(exist_ok=True)
    flame_out = output_dir / "flame_param"
    flame_out.mkdir(exist_ok=True)

    # Create canonical FLAME param (neutral pose, mean shape)
    canonical = {
        "shape": params["shape"],
        "expr": np.zeros(100, dtype=np.float32),
        "rotation": np.zeros(3, dtype=np.float32),
        "neck_pose": np.zeros(3, dtype=np.float32),
        "jaw_pose": np.zeros(3, dtype=np.float32),
        "eyes_pose": np.zeros(6, dtype=np.float32),
        "translation": np.zeros(3, dtype=np.float32),
        "static_offset": params["static_offset"],
    }
    np.savez(str(output_dir / "canonical_flame_param.npz"), **canonical)
    print("[PREPARE] Created canonical_flame_param.npz")

    # Compute camera FoV from focal length
    fovx = 2 * math.atan(w / (2 * focal_length))

    # Build transforms JSON and per-frame FLAME params
    # Use 90% train, 5% val, 5% test split
    frames_train = []
    frames_val = []
    frames_test = []

    images_src = vhap_dir / "images"
    src_images = sorted(images_src.glob("*.jpg"))

    for i in range(min(n_frames, len(src_images))):
        img_src = src_images[i]
        img_name = img_src.name

        # Copy image as PNG (GaussianAvatars defaults to .png extension)
        png_name = f"{img_src.stem}.png"
        img_dst = images_out / png_name
        if not img_dst.exists():
            from PIL import Image as PILImage
            PILImage.open(img_src).save(img_dst, "PNG")

        # Save per-frame FLAME params
        # GaussianAvatars expects:
        # shape: (300,)  — 1D
        # expr: (1, 100) — 2D (line 63 reads .shape[1], line 74 assigns to row)
        # rotation/neck/jaw: (3,) — 1D (line 74-78 assign to rows)
        # eyes_pose: (6,) — 1D
        # static_offset: (5143, 3) — 2D
        frame_flame = {
            "rotation": params["rotation"][i],
            "translation": params["translation"][i],
            "neck_pose": params["neck_pose"][i],
            "jaw_pose": params["jaw_pose"][i],
            "eyes_pose": params["eyes_pose"][i],
            "shape": params["shape"],
            "expr": params["expr"][i].reshape(1, -1),  # (1, 100) for .shape[1]
            "static_offset": params["static_offset"].squeeze(0),
        }
        flame_path = flame_out / f"{img_src.stem}.npz"
        np.savez(str(flame_path), **frame_flame)

        # Camera: fixed monocular camera looking at the face
        # Place camera ~0.6m in front of head along -Z axis (OpenGL convention)
        # VHAP rotation/translation handle head motion, camera stays fixed
        c2w = np.eye(4, dtype=np.float32)
        c2w[2, 3] = 0.6  # Camera 0.6m in front (Z axis)

        # Build per-frame camera using VHAP's tracked head pose
        # Convert VHAP rotation (axis-angle) to rotation matrix
        from scipy.spatial.transform import Rotation as R
        rot_aa = params["rotation"][i]  # axis-angle (3,)
        trans = params["translation"][i]  # (3,)

        rot_mat = R.from_rotvec(rot_aa).as_matrix()  # (3,3)

        # Camera-to-world: head moves, camera compensates
        # Place camera at translated position looking at the head
        c2w_frame = np.eye(4, dtype=np.float32)
        c2w_frame[:3, :3] = rot_mat.T  # Inverse rotation
        c2w_frame[:3, 3] = -rot_mat.T @ trans + np.array([0, 0, 0.6])

        frame_entry = {
            "file_path": f"images/{img_src.stem}",  # No extension — GA adds .png
            "flame_param_path": f"flame_param/{img_src.stem}.npz",
            "transform_matrix": c2w_frame.tolist(),
            "camera_angle_x": float(fovx),
            "timestep_index": i,
            "camera_index": 0,
            "w": w,
            "h": h,
        }

        # Split: frame 0 MUST be in train (GaussianAvatars loads meshes[0])
        # Then every 20th to val, every 20th+1 to test, rest to train
        if i == 0:
            frames_train.append(frame_entry)
        elif i % 20 == 0:
            frames_val.append(frame_entry)
        elif i % 20 == 1:
            frames_test.append(frame_entry)
        else:
            frames_train.append(frame_entry)

    # Write transforms JSONs
    for split, frames in [("train", frames_train), ("val", frames_val), ("test", frames_test)]:
        transforms = {
            "camera_angle_x": float(fovx),
            "frames": frames,
        }
        with open(output_dir / f"transforms_{split}.json", "w") as f:
            json.dump(transforms, f, indent=2)

    print(f"[PREPARE] Train: {len(frames_train)}, Val: {len(frames_val)}, Test: {len(frames_test)}")
    print(f"[PREPARE] Output: {output_dir}")

    training_vol.commit()

    return json.dumps({
        "status": "ready",
        "avatar_id": avatar_id,
        "output_dir": str(output_dir),
        "n_frames": n_frames,
        "train": len(frames_train),
        "val": len(frames_val),
        "test": len(frames_test),
    })


@app.function(**_fn_kwargs)
def upload_flame_model(flame_pkl_bytes: bytes, flame_masks_bytes: bytes) -> str:
    flame_dir = Path(VOLUME_MOUNT) / "flame_model"
    flame_dir.mkdir(parents=True, exist_ok=True)

    flame_path = flame_dir / "flame2023.pkl"
    with open(flame_path, "wb") as f:
        f.write(flame_pkl_bytes)

    masks_path = flame_dir / "FLAME_masks.pkl"
    with open(masks_path, "wb") as f:
        f.write(flame_masks_bytes)

    # Also copy to GaussianAvatars expected location
    ga_flame_dir = Path(GA_ROOT) / "flame_model" / "assets" / "flame"
    ga_flame_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(flame_path, ga_flame_dir / "flame2023.pkl")
    shutil.copy2(masks_path, ga_flame_dir / "FLAME_masks.pkl")

    training_vol.commit()
    print(f"[GA-TRAIN] FLAME model uploaded to {flame_dir}")
    return json.dumps({"status": "uploaded", "flame_dir": str(flame_dir)})


@app.function(**_fn_kwargs)
def upload_training_data(avatar_id: str, data_tar_bytes: bytes) -> str:
    data_dir = Path(VOLUME_MOUNT) / "avatars" / avatar_id
    data_dir.mkdir(parents=True, exist_ok=True)

    tar_buf = io.BytesIO(data_tar_bytes)
    with tarfile.open(fileobj=tar_buf, mode="r:*") as tar:
        tar.extractall(path=str(data_dir), filter="data")

    images_dir = data_dir / "images"
    if not images_dir.exists():
        nested = list(data_dir.glob("*/images"))
        if nested:
            images_dir = nested[0]

    num_images = len(list(images_dir.glob("*.png"))) + len(list(images_dir.glob("*.jpg"))) if images_dir.exists() else 0
    training_vol.commit()
    print(f"[GA-TRAIN] Uploaded {num_images} images for avatar '{avatar_id}'")

    return json.dumps({
        "status": "uploaded",
        "avatar_id": avatar_id,
        "data_dir": str(data_dir),
        "num_images": num_images,
    })


@app.function(**_fn_kwargs)
def train(
    avatar_id: str,
    iterations: int = 30_000,
    sh_degree: int = 3,
    white_background: bool = True,
    eval_split: bool = True,
    save_interval: int = 10_000,
) -> str:
    data_dir = Path(VOLUME_MOUNT) / "avatars" / avatar_id
    if not data_dir.exists():
        return json.dumps({"status": "error", "error": f"No data for avatar '{avatar_id}'. Upload first."})

    source_path = data_dir
    if not (source_path / "images").exists():
        candidates = list(data_dir.glob("*/images"))
        if candidates:
            source_path = candidates[0].parent
        else:
            # Check prepared GA dataset
            ga_path = Path(VOLUME_MOUNT) / "ga_dataset" / avatar_id
            vhap_path = Path(VOLUME_MOUNT) / "vhap_data" / "monocular" / avatar_id
            if (ga_path / "images").exists() and (ga_path / "canonical_flame_param.npz").exists():
                source_path = ga_path
                print(f"[GA-TRAIN] Using prepared dataset at {source_path}")
            elif (vhap_path / "images").exists():
                source_path = vhap_path
                for npz in data_dir.glob("*.npz"):
                    shutil.copy2(npz, source_path / npz.name)
                print(f"[GA-TRAIN] Using VHAP data at {source_path}")
            else:
                return json.dumps({"status": "error", "error": f"No data found. Run prepare_vhap_for_training('{avatar_id}') first."})

    # Check FLAME model
    ga_flame = Path(GA_ROOT) / "flame_model" / "assets" / "flame" / "flame2023.pkl"
    vol_flame = Path(VOLUME_MOUNT) / "flame_model" / "flame2023.pkl"

    if not ga_flame.exists():
        if vol_flame.exists():
            ga_flame.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(vol_flame, ga_flame)
            masks_src = Path(VOLUME_MOUNT) / "flame_model" / "FLAME_masks.pkl"
            if masks_src.exists():
                shutil.copy2(masks_src, ga_flame.parent / "FLAME_masks.pkl")
        else:
            return json.dumps({
                "status": "error",
                "error": "FLAME model not found. Upload via upload_flame_model() first.",
            })

    output_dir = Path(VOLUME_MOUNT) / "outputs" / avatar_id
    output_dir.mkdir(parents=True, exist_ok=True)

    job_id = f"{avatar_id}_{int(time.time())}"

    cmd = [
        "python", f"{GA_ROOT}/train.py",
        "-s", str(source_path),
        "-m", str(output_dir),
        "--iterations", str(iterations),
        "--sh_degree", str(sh_degree),
        "--bind_to_mesh",
        "--port", "0",
        "--save_iterations", *[str(i) for i in range(save_interval, iterations + 1, save_interval)],
        "--test_iterations", *[str(i) for i in range(save_interval, iterations + 1, save_interval)],
        "--checkpoint_iterations", *[str(i) for i in range(save_interval, iterations + 1, save_interval)],
    ]
    if white_background:
        cmd.append("--white_background")
    if eval_split:
        cmd.append("--eval")

    print(f"[GA-TRAIN] Starting: {' '.join(cmd)}")
    start_time = time.time()

    try:
        env = os.environ.copy()
        env["CUDA_VISIBLE_DEVICES"] = "0"

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=7000, env=env, cwd=GA_ROOT,
        )
        elapsed = time.time() - start_time

        metrics = _parse_training_output(result.stdout)

        ply_candidates = list(output_dir.rglob("point_cloud.ply"))
        ply_path = str(ply_candidates[-1]) if ply_candidates else None

        num_gaussians = 0
        if ply_path:
            try:
                from plyfile import PlyData
                num_gaussians = len(PlyData.read(ply_path).elements[0].data)
            except Exception:
                pass

        training_vol.commit()

        if result.returncode != 0:
            return json.dumps({
                "status": "error", "job_id": job_id,
                "returncode": result.returncode,
                "stderr": result.stderr[-2000:] if result.stderr else "",
                "stdout_tail": result.stdout[-1000:] if result.stdout else "",
                "elapsed_sec": elapsed,
            })

        return json.dumps({
            "status": "complete", "job_id": job_id, "avatar_id": avatar_id,
            "ply_path": ply_path, "output_dir": str(output_dir),
            "num_gaussians": num_gaussians, "iterations": iterations,
            "elapsed_sec": elapsed, "metrics": metrics,
        })

    except subprocess.TimeoutExpired:
        training_vol.commit()
        return json.dumps({"status": "timeout", "job_id": job_id, "error": "Training timed out after 7000s."})
    except Exception:
        return json.dumps({"status": "error", "job_id": job_id, "error": traceback.format_exc()[-2000:]})


@app.function(**_fn_kwargs)
def list_avatars() -> str:
    avatars_dir = Path(VOLUME_MOUNT) / "avatars"
    outputs_dir = Path(VOLUME_MOUNT) / "outputs"
    avatars = {}

    if avatars_dir.exists():
        for d in avatars_dir.iterdir():
            if d.is_dir():
                images = list(d.rglob("*.png")) + list(d.rglob("*.jpg"))
                avatars[d.name] = {"has_data": True, "num_images": len(images)}

    if outputs_dir.exists():
        for d in outputs_dir.iterdir():
            if d.is_dir():
                plys = list(d.rglob("point_cloud.ply"))
                if d.name not in avatars:
                    avatars[d.name] = {"has_data": False, "num_images": 0}
                avatars[d.name]["has_output"] = True
                avatars[d.name]["num_plys"] = len(plys)

    flame_exists = (Path(VOLUME_MOUNT) / "flame_model" / "flame2023.pkl").exists()
    return json.dumps({"avatars": avatars, "flame_model_uploaded": flame_exists})


def _parse_training_output(stdout: str) -> dict:
    metrics = {}
    if not stdout:
        return metrics
    eval_pattern = re.compile(
        r"\[ITER (\d+)\] Evaluating (\w+): L1 ([\d.]+) PSNR ([\d.]+) SSIM ([\d.]+) LPIPS ([\d.]+)"
    )
    for match in eval_pattern.finditer(stdout):
        iteration, split, l1, psnr, ssim, lpips_val = match.groups()
        metrics[f"{split}_iter_{iteration}"] = {
            "l1": float(l1), "psnr": float(psnr),
            "ssim": float(ssim), "lpips": float(lpips_val),
        }
    return metrics

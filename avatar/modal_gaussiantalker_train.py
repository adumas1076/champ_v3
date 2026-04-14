"""
GaussianTalker Training on Modal — 500-frame subset

Trains the talking head Gaussian Splat model on Genesis's preprocessed data.
Then renders a preview to verify quality.
"""

import modal
import json

app = modal.App("champ-gaussiantalker-train")

vol = modal.Volume.from_name("champ-gaussiantalker-data", create_if_missing=True)

train_image = (
    modal.Image.from_registry("nvidia/cuda:11.8.0-devel-ubuntu22.04", add_python="3.10")
    .apt_install("ffmpeg", "git", "libgl1-mesa-glx", "libglib2.0-0", "libsm6", "libxext6", "libxrender-dev", "ninja-build", "build-essential", "clang")
    .pip_install(
        "torch==2.1.0", "torchvision==0.16.0", "torchaudio==2.1.0",
        extra_index_url="https://download.pytorch.org/whl/cu118",
    )
    .pip_install(
        "tensorflow-cpu==2.13.0",
        "face_alignment", "scipy", "scikit-learn", "opencv-python-headless",
        "numpy<2", "Pillow", "tqdm", "numba", "resampy", "python_speech_features",
        "pandas", "configargparse", "fvcore", "iopath",
        "lpips", "plyfile", "pytorch_msssim", "open3d", "imageio", "imageio[ffmpeg]",
        "einops", "wandb", "typing_extensions>=4.5",
        "openmim",
    )
    .pip_install(
        "pytorch3d",
        find_links="https://dl.fbaipublicfiles.com/pytorch3d/packaging/wheels/py310_cu118_pyt210/download.html",
    )
    .pip_install("wheel", "setuptools")
    .run_commands("mim install mmcv==1.6.0")
    .run_commands(
        # Clone repo + submodules + build CUDA extensions all in one step
        "rm -rf /root/GaussianTalker"
        " && git clone https://github.com/cvlab-kaist/GaussianTalker.git /root/GaussianTalker"
        " && rm -rf /root/GaussianTalker/submodules/custom-bg-depth-diff-gaussian-rasterization"
        " && git clone --recursive https://github.com/joungbinlee/custom-bg-depth-diff-gaussian-rasterization.git /root/GaussianTalker/submodules/custom-bg-depth-diff-gaussian-rasterization"
        " && rm -rf /root/GaussianTalker/submodules/simple-knn"
        " && git clone https://github.com/camenduru/simple-knn.git /root/GaussianTalker/submodules/simple-knn"
        " && cd /root/GaussianTalker/submodules/custom-bg-depth-diff-gaussian-rasterization && pip install ."
        " && cd /root/GaussianTalker/submodules/simple-knn && pip install ."
        " && pip install --upgrade typing_extensions",
        gpu="A10G",
    )
)

DATA_DIR = "/data"
GT_REPO = "/root/GaussianTalker"


@app.function(
    image=train_image,
    gpu="A10G",
    volumes={DATA_DIR: vol},
    timeout=18000,  # 5 hours
)
def train_and_render(avatar_id: str = "genesis", iterations: int = 10000):
    """Train GaussianTalker on preprocessed dataset, then render preview."""
    import os
    import sys
    import subprocess
    import shutil
    import time
    import glob

    # Reload volume to get latest data (fixes stale cache)
    vol.reload()

    base_dir = f"{DATA_DIR}/datasets/{avatar_id}"
    model_dir = f"{DATA_DIR}/outputs/{avatar_id}"
    os.makedirs(model_dir, exist_ok=True)

    # GaussianTalker repo + CUDA submodules are pre-built in the image at /root/GaussianTalker
    print("[TRAIN] Using pre-built GaussianTalker from image")

    # Copy 3DMM files and regenerate with container numpy
    dmm_src = f"{DATA_DIR}/models/3DMM"
    dmm_dst = f"{GT_REPO}/data_utils/face_tracking/3DMM"
    face_tracking_dir = f"{GT_REPO}/data_utils/face_tracking"
    if os.path.isdir(dmm_src):
        os.makedirs(dmm_dst, exist_ok=True)
        for f in os.listdir(dmm_src):
            shutil.copy2(os.path.join(dmm_src, f), os.path.join(dmm_dst, f))
        mat_file = os.path.join(dmm_dst, "01_MorphableModel.mat")
        if os.path.exists(mat_file):
            subprocess.run("python convert_BFM.py", shell=True, capture_output=True, cwd=face_tracking_dir)

    # Copy face parsing model
    parsing_src = f"{DATA_DIR}/models/79999_iter.pth"
    parsing_dst = f"{GT_REPO}/data_utils/face_parsing/79999_iter.pth"
    if os.path.exists(parsing_src):
        shutil.copy2(parsing_src, parsing_dst)

    # Verify dataset exists
    required = ["track_params.pt", "transforms_train.json", "aud_ds.npy", "bc.jpg"]
    for f in required:
        path = os.path.join(base_dir, f)
        if not os.path.exists(path):
            return json.dumps({"status": "error", "message": f"Missing: {path}"})

    # Also need au.csv — create a dummy if OpenFace wasn't run
    au_path = os.path.join(base_dir, "au.csv")
    if not os.path.exists(au_path):
        print("[TRAIN] Creating dummy au.csv (no OpenFace data)...")
        import numpy as np
        import pandas as pd
        import torch
        params = torch.load(os.path.join(base_dir, "track_params.pt"), map_location="cpu")
        n = params["euler"].shape[0]
        # AU45_r = eye blink, default to 0 (eyes open)
        df = pd.DataFrame({" AU45_r": np.zeros(n)})
        df.to_csv(au_path, index=False)
        print(f"[TRAIN] Dummy au.csv created: {n} frames")

    os.chdir(GT_REPO)
    sys.path.insert(0, GT_REPO)

    # ── TRAIN ──────────────────────────────────────────────────────────
    print(f"\n[TRAIN] Starting training: {iterations} iterations")
    print(f"[TRAIN] Dataset: {base_dir}")
    print(f"[TRAIN] Output: {model_dir}")
    t0 = time.time()

    # Downscale images if too large for GPU memory (A10G = 24GB)
    import cv2
    import torch
    import numpy as np
    import glob as _glob
    sample = None
    ori_imgs = sorted(_glob.glob(f"{base_dir}/ori_imgs/*.jpg"))
    # Also check torso_imgs size (may differ from ori_imgs if previous run partially downscaled)
    torso_check = _glob.glob(f"{base_dir}/torso_imgs/*.png")
    torso_needs_resize = False
    if torso_check:
        t_sample = cv2.imread(torso_check[0], cv2.IMREAD_UNCHANGED)
        if t_sample is not None and max(t_sample.shape[:2]) > 600:
            torso_needs_resize = True
    if ori_imgs:
        sample = cv2.imread(ori_imgs[0])
        h, w = sample.shape[:2]
        if max(h, w) > 600 or torso_needs_resize:
            target = 512
            scale = target / max(h, w)
            new_w, new_h = int(w * scale), int(h * scale)
            print(f"[TRAIN] Downscaling images for training: {w}x{h} -> {new_w}x{new_h}")

            train_imgs_dir = f"{base_dir}/train_imgs"
            os.makedirs(train_imgs_dir, exist_ok=True)

            for img_path in ori_imgs:
                fname = os.path.basename(img_path)
                img = cv2.imread(img_path)
                img_small = cv2.resize(img, (new_w, new_h))
                cv2.imwrite(os.path.join(train_imgs_dir, fname), img_small)

            # Also downscale gt_imgs and torso_imgs
            for subdir in ["gt_imgs", "torso_imgs"]:
                src_dir = f"{base_dir}/{subdir}"
                if os.path.isdir(src_dir):
                    count = 0
                    for f in os.listdir(src_dir):
                        fpath = os.path.join(src_dir, f)
                        img = cv2.imread(fpath, cv2.IMREAD_UNCHANGED)
                        if img is not None and (img.shape[1] != new_w or img.shape[0] != new_h):
                            img_small = cv2.resize(img, (new_w, new_h))
                            cv2.imwrite(fpath, img_small)
                            count += 1
                    print(f"[TRAIN] Downscaled {count} files in {subdir}")

            # Downscale parsing masks
            parsing_dir = f"{base_dir}/parsing"
            if os.path.isdir(parsing_dir):
                for f in os.listdir(parsing_dir):
                    fpath = os.path.join(parsing_dir, f)
                    img = cv2.imread(fpath)
                    if img is not None:
                        img_small = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_NEAREST)
                        cv2.imwrite(fpath, img_small)

            # Downscale background
            bc_path = f"{base_dir}/bc.jpg"
            if os.path.exists(bc_path):
                bc = cv2.imread(bc_path)
                bc_small = cv2.resize(bc, (new_w, new_h))
                cv2.imwrite(bc_path, bc_small)

            # Scale landmarks in ori_imgs
            for lms_path in _glob.glob(f"{base_dir}/ori_imgs/*.lms"):
                import numpy as np
                lms = np.loadtxt(lms_path)
                lms *= scale
                np.savetxt(lms_path, lms, fmt='%f')

            # Overwrite ori_imgs with downscaled
            for f in os.listdir(train_imgs_dir):
                shutil.copy2(os.path.join(train_imgs_dir, f), os.path.join(f"{base_dir}/ori_imgs", f))

            # Update track_params focal and trans
            track_path = f"{base_dir}/track_params.pt"
            if os.path.exists(track_path):
                params = torch.load(track_path, map_location="cpu")
                params["focal"] = params["focal"] * scale
                params["trans"] = params["trans"] * scale
                torch.save(params, track_path)

            # Fix transforms JSON with correct integer dimensions
            for tf_name in ["transforms_train.json", "transforms_val.json"]:
                tf_path = os.path.join(base_dir, tf_name)
                if os.path.exists(tf_path):
                    with open(tf_path, 'r') as f:
                        tf_data = json.load(f)
                    tf_data["cx"] = new_w / 2.0
                    tf_data["cy"] = new_h / 2.0
                    tf_data["w"] = int(new_w)
                    tf_data["h"] = int(new_h)
                    # Scale focal length
                    if "focal_len" in tf_data:
                        tf_data["focal_len"] = tf_data["focal_len"] * scale
                    with open(tf_path, 'w') as f:
                        json.dump(tf_data, f, indent=2)

            # Commit downscaled data to volume
            vol.commit()
            print(f"[TRAIN] Downscale complete and committed to volume")

    # Force-check ALL image directories are at target resolution
    target_max = 512
    for img_dir, ext, interp in [
        (f"{base_dir}/ori_imgs", "*.jpg", cv2.INTER_AREA),
        (f"{base_dir}/gt_imgs", "*.jpg", cv2.INTER_AREA),
        (f"{base_dir}/torso_imgs", "*.png", cv2.INTER_AREA),
        (f"{base_dir}/parsing", "*.png", cv2.INTER_NEAREST),
    ]:
        if not os.path.isdir(img_dir):
            continue
        files = _glob.glob(os.path.join(img_dir, ext))
        if not files:
            continue
        check = cv2.imread(files[0], cv2.IMREAD_UNCHANGED)
        if check is None:
            continue
        ch, cw = check.shape[:2]
        if max(ch, cw) > target_max + 10:
            scale_f = target_max / max(ch, cw)
            nw, nh = int(cw * scale_f), int(ch * scale_f)
            print(f"[TRAIN] Resizing {os.path.basename(img_dir)}: {cw}x{ch} -> {nw}x{nh} ({len(files)} files)")
            for fpath in files:
                img = cv2.imread(fpath, cv2.IMREAD_UNCHANGED)
                if img is not None:
                    img = cv2.resize(img, (nw, nh), interpolation=interp)
                    cv2.imwrite(fpath, img)

    # Also check bc.jpg
    bc_path = f"{base_dir}/bc.jpg"
    if os.path.exists(bc_path):
        bc = cv2.imread(bc_path)
        if bc is not None and max(bc.shape[:2]) > target_max + 10:
            scale_f = target_max / max(bc.shape[:2])
            nw, nh = int(bc.shape[1] * scale_f), int(bc.shape[0] * scale_f)
            cv2.imwrite(bc_path, cv2.resize(bc, (nw, nh)))
            print(f"[TRAIN] Resized bc.jpg to {nw}x{nh}")

    vol.commit()

    # Fix transforms cx/cy to match actual image dimensions on disk
    sample_img = cv2.imread(f"{base_dir}/ori_imgs/0.jpg")
    if sample_img is not None:
        actual_h, actual_w = sample_img.shape[:2]
        for tf_name in ["transforms_train.json", "transforms_val.json"]:
            tf_path = os.path.join(base_dir, tf_name)
            if os.path.exists(tf_path):
                with open(tf_path, 'r') as f:
                    tf_data = json.load(f)
                old_w = int(tf_data.get("cx", 0) * 2)
                if old_w != actual_w:
                    scale_factor = actual_w / old_w
                    tf_data["cx"] = actual_w / 2.0
                    tf_data["cy"] = actual_h / 2.0
                    tf_data["focal_len"] = tf_data["focal_len"] * scale_factor
                    with open(tf_path, 'w') as f:
                        json.dump(tf_data, f, indent=2)
                    print(f"[TRAIN] Fixed {tf_name}: cx/cy scaled to {actual_w}x{actual_h} (factor={scale_factor:.4f})")

    # Patch GaussianTalker's talking_dataset_readers.py to cast w/h to int
    # (their code does contents["w"] = contents["cx"] * 2 which creates floats,
    #  then passes to cv2.resize which needs ints)
    reader_path = f"{GT_REPO}/scene/talking_dataset_readers.py"
    with open(reader_path, 'r') as f:
        reader_code = f.read()
    if 'int(contents["cx"]' not in reader_code:
        reader_code = reader_code.replace(
            'contents["w"] = contents["cx"] * 2',
            'contents["w"] = int(contents["cx"] * 2)'
        )
        reader_code = reader_code.replace(
            'contents["h"] = contents["cy"] * 2',
            'contents["h"] = int(contents["cy"] * 2)'
        )
        with open(reader_path, 'w') as f:
            f.write(reader_code)
        print("[TRAIN] Patched talking_dataset_readers.py: w/h cast to int")

    train_cmd = (
        f"python {GT_REPO}/train.py "
        f"-s {base_dir} "
        f"--model_path {model_dir} "
        f"--configs {GT_REPO}/arguments/64_dim_1_transformer.py "
        f"--iterations {iterations}"
    )
    proc = subprocess.run(train_cmd, shell=True, capture_output=True, text=True, timeout=14400)  # 4 hours

    train_time = time.time() - t0
    print(f"[TRAIN] Training finished in {train_time/60:.1f} min (exit code: {proc.returncode})")

    if proc.returncode != 0:
        return json.dumps({
            "status": "error",
            "phase": "training",
            "elapsed_min": round(train_time / 60, 1),
            "stdout_tail": proc.stdout[-2000:] if proc.stdout else "",
            "stderr_tail": proc.stderr[-2000:] if proc.stderr else "",
        })

    # ── RENDER PREVIEW ─────────────────────────────────────────────────
    print(f"\n[RENDER] Rendering preview...")
    t0 = time.time()

    render_cmd = (
        f"python {GT_REPO}/render.py "
        f"-s {base_dir} "
        f"--model_path {model_dir} "
        f"--configs {GT_REPO}/arguments/64_dim_1_transformer.py "
        f"--iteration {iterations} "
        f"--batch 64 "
        f"--skip_train"
    )
    proc_render = subprocess.run(render_cmd, shell=True, capture_output=True, text=True, timeout=1800)

    render_time = time.time() - t0
    print(f"[RENDER] Render finished in {render_time/60:.1f} min (exit code: {proc_render.returncode})")

    # Find rendered images
    render_dir = f"{model_dir}/test/ours_{iterations}"
    rendered_files = []
    if os.path.isdir(render_dir):
        for root, dirs, files in os.walk(render_dir):
            for f in sorted(files)[:10]:
                if f.endswith(".png") or f.endswith(".jpg"):
                    rendered_files.append(os.path.join(root, f))

    # Save results to volume
    vol.commit()

    result = {
        "status": "complete" if proc.returncode == 0 else "error",
        "iterations": iterations,
        "train_min": round(train_time / 60, 1),
        "render_min": round(render_time / 60, 1),
        "model_dir": model_dir,
        "rendered_files": rendered_files[:5],
        "stdout_tail": proc.stdout[-500:] if proc.stdout else "",
    }

    if proc_render.returncode != 0:
        result["render_error"] = proc_render.stderr[-500:] if proc_render.stderr else ""

    return json.dumps(result, indent=2)

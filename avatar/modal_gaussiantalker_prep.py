"""
GaussianTalker Preprocessing on Modal — Step-by-Step Dry Run

Runs process.py steps individually on Genesis video.
Reports pass/fail for each step. No training.

Steps:
  1. Extract audio (ffmpeg)
  2. Audio features (DeepSpeech — TF CPU)
  3. Extract frames at 25fps (ffmpeg)
  4. Face parsing / semantic masks (BiSeNet)
  5. Background extraction (sklearn)
  6. Torso + GT images (scipy compositing)
  7. Face landmarks (face_alignment)
  8. Face tracking / 3DMM fitting (Basel model + CUDA)
  9. Save transforms JSON
"""

import modal
import json

app = modal.App("champ-gaussiantalker-prep")

# Persistent volume for data
vol = modal.Volume.from_name("champ-gaussiantalker-data", create_if_missing=True)

# Docker image — PyTorch GPU + TF CPU + all deps
gt_image = (
    modal.Image.debian_slim(python_version="3.10")
    .apt_install("ffmpeg", "git", "libgl1-mesa-glx", "libglib2.0-0", "libsm6", "libxext6", "libxrender-dev")
    .pip_install(
        "torch==2.1.0", "torchvision==0.16.0", "torchaudio==2.1.0",
        extra_index_url="https://download.pytorch.org/whl/cu118",
    )
    .pip_install(
        "tensorflow-cpu==2.13.0",  # CPU only — no CUDA conflict with PyTorch
        "face_alignment",
        "scipy",
        "scikit-learn",
        "opencv-python-headless",
        "numpy<2",
        "Pillow",
        "tqdm",
        "numba",
        "resampy",
        "python_speech_features",
        "pandas",
        "configargparse",
    )
    .pip_install("fvcore", "iopath")
    .apt_install("ninja-build", "g++")
    .run_commands(
        # Install pytorch3d from conda-forge (pre-built with CUDA)
        'pip install pytorch3d -f https://dl.fbaipublicfiles.com/pytorch3d/packaging/wheels/py310_cu118_pyt210/download.html || '
        # Fallback: build from specific release with CUDA
        'FORCE_CUDA=1 TORCH_CUDA_ARCH_LIST="8.6" pip install "pytorch3d==0.7.8" --no-build-isolation',
        gpu="A10G",
    )
)

DATA_DIR = "/data"
GT_REPO = "/root/GaussianTalker"


def _upload_file_to_volume(local_path: str, vol_path: str):
    """Helper to upload a local file to the Modal volume."""
    with open(local_path, "rb") as f:
        data = f.read()
    vol = modal.Volume.from_name("champ-gaussiantalker-data")
    vol.write_file(vol_path, data)
    return len(data)


@app.function(image=gt_image, volumes={DATA_DIR: vol}, timeout=600)
def health():
    """Verify environment is working."""
    import torch
    import cv2
    import subprocess

    results = {}
    results["torch"] = torch.__version__
    results["cuda"] = torch.cuda.is_available()
    if results["cuda"]:
        results["gpu"] = torch.cuda.get_device_name(0)
    results["cv2"] = cv2.__version__
    results["ffmpeg"] = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True).stdout.split("\n")[0]

    try:
        import tensorflow as tf
        results["tensorflow"] = tf.__version__
    except Exception as e:
        results["tensorflow"] = f"FAIL: {e}"

    try:
        import face_alignment
        results["face_alignment"] = "OK"
    except Exception as e:
        results["face_alignment"] = f"FAIL: {e}"

    return json.dumps(results, indent=2)


@app.function(
    image=gt_image,
    gpu="A10G",
    volumes={DATA_DIR: vol},
    timeout=10800,  # 3 hours for heavy tracking
)
def run_preprocessing(avatar_id: str = "genesis", steps: str = "all"):
    """
    Run GaussianTalker process.py steps on the video.

    Args:
        avatar_id: Name of the avatar dataset
        steps: Comma-separated step numbers (1-9) or "all"
    """
    import os
    import sys
    import subprocess
    import shutil
    import time
    import torch
    import numpy as np
    import cv2
    import glob

    base_dir = f"{DATA_DIR}/datasets/{avatar_id}"
    video_path = f"{base_dir}/{avatar_id}.mp4"
    ori_imgs_dir = f"{base_dir}/ori_imgs"
    parsing_dir = f"{base_dir}/parsing"
    gt_imgs_dir = f"{base_dir}/gt_imgs"
    torso_imgs_dir = f"{base_dir}/torso_imgs"

    # Ensure directories exist
    for d in [ori_imgs_dir, parsing_dir, gt_imgs_dir, torso_imgs_dir]:
        os.makedirs(d, exist_ok=True)

    # Check video exists
    if not os.path.exists(video_path):
        return json.dumps({"status": "error", "message": f"Video not found: {video_path}. Upload it first."})

    # Clone GaussianTalker repo if not present
    if not os.path.exists(GT_REPO):
        subprocess.run(
            ["git", "clone", "--depth", "1", "https://github.com/cvlab-kaist/GaussianTalker.git", GT_REPO],
            check=True, capture_output=True,
        )

    # Copy 3DMM model files from volume to repo
    dmm_src = f"{DATA_DIR}/models/3DMM"
    dmm_dst = f"{GT_REPO}/data_utils/face_tracking/3DMM"
    if os.path.isdir(dmm_src):
        os.makedirs(dmm_dst, exist_ok=True)
        for f in os.listdir(dmm_src):
            shutil.copy2(os.path.join(dmm_src, f), os.path.join(dmm_dst, f))

        # Regenerate 3DMM_info.npy with THIS container's numpy version
        # (avoids numpy._core version mismatch from local machine)
        face_tracking_dir = f"{GT_REPO}/data_utils/face_tracking"
        mat_file = os.path.join(face_tracking_dir, "3DMM", "01_MorphableModel.mat")
        if os.path.exists(mat_file):
            print(f"[PREP] Regenerating 3DMM_info.npy in {face_tracking_dir}...")
            proc = subprocess.run(
                "python convert_BFM.py",
                shell=True, capture_output=True, text=True,
                cwd=face_tracking_dir,
            )
            if proc.returncode != 0:
                print(f"[PREP] convert_BFM stderr: {proc.stderr[:300]}")
            else:
                info_path = os.path.join(face_tracking_dir, "3DMM", "3DMM_info.npy")
                if os.path.exists(info_path):
                    print(f"[PREP] 3DMM_info.npy regenerated: {os.path.getsize(info_path)} bytes")
                else:
                    print("[PREP] WARNING: 3DMM_info.npy not created after convert_BFM.py")
        print(f"[PREP] 3DMM files: {os.listdir(dmm_dst)}")

    # Copy face parsing model
    parsing_model_src = f"{DATA_DIR}/models/79999_iter.pth"
    parsing_model_dst = f"{GT_REPO}/data_utils/face_parsing/79999_iter.pth"
    if os.path.exists(parsing_model_src):
        shutil.copy2(parsing_model_src, parsing_model_dst)
        print(f"[PREP] Face parsing model copied")

    # Determine which steps to run
    if steps == "all":
        run_steps = list(range(1, 10))
    else:
        run_steps = [int(s.strip()) for s in steps.split(",")]

    results = {"avatar_id": avatar_id, "steps": {}}
    sys.path.insert(0, GT_REPO)
    os.chdir(GT_REPO)

    # ── STEP 1: Extract audio ──────────────────────────────────────────
    if 1 in run_steps:
        print("\n[STEP 1] Extracting audio...")
        t0 = time.time()
        try:
            wav_path = f"{base_dir}/aud.wav"

            # Full audio
            cmd = f'ffmpeg -y -i {video_path} -f wav -ar 16000 {wav_path}'
            subprocess.run(cmd, shell=True, check=True, capture_output=True)

            # Get duration for train/val split
            probe = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", video_path],
                capture_output=True, text=True,
            )
            total_duration = float(probe.stdout.strip())
            train_duration = total_duration * 10 / 11
            test_start = total_duration - (total_duration / 11)

            # Train audio
            subprocess.run(
                f'ffmpeg -y -i {video_path} -f wav -ar 16000 -t {train_duration} {base_dir}/aud_train.wav',
                shell=True, check=True, capture_output=True,
            )
            # Test audio
            subprocess.run(
                f'ffmpeg -y -i {video_path} -f wav -ar 16000 -ss {test_start} {base_dir}/aud_novel.wav',
                shell=True, check=True, capture_output=True,
            )

            exists = os.path.exists(wav_path)
            size = os.path.getsize(wav_path) if exists else 0
            results["steps"]["1_audio"] = {
                "status": "PASS" if exists and size > 0 else "FAIL",
                "duration_sec": round(total_duration, 1),
                "wav_size": size,
                "elapsed": round(time.time() - t0, 1),
            }
            vol.commit()
        except Exception as e:
            results["steps"]["1_audio"] = {"status": "FAIL", "error": str(e)}

    # ── STEP 2: DeepSpeech audio features ──────────────────────────────
    if 2 in run_steps:
        print("\n[STEP 2] Extracting DeepSpeech audio features...")
        t0 = time.time()
        try:
            wav_path = f"{base_dir}/aud.wav"

            # Run DeepSpeech as isolated subprocess (uses TensorFlow)
            cmd = f'python extract_ds_features.py --input {wav_path}'
            proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=600, cwd=f"{GT_REPO}/data_utils/deepspeech_features")

            npy_path = wav_path.replace('.wav', '.npy')
            ds_path = wav_path.replace('.wav', '_ds.npy')

            # Copy to aud_ds.npy if the extraction produced aud.npy
            if os.path.exists(npy_path):
                shutil.copy2(npy_path, f"{base_dir}/aud_ds.npy")
                feats = np.load(f"{base_dir}/aud_ds.npy")
                results["steps"]["2_audio_features"] = {
                    "status": "PASS",
                    "shape": list(feats.shape),
                    "elapsed": round(time.time() - t0, 1),
                }
            else:
                results["steps"]["2_audio_features"] = {
                    "status": "FAIL",
                    "error": "npy not produced",
                    "stdout": proc.stdout[-500:] if proc.stdout else "",
                    "stderr": proc.stderr[-500:] if proc.stderr else "",
                }
            vol.commit()
        except Exception as e:
            results["steps"]["2_audio_features"] = {"status": "FAIL", "error": str(e)[:300]}

    # ── STEP 3: Extract frames ─────────────────────────────────────────
    if 3 in run_steps:
        print("\n[STEP 3] Extracting video frames at 25fps...")
        t0 = time.time()
        try:
            cmd = f'ffmpeg -y -i {video_path} -vf fps=25 -qmin 1 -q:v 1 -start_number 0 {ori_imgs_dir}/%d.jpg'
            subprocess.run(cmd, shell=True, check=True, capture_output=True)

            n_frames = len(glob.glob(f"{ori_imgs_dir}/*.jpg"))
            if n_frames > 0:
                sample = cv2.imread(f"{ori_imgs_dir}/0.jpg")
                h, w = sample.shape[:2]
            else:
                h, w = 0, 0

            results["steps"]["3_frames"] = {
                "status": "PASS" if n_frames > 0 else "FAIL",
                "n_frames": n_frames,
                "resolution": f"{w}x{h}",
                "elapsed": round(time.time() - t0, 1),
            }
            vol.commit()
        except Exception as e:
            results["steps"]["3_frames"] = {"status": "FAIL", "error": str(e)}

    # ── STEP 4: Face parsing (semantic masks) ──────────────────────────
    if 4 in run_steps:
        print("\n[STEP 4] Running face parsing...")
        t0 = time.time()
        try:
            cmd = f'python {GT_REPO}/data_utils/face_parsing/test.py --respath={parsing_dir} --imgpath={ori_imgs_dir}'
            proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5400)

            n_masks = len(glob.glob(f"{parsing_dir}/*.png"))
            results["steps"]["4_parsing"] = {
                "status": "PASS" if n_masks > 0 else "FAIL",
                "n_masks": n_masks,
                "elapsed": round(time.time() - t0, 1),
            }
            if n_masks == 0:
                results["steps"]["4_parsing"]["stderr"] = proc.stderr[-500:] if proc.stderr else ""
            vol.commit()
        except Exception as e:
            results["steps"]["4_parsing"] = {"status": "FAIL", "error": str(e)[:300]}

    # ── STEP 5: Background extraction ──────────────────────────────────
    if 5 in run_steps:
        print("\n[STEP 5] Extracting background...")
        t0 = time.time()
        try:
            sys.path.insert(0, GT_REPO)
            from data_utils.process import extract_background
            extract_background(base_dir, ori_imgs_dir)

            bc_exists = os.path.exists(f"{base_dir}/bc.jpg")
            results["steps"]["5_background"] = {
                "status": "PASS" if bc_exists else "FAIL",
                "elapsed": round(time.time() - t0, 1),
            }
            vol.commit()
        except Exception as e:
            results["steps"]["5_background"] = {"status": "FAIL", "error": str(e)[:300]}

    # ── STEP 6: Torso + GT images ──────────────────────────────────────
    if 6 in run_steps:
        print("\n[STEP 6] Extracting torso and GT images...")
        t0 = time.time()
        try:
            from data_utils.process import extract_torso_and_gt
            extract_torso_and_gt(base_dir, ori_imgs_dir)

            n_gt = len(glob.glob(f"{gt_imgs_dir}/*.jpg"))
            n_torso = len(glob.glob(f"{torso_imgs_dir}/*.png"))
            results["steps"]["6_torso_gt"] = {
                "status": "PASS" if n_gt > 0 and n_torso > 0 else "FAIL",
                "n_gt_imgs": n_gt,
                "n_torso_imgs": n_torso,
                "elapsed": round(time.time() - t0, 1),
            }
            vol.commit()
        except Exception as e:
            results["steps"]["6_torso_gt"] = {"status": "FAIL", "error": str(e)[:300]}

    # ── STEP 7: Face landmarks ─────────────────────────────────────────
    if 7 in run_steps:
        print("\n[STEP 7] Extracting face landmarks...")
        t0 = time.time()
        try:
            from data_utils.process import extract_landmarks
            extract_landmarks(ori_imgs_dir)

            n_lms = len(glob.glob(f"{ori_imgs_dir}/*.lms"))
            results["steps"]["7_landmarks"] = {
                "status": "PASS" if n_lms > 0 else "FAIL",
                "n_landmarks": n_lms,
                "elapsed": round(time.time() - t0, 1),
            }
            vol.commit()
        except Exception as e:
            results["steps"]["7_landmarks"] = {"status": "FAIL", "error": str(e)[:300]}

    # ── STEP 8: Face tracking (3DMM) ───────────────────────────────────
    if 8 in run_steps:
        print("\n[STEP 8] Running face tracking (3DMM)...")
        t0 = time.time()
        try:
            n_frames = len(glob.glob(f"{ori_imgs_dir}/*.jpg"))
            sample = cv2.imread(f"{ori_imgs_dir}/0.jpg")
            h, w = sample.shape[:2]

            # GaussianTalker's face tracker is designed for ~512x512
            # Our frames are 1920x1080 — too heavy for iterative 3DMM fitting
            # Resize frames + landmarks for tracking, keep originals for training
            tracking_h, tracking_w = h, w
            if h > 600 or w > 600:
                scale = 512.0 / max(h, w)
                tracking_h = int(h * scale)
                tracking_w = int(w * scale)
                print(f"[STEP 8] Resizing for tracking: {w}x{h} -> {tracking_w}x{tracking_h}")

                # Create resized copies for tracking
                tracking_dir = f"{base_dir}/tracking_imgs"
                os.makedirs(tracking_dir, exist_ok=True)
                for i in range(n_frames):
                    src = f"{ori_imgs_dir}/{i}.jpg"
                    dst = f"{tracking_dir}/{i}.jpg"
                    if os.path.exists(src):
                        img = cv2.imread(src)
                        img_resized = cv2.resize(img, (tracking_w, tracking_h))
                        cv2.imwrite(dst, img_resized)

                    # Scale landmarks too
                    lms_src = f"{ori_imgs_dir}/{i}.lms"
                    lms_dst = f"{tracking_dir}/{i}.lms"
                    if os.path.exists(lms_src):
                        lms = np.loadtxt(lms_src)
                        lms *= scale
                        np.savetxt(lms_dst, lms, fmt='%f')

                print(f"[STEP 8] Resized {n_frames} frames + landmarks for tracking")
                track_path_input = tracking_dir
            else:
                track_path_input = ori_imgs_dir

            cmd = (
                f'python {GT_REPO}/data_utils/face_tracking/face_tracker.py '
                f'--path={track_path_input} --img_h={tracking_h} --img_w={tracking_w} --frame_num={n_frames}'
            )
            proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=7200)

            # Move track_params.pt to base_dir if it was saved in tracking_dir
            tracking_params = f"{tracking_dir}/track_params.pt" if tracking_h != h else None
            if tracking_params and os.path.exists(tracking_params):
                # Scale translation back to original resolution
                params = torch.load(tracking_params, map_location="cpu")
                params["trans"] = params["trans"] / scale
                params["focal"] = params["focal"] / scale
                torch.save(params, f"{base_dir}/track_params.pt")
                print(f"[STEP 8] Scaled tracking params back to original resolution")
            elif os.path.exists(f"{base_dir}/track_params.pt"):
                pass  # already in right place

            track_path = f"{base_dir}/track_params.pt"
            if os.path.exists(track_path):
                params = torch.load(track_path, map_location="cpu")
                keys = list(params.keys())
                results["steps"]["8_tracking"] = {
                    "status": "PASS",
                    "keys": keys,
                    "n_frames_tracked": params["euler"].shape[0] if "euler" in params else 0,
                    "elapsed": round(time.time() - t0, 1),
                }
            else:
                results["steps"]["8_tracking"] = {
                    "status": "FAIL",
                    "error": "track_params.pt not produced",
                    "stdout": proc.stdout[-500:] if proc.stdout else "",
                    "stderr": proc.stderr[-500:] if proc.stderr else "",
                }
            vol.commit()
        except Exception as e:
            results["steps"]["8_tracking"] = {"status": "FAIL", "error": str(e)[:300]}

    # ── STEP 9: Save transforms ────────────────────────────────────────
    if 9 in run_steps:
        print("\n[STEP 9] Saving transforms JSON...")
        t0 = time.time()
        try:
            from data_utils.process import save_transforms
            save_transforms(base_dir, ori_imgs_dir)

            train_exists = os.path.exists(f"{base_dir}/transforms_train.json")
            val_exists = os.path.exists(f"{base_dir}/transforms_val.json")

            if train_exists:
                with open(f"{base_dir}/transforms_train.json") as f:
                    train_data = json.load(f)
                n_train = len(train_data.get("frames", []))
            else:
                n_train = 0

            results["steps"]["9_transforms"] = {
                "status": "PASS" if train_exists and val_exists else "FAIL",
                "train_frames": n_train,
                "elapsed": round(time.time() - t0, 1),
            }
            vol.commit()
        except Exception as e:
            results["steps"]["9_transforms"] = {"status": "FAIL", "error": str(e)[:300]}

    # ── Summary ────────────────────────────────────────────────────────
    passed = sum(1 for s in results["steps"].values() if s.get("status") == "PASS")
    failed = sum(1 for s in results["steps"].values() if s.get("status") == "FAIL")
    results["summary"] = {
        "passed": passed,
        "failed": failed,
        "total": passed + failed,
    }

    print(f"\n[DONE] {passed}/{passed+failed} steps passed")
    return json.dumps(results, indent=2)


@app.function(
    image=gt_image,
    gpu="A10G",
    volumes={DATA_DIR: vol},
    timeout=1800,
)
def micro_test_tracking(avatar_id: str = "genesis", n_frames: int = 50):
    """
    Micro-test: run ONLY face tracking (step 8) on a small subset.
    Proves the tracker works before committing to a full run.
    """
    import os
    import sys
    import subprocess
    import shutil
    import time
    import torch
    import numpy as np
    import cv2
    import glob

    base_dir = f"{DATA_DIR}/datasets/{avatar_id}"
    ori_imgs_dir = f"{base_dir}/ori_imgs"
    micro_dir = f"{base_dir}/micro_test"
    os.makedirs(micro_dir, exist_ok=True)

    # Clone repo if needed
    if not os.path.exists(GT_REPO):
        subprocess.run(
            ["git", "clone", "--depth", "1", "https://github.com/cvlab-kaist/GaussianTalker.git", GT_REPO],
            check=True, capture_output=True,
        )

    # Copy 3DMM model files
    dmm_src = f"{DATA_DIR}/models/3DMM"
    dmm_dst = f"{GT_REPO}/data_utils/face_tracking/3DMM"
    face_tracking_dir = f"{GT_REPO}/data_utils/face_tracking"
    if os.path.isdir(dmm_src):
        os.makedirs(dmm_dst, exist_ok=True)
        for f in os.listdir(dmm_src):
            shutil.copy2(os.path.join(dmm_src, f), os.path.join(dmm_dst, f))

        # Regenerate 3DMM_info.npy with container numpy
        mat_file = os.path.join(dmm_dst, "01_MorphableModel.mat")
        if os.path.exists(mat_file):
            subprocess.run(
                "python convert_BFM.py",
                shell=True, capture_output=True,
                cwd=face_tracking_dir,
            )

    # Copy N frames + landmarks to micro dir, downscaled to 512
    sample = cv2.imread(f"{ori_imgs_dir}/0.jpg")
    orig_h, orig_w = sample.shape[:2]
    scale = 512.0 / max(orig_h, orig_w)
    target_w = int(orig_w * scale)
    target_h = int(orig_h * scale)

    print(f"[MICRO] Preparing {n_frames} frames at {target_w}x{target_h} (scale={scale:.4f})")
    t0 = time.time()

    for i in range(n_frames):
        src_img = f"{ori_imgs_dir}/{i}.jpg"
        src_lms = f"{ori_imgs_dir}/{i}.lms"
        if not os.path.exists(src_img) or not os.path.exists(src_lms):
            continue

        # Resize image
        img = cv2.imread(src_img)
        img_small = cv2.resize(img, (target_w, target_h))
        cv2.imwrite(f"{micro_dir}/{i}.jpg", img_small)

        # Scale landmarks
        lms = np.loadtxt(src_lms)
        lms_scaled = lms * scale
        np.savetxt(f"{micro_dir}/{i}.lms", lms_scaled, fmt='%f')

    prep_time = time.time() - t0
    print(f"[MICRO] Prep done in {prep_time:.1f}s")

    # Run face tracker on micro subset
    print(f"[MICRO] Running face tracker on {n_frames} frames...")
    t0 = time.time()

    cmd = (
        f'python {GT_REPO}/data_utils/face_tracking/face_tracker.py '
        f'--path={micro_dir} --img_h={target_h} --img_w={target_w} --frame_num={n_frames}'
    )
    proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=1200)

    track_time = time.time() - t0

    # Check result
    track_path = f"{base_dir}/track_params.pt"
    result = {
        "n_frames": n_frames,
        "resolution": f"{target_w}x{target_h}",
        "scale": round(scale, 4),
        "prep_sec": round(prep_time, 1),
        "track_sec": round(track_time, 1),
    }

    if os.path.exists(track_path):
        params = torch.load(track_path, map_location="cpu")
        result["status"] = "PASS"
        result["keys"] = list(params.keys())
        result["euler_shape"] = list(params["euler"].shape) if "euler" in params else None
        result["focal"] = float(params["focal"][0]) if "focal" in params else None
        result["trans_shape"] = list(params["trans"].shape) if "trans" in params else None
    else:
        result["status"] = "FAIL"
        result["stdout"] = proc.stdout[-500:] if proc.stdout else ""
        result["stderr"] = proc.stderr[-500:] if proc.stderr else ""

    import json
    return json.dumps(result, indent=2)


@app.function(image=gt_image, volumes={DATA_DIR: vol}, timeout=300)
def upload_assets(avatar_id: str = "genesis"):
    """Upload Genesis video + models to the volume. Called from local."""
    import os
    results = {}

    # Check what's on the volume
    datasets_dir = f"{DATA_DIR}/datasets/{avatar_id}"
    models_dir = f"{DATA_DIR}/models"
    os.makedirs(datasets_dir, exist_ok=True)
    os.makedirs(f"{models_dir}/3DMM", exist_ok=True)

    video_path = f"{datasets_dir}/{avatar_id}.mp4"
    results["video_exists"] = os.path.exists(video_path)
    results["video_size"] = os.path.getsize(video_path) if results["video_exists"] else 0

    dmm_path = f"{models_dir}/3DMM/3DMM_info.npy"
    results["3dmm_exists"] = os.path.exists(dmm_path)

    parsing_path = f"{models_dir}/79999_iter.pth"
    results["parsing_model_exists"] = os.path.exists(parsing_path)

    return json.dumps(results, indent=2)

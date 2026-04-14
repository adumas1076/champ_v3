"""
GaussianTalker Clean Pipeline — 500 frames, 512x288, from scratch.

ONE script does everything:
  1. Extract 500 frames at 512x288 from video
  2. Extract audio
  3. DeepSpeech features
  4. Face parsing
  5. Background extraction
  6. Torso + GT images
  7. Face landmarks
  8. Face tracking (3DMM)
  9. Save transforms
  10. Create dummy au.csv
  11. Train (10K iterations)
  12. Render preview

No mixed state. No patching. No volume caching fights.
"""

import modal
import json

app = modal.App("champ-gt-clean")

vol = modal.Volume.from_name("champ-gaussiantalker-data", create_if_missing=True)

# Training image — everything pre-built
image = (
    modal.Image.from_registry("nvidia/cuda:11.8.0-devel-ubuntu22.04", add_python="3.10")
    .apt_install("ffmpeg", "git", "libgl1-mesa-glx", "libglib2.0-0", "libsm6", "libxext6",
                 "libxrender-dev", "ninja-build", "build-essential", "clang")
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
        "einops", "wandb", "typing_extensions>=4.5", "openmim",
    )
    .run_commands("mim install mmcv==1.6.0")
    .pip_install("wheel", "setuptools")
    .pip_install(
        "pytorch3d",
        find_links="https://dl.fbaipublicfiles.com/pytorch3d/packaging/wheels/py310_cu118_pyt210/download.html",
    )
    .run_commands(
        # Clone GaussianTalker + build CUDA extensions
        "git clone https://github.com/cvlab-kaist/GaussianTalker.git /root/GaussianTalker"
        " && rm -rf /root/GaussianTalker/submodules/custom-bg-depth-diff-gaussian-rasterization"
        " && git clone --recursive https://github.com/joungbinlee/custom-bg-depth-diff-gaussian-rasterization.git"
        "   /root/GaussianTalker/submodules/custom-bg-depth-diff-gaussian-rasterization"
        " && rm -rf /root/GaussianTalker/submodules/simple-knn"
        " && git clone https://github.com/camenduru/simple-knn.git"
        "   /root/GaussianTalker/submodules/simple-knn"
        " && cd /root/GaussianTalker/submodules/custom-bg-depth-diff-gaussian-rasterization && python setup.py install"
        " && cd /root/GaussianTalker/submodules/simple-knn && python setup.py install"
        " && pip install --upgrade typing_extensions",
        gpu="A10G",
    )
)

DATA_DIR = "/data"
GT_REPO = "/root/GaussianTalker"


@app.function(
    image=image,
    gpu="A10G",
    volumes={DATA_DIR: vol},
    timeout=18000,  # 5 hours max
)
def clean_pipeline(avatar_id: str = "genesis", n_frames: int = 500, iterations: int = 10000):
    """
    Clean end-to-end pipeline: video → 500 frames at 512px → preprocess → train → render.
    """
    import os
    import sys
    import subprocess
    import shutil
    import time
    import glob
    import cv2
    import torch
    import numpy as np

    # ── SETUP ──────────────────────────────────────────────────────────
    video_src = f"{DATA_DIR}/datasets/{avatar_id}/{avatar_id}.mp4"

    # Clean workspace on LOCAL disk (not volume — avoids caching)
    base_dir = f"/tmp/genesis_clean"
    model_dir = f"{DATA_DIR}/outputs/{avatar_id}_clean"

    if os.path.exists(base_dir):
        shutil.rmtree(base_dir)
    os.makedirs(base_dir, exist_ok=True)
    os.makedirs(model_dir, exist_ok=True)

    # Copy video to local
    shutil.copy2(video_src, f"{base_dir}/{avatar_id}.mp4")
    video_path = f"{base_dir}/{avatar_id}.mp4"

    ori_imgs_dir = f"{base_dir}/ori_imgs"
    parsing_dir = f"{base_dir}/parsing"
    gt_imgs_dir = f"{base_dir}/gt_imgs"
    torso_imgs_dir = f"{base_dir}/torso_imgs"
    for d in [ori_imgs_dir, parsing_dir, gt_imgs_dir, torso_imgs_dir]:
        os.makedirs(d, exist_ok=True)

    results = {"avatar_id": avatar_id, "n_frames": n_frames, "steps": {}}
    t_total = time.time()

    # ── STEP 1: Extract N frames at 512x288 ───────────────────────────
    print(f"\n[1/12] Extracting {n_frames} frames at 512x288...")
    t0 = time.time()

    # Get video duration to calculate frame sampling
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", video_path],
        capture_output=True, text=True,
    )
    duration = float(probe.stdout.strip())
    target_fps = n_frames / duration  # Sample evenly across video

    cmd = (f'ffmpeg -y -i {video_path} '
           f'-vf "fps={target_fps},scale=512:-2" '
           f'-qmin 1 -q:v 1 -start_number 0 '
           f'{ori_imgs_dir}/%d.jpg')
    subprocess.run(cmd, shell=True, check=True, capture_output=True)

    actual_frames = len(glob.glob(f"{ori_imgs_dir}/*.jpg"))
    sample = cv2.imread(f"{ori_imgs_dir}/0.jpg")
    h, w = sample.shape[:2]
    results["steps"]["1_frames"] = {
        "status": "PASS" if actual_frames > 0 else "FAIL",
        "n_frames": actual_frames, "resolution": f"{w}x{h}",
        "elapsed": round(time.time() - t0, 1),
    }
    print(f"  {actual_frames} frames at {w}x{h} in {time.time()-t0:.1f}s")

    # ── STEP 2: Extract audio ──────────────────────────────────────────
    print(f"\n[2/12] Extracting audio...")
    t0 = time.time()
    wav_path = f"{base_dir}/aud.wav"
    subprocess.run(f'ffmpeg -y -i {video_path} -f wav -ar 16000 {wav_path}',
                   shell=True, check=True, capture_output=True)

    train_dur = duration * 10 / 11
    subprocess.run(f'ffmpeg -y -i {video_path} -f wav -ar 16000 -t {train_dur} {base_dir}/aud_train.wav',
                   shell=True, check=True, capture_output=True)
    subprocess.run(f'ffmpeg -y -i {video_path} -f wav -ar 16000 -ss {duration - duration/11} {base_dir}/aud_novel.wav',
                   shell=True, check=True, capture_output=True)
    results["steps"]["2_audio"] = {"status": "PASS", "elapsed": round(time.time() - t0, 1)}
    print(f"  Done in {time.time()-t0:.1f}s")

    # ── STEP 3: DeepSpeech features ───────────────────────────────────
    print(f"\n[3/12] DeepSpeech features...")
    t0 = time.time()
    proc = subprocess.run(
        f'python extract_ds_features.py --input {wav_path}',
        shell=True, capture_output=True, text=True, timeout=600,
        cwd=f"{GT_REPO}/data_utils/deepspeech_features",
    )
    npy_path = wav_path.replace('.wav', '.npy')
    if os.path.exists(npy_path):
        shutil.copy2(npy_path, f"{base_dir}/aud_ds.npy")
        feats = np.load(f"{base_dir}/aud_ds.npy")
        results["steps"]["3_deepspeech"] = {"status": "PASS", "shape": list(feats.shape),
                                             "elapsed": round(time.time() - t0, 1)}
        print(f"  Shape: {feats.shape} in {time.time()-t0:.1f}s")
    else:
        results["steps"]["3_deepspeech"] = {"status": "FAIL", "error": proc.stderr[-300:]}
        print(f"  FAIL: {proc.stderr[-200:]}")

    # ── STEP 4: Face parsing ──────────────────────────────────────────
    print(f"\n[4/12] Face parsing...")
    t0 = time.time()

    # Copy parsing model
    parsing_model_src = f"{DATA_DIR}/models/79999_iter.pth"
    parsing_model_dst = f"{GT_REPO}/data_utils/face_parsing/79999_iter.pth"
    if os.path.exists(parsing_model_src):
        shutil.copy2(parsing_model_src, parsing_model_dst)

    proc = subprocess.run(
        f'python {GT_REPO}/data_utils/face_parsing/test.py --respath={parsing_dir} --imgpath={ori_imgs_dir} --modelpath={GT_REPO}/data_utils/face_parsing/79999_iter.pth',
        shell=True, capture_output=True, text=True, timeout=3600,
    )
    if proc.returncode != 0:
        print(f"  Parsing stderr: {proc.stderr[-300:]}")
    n_masks = len(glob.glob(f"{parsing_dir}/*.png"))
    # Check what files are actually in parsing dir
    if n_masks == 0:
        # Parsing might have saved elsewhere — check
        all_files = os.listdir(parsing_dir) if os.path.isdir(parsing_dir) else []
        print(f"  Parsing dir contents: {all_files[:10]}")
    else:
        # Verify naming matches ori_imgs
        sample_mask = sorted(glob.glob(f"{parsing_dir}/*.png"))[0]
        print(f"  Sample mask: {os.path.basename(sample_mask)}")
    results["steps"]["4_parsing"] = {"status": "PASS" if n_masks > 0 else "FAIL",
                                      "n_masks": n_masks, "elapsed": round(time.time() - t0, 1)}
    print(f"  {n_masks} masks in {time.time()-t0:.1f}s")

    # ── STEP 5: Background extraction ─────────────────────────────────
    print(f"\n[5/12] Background extraction...")
    t0 = time.time()
    sys.path.insert(0, GT_REPO)
    os.chdir(GT_REPO)
    from data_utils.process import extract_background, extract_torso_and_gt, extract_landmarks, save_transforms
    extract_background(base_dir, ori_imgs_dir)
    results["steps"]["5_background"] = {"status": "PASS" if os.path.exists(f"{base_dir}/bc.jpg") else "FAIL",
                                         "elapsed": round(time.time() - t0, 1)}
    print(f"  Done in {time.time()-t0:.1f}s")

    # ── STEP 6: Torso + GT images ────────────────────────────────────
    print(f"\n[6/12] Torso + GT images...")
    t0 = time.time()
    extract_torso_and_gt(base_dir, ori_imgs_dir)
    n_gt = len(glob.glob(f"{gt_imgs_dir}/*.jpg"))
    n_torso = len(glob.glob(f"{torso_imgs_dir}/*.png"))
    results["steps"]["6_torso_gt"] = {"status": "PASS" if n_gt > 0 else "FAIL",
                                       "n_gt": n_gt, "n_torso": n_torso,
                                       "elapsed": round(time.time() - t0, 1)}
    print(f"  {n_gt} GT + {n_torso} torso in {time.time()-t0:.1f}s")

    # ── STEP 7: Face landmarks ────────────────────────────────────────
    print(f"\n[7/12] Face landmarks...")
    t0 = time.time()
    extract_landmarks(ori_imgs_dir)
    n_lms = len(glob.glob(f"{ori_imgs_dir}/*.lms"))
    results["steps"]["7_landmarks"] = {"status": "PASS" if n_lms > 0 else "FAIL",
                                        "n_landmarks": n_lms, "elapsed": round(time.time() - t0, 1)}
    print(f"  {n_lms} landmarks in {time.time()-t0:.1f}s")

    # ── STEP 8: Face tracking (3DMM) ─────────────────────────────────
    print(f"\n[8/12] Face tracking (3DMM)...")
    t0 = time.time()

    # Copy 3DMM files
    dmm_src = f"{DATA_DIR}/models/3DMM"
    dmm_dst = f"{GT_REPO}/data_utils/face_tracking/3DMM"
    if os.path.isdir(dmm_src):
        os.makedirs(dmm_dst, exist_ok=True)
        for f in os.listdir(dmm_src):
            shutil.copy2(os.path.join(dmm_src, f), os.path.join(dmm_dst, f))
        # Regenerate with container numpy
        subprocess.run("python convert_BFM.py", shell=True, capture_output=True,
                       cwd=f"{GT_REPO}/data_utils/face_tracking")

    cmd = (f'python {GT_REPO}/data_utils/face_tracking/face_tracker.py '
           f'--path={ori_imgs_dir} --img_h={h} --img_w={w} --frame_num={actual_frames}')
    proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=7200)

    track_path = f"{base_dir}/track_params.pt"
    if os.path.exists(track_path):
        params = torch.load(track_path, map_location="cpu")
        results["steps"]["8_tracking"] = {
            "status": "PASS",
            "n_tracked": params["euler"].shape[0],
            "focal": float(params["focal"][0]),
            "elapsed": round(time.time() - t0, 1),
        }
        print(f"  Tracked {params['euler'].shape[0]} frames, focal={params['focal'][0]:.0f} in {time.time()-t0:.1f}s")
    else:
        results["steps"]["8_tracking"] = {"status": "FAIL", "error": proc.stderr[-300:],
                                           "elapsed": round(time.time() - t0, 1)}
        print(f"  FAIL in {time.time()-t0:.1f}s")
        return json.dumps(results, indent=2)

    # ── STEP 9: Save transforms ───────────────────────────────────────
    print(f"\n[9/12] Save transforms...")
    t0 = time.time()
    save_transforms(base_dir, ori_imgs_dir)

    # Fix w/h to be integers
    for tf_name in ["transforms_train.json", "transforms_val.json"]:
        tf_path = os.path.join(base_dir, tf_name)
        if os.path.exists(tf_path):
            with open(tf_path, 'r') as f:
                tf = json.load(f)
            tf["w"] = int(tf["cx"] * 2)
            tf["h"] = int(tf["cy"] * 2)
            with open(tf_path, 'w') as f:
                json.dump(tf, f, indent=2)

    results["steps"]["9_transforms"] = {"status": "PASS", "elapsed": round(time.time() - t0, 1)}
    print(f"  Done in {time.time()-t0:.1f}s")

    # ── STEP 10: Dummy au.csv ─────────────────────────────────────────
    print(f"\n[10/12] Creating au.csv...")
    import pandas as pd
    n = params["euler"].shape[0]
    pd.DataFrame({" AU45_r": np.zeros(n)}).to_csv(f"{base_dir}/au.csv", index=False)
    results["steps"]["10_au"] = {"status": "PASS"}

    # ── Verify dataset ────────────────────────────────────────────────
    print(f"\n[VERIFY] Dataset check:")
    for d, ext in [("ori_imgs", "*.jpg"), ("parsing", "*.png"), ("gt_imgs", "*.jpg"), ("torso_imgs", "*.png")]:
        count = len(glob.glob(f"{base_dir}/{d}/{ext}"))
        print(f"  {d}: {count}")

    # Patch GaussianTalker reader
    reader_path = f"{GT_REPO}/scene/talking_dataset_readers.py"
    with open(reader_path, 'r') as f:
        code = f.read()
    if 'int(contents["cx"]' not in code:
        code = code.replace('contents["w"] = contents["cx"] * 2', 'contents["w"] = int(contents["cx"] * 2)')
        code = code.replace('contents["h"] = contents["cy"] * 2', 'contents["h"] = int(contents["cy"] * 2)')
        with open(reader_path, 'w') as f:
            f.write(code)
        print("  Patched reader: w/h cast to int")

    # ── STEP 11: Train ────────────────────────────────────────────────
    print(f"\n[11/12] Training {iterations} iterations...")
    t0 = time.time()

    train_cmd = (
        f"python {GT_REPO}/train.py "
        f"-s {base_dir} "
        f"--model_path {model_dir} "
        f"--configs {GT_REPO}/arguments/64_dim_1_transformer.py "
        f"--iterations {iterations}"
    )
    proc = subprocess.run(train_cmd, shell=True, capture_output=True, text=True, timeout=14400)

    train_time = time.time() - t0
    results["steps"]["11_training"] = {
        "status": "PASS" if proc.returncode == 0 else "FAIL",
        "elapsed_min": round(train_time / 60, 1),
        "returncode": proc.returncode,
    }
    if proc.returncode != 0:
        results["steps"]["11_training"]["stderr"] = proc.stderr[-500:]
        print(f"  FAIL in {train_time/60:.1f} min")
    else:
        print(f"  PASS in {train_time/60:.1f} min")

    # Save training output to volume
    vol.commit()

    # ── STEP 12: Render preview ───────────────────────────────────────
    if proc.returncode == 0:
        print(f"\n[12/12] Rendering preview...")
        t0 = time.time()
        render_cmd = (
            f"python {GT_REPO}/render.py "
            f"-s {base_dir} "
            f"--model_path {model_dir} "
            f"--configs {GT_REPO}/arguments/64_dim_1_transformer.py "
            f"--iteration {iterations} "
            f"--batch 64 --skip_train"
        )
        proc_r = subprocess.run(render_cmd, shell=True, capture_output=True, text=True, timeout=1800)
        results["steps"]["12_render"] = {
            "status": "PASS" if proc_r.returncode == 0 else "FAIL",
            "elapsed_min": round((time.time() - t0) / 60, 1),
        }
        vol.commit()

    total_time = time.time() - t_total
    results["total_min"] = round(total_time / 60, 1)
    results["status"] = "complete" if all(
        s.get("status") == "PASS" for s in results["steps"].values()
    ) else "partial"

    print(f"\n{'='*50}")
    print(f"TOTAL: {total_time/60:.1f} min")
    for name, step in results["steps"].items():
        print(f"  [{step.get('status','?')}] {name}")
    print(f"{'='*50}")

    return json.dumps(results, indent=2)

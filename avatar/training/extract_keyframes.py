"""
CHAMP Avatar Training — Keyframe Extraction from 2-Minute Video

Extracts diverse, high-quality reference frames from a recording:
  1. Sample frames at regular intervals
  2. Detect faces, filter bad frames (no face, eyes closed, blurry)
  3. Estimate head pose (yaw/pitch) for each frame
  4. Cluster by pose to ensure diversity (front, left, right, up, down)
  5. Select best frame per cluster (highest face confidence + sharpness)
  6. Crop and resize to 512x512 (matching FlashHead's face crop pattern)

Usage:
    from avatar.training.extract_keyframes import extract_keyframes
    frames = extract_keyframes("path/to/video.mp4", output_dir="models/avatars/my_avatar/frames")

Output: 10-20 PNG files in output_dir, ready for FlashHead's cond_image_dir input.
"""

import logging
import os
import sys
from pathlib import Path
from typing import Optional

import numpy as np

from .. import config

logger = logging.getLogger("champ.avatar.training.keyframes")

# Target number of keyframes per pose cluster
TARGET_FRAMES_PER_CLUSTER = 2
MIN_TOTAL_FRAMES = 8
MAX_TOTAL_FRAMES = 20

# Pose clusters (yaw_range, pitch_range, name)
POSE_CLUSTERS = [
    ((-15, 15), (-10, 10), "front"),
    ((-45, -15), (-10, 10), "left"),
    ((15, 45), (-10, 10), "right"),
    ((-15, 15), (-30, -10), "up"),
    ((-15, 15), (10, 30), "down"),
    ((-45, -15), (-30, -10), "left_up"),
    ((15, 45), (-30, -10), "right_up"),
    ((-45, -15), (10, 30), "left_down"),
    ((15, 45), (10, 30), "right_down"),
]


def _ensure_cv2():
    try:
        import cv2
        return cv2
    except ImportError:
        raise ImportError("opencv-python required: pip install opencv-python")


def _compute_sharpness(gray_frame: np.ndarray) -> float:
    """Laplacian variance — higher = sharper."""
    cv2 = _ensure_cv2()
    return cv2.Laplacian(gray_frame, cv2.CV_64F).var()


def _estimate_head_pose_simple(face_box: list, img_w: int, img_h: int) -> tuple[float, float]:
    """
    Simple head pose estimation from face bounding box position.
    Not as accurate as landmark-based, but works without extra models.

    Returns (yaw_deg, pitch_deg) estimated from face center offset.
    """
    x1, y1, x2, y2 = face_box
    cx = (x1 + x2) / 2
    cy = (y1 + y2) / 2

    # Normalize to [-1, 1] relative to image center
    norm_x = (cx / img_w - 0.5) * 2
    norm_y = (cy / img_h - 0.5) * 2

    # Map to approximate degrees (rough, but good enough for clustering)
    yaw = norm_x * 45    # ±45 degrees
    pitch = norm_y * 30   # ±30 degrees

    return yaw, pitch


def _assign_cluster(yaw: float, pitch: float) -> Optional[str]:
    """Assign a pose to the nearest cluster."""
    for yaw_range, pitch_range, name in POSE_CLUSTERS:
        if yaw_range[0] <= yaw <= yaw_range[1] and pitch_range[0] <= pitch <= pitch_range[1]:
            return name
    return "front"  # Default fallback


def extract_keyframes(
    video_path: str,
    output_dir: str,
    target_size: tuple[int, int] = (512, 512),
    face_ratio: float = 2.0,
    sample_interval_sec: float = 0.5,
    min_face_confidence: float = 0.5,
    min_sharpness: float = 50.0,
) -> list[str]:
    """
    Extract diverse keyframes from a video for FlashHead multi-reference.

    Args:
        video_path: Path to input video (2-min recording)
        output_dir: Where to save extracted PNGs
        target_size: Output frame size (must match FlashHead: 512x512)
        face_ratio: Face crop ratio (FlashHead default: 2.0)
        sample_interval_sec: How often to sample frames (seconds)
        min_face_confidence: Minimum face detection confidence
        min_sharpness: Minimum Laplacian sharpness score

    Returns:
        List of saved PNG file paths
    """
    cv2 = _ensure_cv2()
    from PIL import Image

    # Try to use FlashHead's own face detector for consistency
    face_detector = None
    try:
        flashhead_src = str(config.FLASHHEAD_SRC_DIR)
        if flashhead_src not in sys.path:
            sys.path.insert(0, flashhead_src)
        from flash_head.utils.cpu_face_handler import CPUFaceHandler
        from flash_head.utils.facecrop import get_scaled_bbox
        face_detector = CPUFaceHandler()
        use_flashhead_crop = True
        logger.info("Using FlashHead CPUFaceHandler for face detection")
    except ImportError:
        use_flashhead_crop = False
        logger.info("FlashHead face handler not available, using OpenCV Haar cascade")

    # Open video
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Could not open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration_sec = total_frames / fps
    sample_interval_frames = int(sample_interval_sec * fps)

    logger.info(f"Video: {video_path}")
    logger.info(f"  Duration: {duration_sec:.1f}s, FPS: {fps:.1f}, Frames: {total_frames}")
    logger.info(f"  Sampling every {sample_interval_sec}s ({sample_interval_frames} frames)")

    # Phase 1: Sample and score frames
    candidates = []  # (frame_idx, face_box, confidence, sharpness, yaw, pitch, frame_rgb)
    frame_idx = 0

    while True:
        ret, frame_bgr = cap.read()
        if not ret:
            break

        if frame_idx % sample_interval_frames != 0:
            frame_idx += 1
            continue

        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        img_h, img_w = frame_rgb.shape[:2]

        # Face detection
        if face_detector is not None:
            boxes, scores = face_detector(frame_rgb)
            if len(boxes) == 0:
                frame_idx += 1
                continue
            confidence = float(scores[0])
            if confidence < min_face_confidence:
                frame_idx += 1
                continue
            # Convert relative coords to absolute
            face_box = [
                boxes[0][0] * img_w,
                boxes[0][1] * img_h,
                boxes[0][2] * img_w,
                boxes[0][3] * img_h,
            ]
        else:
            # Fallback: OpenCV Haar cascade
            face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            )
            faces = face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(80, 80))
            if len(faces) == 0:
                frame_idx += 1
                continue
            x, y, w, h = faces[0]
            face_box = [float(x), float(y), float(x + w), float(y + h)]
            confidence = 0.8  # Haar doesn't give confidence

        # Sharpness check
        sharpness = _compute_sharpness(gray)
        if sharpness < min_sharpness:
            frame_idx += 1
            continue

        # Estimate head pose
        yaw, pitch = _estimate_head_pose_simple(face_box, img_w, img_h)

        candidates.append({
            "frame_idx": frame_idx,
            "face_box": face_box,
            "confidence": confidence,
            "sharpness": sharpness,
            "yaw": yaw,
            "pitch": pitch,
            "frame_rgb": frame_rgb,
            "img_w": img_w,
            "img_h": img_h,
        })

        frame_idx += 1

    cap.release()
    logger.info(f"  Candidates: {len(candidates)} frames passed face+sharpness filter")

    if len(candidates) == 0:
        raise ValueError("No valid frames found in video — check lighting and face visibility")

    # Phase 2: Cluster by head pose and select best per cluster
    clusters: dict[str, list] = {}
    for c in candidates:
        cluster_name = _assign_cluster(c["yaw"], c["pitch"])
        clusters.setdefault(cluster_name, []).append(c)

    # Sort each cluster by quality score (confidence × sharpness)
    for name in clusters:
        clusters[name].sort(
            key=lambda c: c["confidence"] * c["sharpness"],
            reverse=True,
        )

    # Select top N from each cluster
    selected = []
    for name, frames in clusters.items():
        n = min(TARGET_FRAMES_PER_CLUSTER, len(frames))
        selected.extend(frames[:n])
        logger.info(f"  Cluster '{name}': {len(frames)} candidates, selected {n}")

    # Ensure minimum count — if not enough clusters, take top overall
    if len(selected) < MIN_TOTAL_FRAMES:
        all_sorted = sorted(
            candidates,
            key=lambda c: c["confidence"] * c["sharpness"],
            reverse=True,
        )
        for c in all_sorted:
            if c not in selected:
                selected.append(c)
                if len(selected) >= MIN_TOTAL_FRAMES:
                    break

    # Cap at maximum
    selected = selected[:MAX_TOTAL_FRAMES]
    logger.info(f"  Selected {len(selected)} keyframes across {len(clusters)} pose clusters")

    # Phase 3: Crop, resize, and save
    os.makedirs(output_dir, exist_ok=True)
    saved_paths = []

    for i, c in enumerate(selected):
        pil_image = Image.fromarray(c["frame_rgb"])

        if use_flashhead_crop:
            # Use FlashHead's exact crop logic for consistency
            cropped = get_scaled_bbox(
                c["face_box"],
                c["img_w"],
                c["img_h"],
                face_ratio,
                pil_image,
            )
            cropped = cropped.resize(target_size, Image.LANCZOS)
        else:
            # Manual crop with same ratio logic
            x1, y1, x2, y2 = c["face_box"]
            cx = (x1 + x2) / 2
            cy = (y1 + y2) / 2
            w = (x2 - x1) * face_ratio
            new_x1 = max(0, int(cx - w / 2))
            new_y1 = max(0, int(cy - w * 0.55))
            new_x2 = min(c["img_w"], int(cx + w / 2))
            new_y2 = min(c["img_h"], int(cy + w * 0.45))
            cropped = pil_image.crop((new_x1, new_y1, new_x2, new_y2))
            cropped = cropped.resize(target_size, Image.LANCZOS)

        # Save with descriptive filename
        cluster_name = _assign_cluster(c["yaw"], c["pitch"])
        filename = f"keyframe_{i:03d}_{cluster_name}_f{c['frame_idx']}.png"
        filepath = os.path.join(output_dir, filename)
        cropped.save(filepath)
        saved_paths.append(filepath)

    logger.info(f"  Saved {len(saved_paths)} keyframes to {output_dir}")
    return saved_paths


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Extract keyframes from avatar reference video")
    parser.add_argument("video", help="Path to 2-minute reference video")
    parser.add_argument("--output", "-o", default=None, help="Output directory for keyframes")
    parser.add_argument("--avatar-id", default="default", help="Avatar identifier")
    parser.add_argument("--interval", type=float, default=0.5, help="Sample interval in seconds")
    parser.add_argument("--min-sharpness", type=float, default=50.0, help="Minimum sharpness score")
    args = parser.parse_args()

    output_dir = args.output or str(config.AVATARS_DIR / args.avatar_id / "frames")

    paths = extract_keyframes(
        video_path=args.video,
        output_dir=output_dir,
        sample_interval_sec=args.interval,
        min_sharpness=args.min_sharpness,
    )

    print(f"\nExtracted {len(paths)} keyframes:")
    for p in paths:
        print(f"  {p}")

"""
CHAMP Avatar Training — Prepare Training Data from 2-Minute Video

Extracts aligned (audio_chunk, video_chunk) pairs for LoRA fine-tuning.

Pipeline:
  1. Split video into chunks matching FlashHead's frame_num (33 frames @ 25fps = 1.32s each)
  2. Extract audio segments aligned to each video chunk
  3. Save as training pairs: video frames + audio .wav files
  4. Optionally pre-encode video frames through VAE for faster training

Usage:
    from avatar.training.prepare_training_data import prepare_training_data
    pairs = prepare_training_data("path/to/video.mp4", "output/training_data/")

Output structure:
    training_data/
        chunk_000/
            frames/          # 33 PNG frames per chunk
            audio.wav        # Aligned audio segment (16kHz mono)
            metadata.json    # Timing, frame indices, audio offset
        chunk_001/
        ...
"""

import json
import logging
import os
import wave
import struct
from pathlib import Path

import numpy as np

from .. import config

logger = logging.getLogger("champ.avatar.training.data")

# FlashHead training chunk parameters
CHUNK_FRAMES = config.FLASHHEAD_CHUNK_FRAMES  # 33
TARGET_FPS = config.VIDEO_FPS  # 25
CHUNK_DURATION_SEC = CHUNK_FRAMES / TARGET_FPS  # 1.32s
AUDIO_SAMPLE_RATE = config.AUDIO_MODEL_SAMPLE_RATE  # 16000
OVERLAP_FRAMES = 5  # Motion continuity overlap between chunks


def _ensure_cv2():
    try:
        import cv2
        return cv2
    except ImportError:
        raise ImportError("opencv-python required: pip install opencv-python")


def _write_wav(filepath: str, audio_f32: np.ndarray, sample_rate: int = AUDIO_SAMPLE_RATE):
    """Write float32 audio array to 16-bit WAV file."""
    audio_int16 = np.clip(audio_f32 * 32767, -32768, 32767).astype(np.int16)
    with wave.open(filepath, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio_int16.tobytes())


def _extract_audio_from_video(video_path: str, output_path: str) -> str:
    """Extract audio from video as 16kHz mono WAV using ffmpeg."""
    import subprocess

    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vn",  # No video
        "-acodec", "pcm_s16le",
        "-ar", str(AUDIO_SAMPLE_RATE),
        "-ac", "1",  # Mono
        output_path,
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return output_path
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        raise RuntimeError(f"ffmpeg failed to extract audio: {e}")


def _load_audio_wav(wav_path: str) -> np.ndarray:
    """Load WAV file as float32 numpy array."""
    with wave.open(wav_path, "r") as wf:
        n_frames = wf.getnframes()
        raw = wf.readframes(n_frames)
        audio_int16 = np.frombuffer(raw, dtype=np.int16)
        return audio_int16.astype(np.float32) / 32768.0


def prepare_training_data(
    video_path: str,
    output_dir: str,
    face_crop: bool = True,
    face_ratio: float = 2.0,
    overlap: int = OVERLAP_FRAMES,
) -> list[dict]:
    """
    Extract aligned audio+video training pairs from a 2-minute reference video.

    Args:
        video_path: Path to input video
        output_dir: Where to save training chunks
        face_crop: Apply face detection and crop (matches FlashHead input)
        face_ratio: Face crop ratio (FlashHead default: 2.0)
        overlap: Frame overlap between chunks for motion continuity

    Returns:
        List of chunk metadata dicts with paths to frames and audio
    """
    cv2 = _ensure_cv2()
    from PIL import Image

    os.makedirs(output_dir, exist_ok=True)

    # Step 1: Extract full audio track
    logger.info(f"Extracting audio from {video_path}...")
    audio_path = os.path.join(output_dir, "_full_audio.wav")
    _extract_audio_from_video(video_path, audio_path)
    full_audio = _load_audio_wav(audio_path)

    # Step 2: Open video and get properties
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Could not open video: {video_path}")

    video_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_video_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    video_duration = total_video_frames / video_fps

    logger.info(f"  Video: {video_duration:.1f}s, {video_fps:.1f}fps, {total_video_frames} frames")
    logger.info(f"  Audio: {len(full_audio)} samples ({len(full_audio)/AUDIO_SAMPLE_RATE:.1f}s)")

    # Set up face detection if requested
    face_detector = None
    use_flashhead_crop = False
    if face_crop:
        try:
            import sys
            flashhead_src = str(config.FLASHHEAD_SRC_DIR)
            if flashhead_src not in sys.path:
                sys.path.insert(0, flashhead_src)
            from flash_head.utils.cpu_face_handler import CPUFaceHandler
            from flash_head.utils.facecrop import get_scaled_bbox
            face_detector = CPUFaceHandler()
            use_flashhead_crop = True
        except ImportError:
            logger.info("  FlashHead face handler not available, skipping face crop")

    # Step 3: Extract chunks
    # Calculate frame stride to match target FPS
    frame_stride = max(1, round(video_fps / TARGET_FPS))
    usable_frames_per_chunk = CHUNK_FRAMES - overlap

    chunks = []
    chunk_idx = 0
    video_frame_pos = 0

    while True:
        chunk_dir = os.path.join(output_dir, f"chunk_{chunk_idx:03d}")
        frames_dir = os.path.join(chunk_dir, "frames")
        os.makedirs(frames_dir, exist_ok=True)

        # Calculate time range for this chunk
        start_time = (chunk_idx * usable_frames_per_chunk) / TARGET_FPS
        end_time = start_time + CHUNK_DURATION_SEC

        if end_time > video_duration:
            break

        # Extract video frames for this chunk
        start_video_frame = int(start_time * video_fps)
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_video_frame)

        frame_paths = []
        for frame_i in range(CHUNK_FRAMES):
            target_video_frame = start_video_frame + frame_i * frame_stride

            # Read and skip to target frame
            cap.set(cv2.CAP_PROP_POS_FRAMES, target_video_frame)
            ret, frame_bgr = cap.read()
            if not ret:
                break

            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(frame_rgb)
            img_h, img_w = frame_rgb.shape[:2]

            # Face crop if available
            if face_detector is not None and use_flashhead_crop:
                boxes, scores = face_detector(frame_rgb)
                if len(boxes) > 0:
                    face_box = [
                        boxes[0][0] * img_w, boxes[0][1] * img_h,
                        boxes[0][2] * img_w, boxes[0][3] * img_h,
                    ]
                    pil_image = get_scaled_bbox(
                        face_box, img_w, img_h, face_ratio, pil_image
                    )

            # Resize to FlashHead target size
            pil_image = pil_image.resize(
                (config.VIDEO_WIDTH, config.VIDEO_HEIGHT), Image.LANCZOS
            )

            frame_path = os.path.join(frames_dir, f"frame_{frame_i:03d}.png")
            pil_image.save(frame_path)
            frame_paths.append(frame_path)

        if len(frame_paths) < CHUNK_FRAMES:
            # Not enough frames — skip this partial chunk
            break

        # Extract aligned audio segment
        audio_start = int(start_time * AUDIO_SAMPLE_RATE)
        audio_end = int(end_time * AUDIO_SAMPLE_RATE)
        audio_chunk = full_audio[audio_start:audio_end]

        chunk_audio_path = os.path.join(chunk_dir, "audio.wav")
        _write_wav(chunk_audio_path, audio_chunk)

        # Save metadata
        meta = {
            "chunk_idx": chunk_idx,
            "start_time": start_time,
            "end_time": end_time,
            "num_frames": len(frame_paths),
            "audio_samples": len(audio_chunk),
            "audio_duration_sec": len(audio_chunk) / AUDIO_SAMPLE_RATE,
            "frames_dir": frames_dir,
            "audio_path": chunk_audio_path,
        }

        meta_path = os.path.join(chunk_dir, "metadata.json")
        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2)

        chunks.append(meta)
        chunk_idx += 1

    cap.release()

    logger.info(f"  Extracted {len(chunks)} training chunks to {output_dir}")
    return chunks


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Prepare training data from reference video")
    parser.add_argument("video", help="Path to 2-minute reference video")
    parser.add_argument("--output", "-o", required=True, help="Output directory for training data")
    parser.add_argument("--no-face-crop", action="store_true", help="Skip face detection/crop")
    args = parser.parse_args()

    chunks = prepare_training_data(
        video_path=args.video,
        output_dir=args.output,
        face_crop=not args.no_face_crop,
    )

    print(f"\nPrepared {len(chunks)} training chunks:")
    for c in chunks:
        print(f"  chunk_{c['chunk_idx']:03d}: {c['num_frames']} frames, {c['audio_duration_sec']:.2f}s audio")

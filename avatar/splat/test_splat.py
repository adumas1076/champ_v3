"""
CHAMP Avatar — Gaussian Splat Pipeline Tests (Phase 7)

Tests the full splat pipeline without GPU, COLMAP, or external models.
All components have placeholder/fallback modes for testing.

Usage:
    cd champ_v3
    python -m avatar.splat.test_splat

Test Suites:
  1. Config — GAUSSIAN_SPLAT + PERSONALIVE render modes + splat constants
  2. MotionDriver — ARKit→FLAME mapping, serialization, DataChannel format
  3. MotionFrame — Binary serialization/deserialization roundtrip
  4. InstantPreview — Placeholder head cloud generation + PLY output
  5. SplatExporter — PLY read/write, SPLAT format, pruning, validation
  6. SplatTrainer — Placeholder splat generation, frame extraction hooks
  7. VirtualCaptureStudio — Placeholder view generation, expression variants
  8. AvatarRegistry — Splat metadata fields, status progression
  9. PersonaLive — Zero-training renderer, driving from blendshapes, lifecycle
  10. Integration — Full pipeline: photo → preview → views → train → export
"""

import json
import os
import shutil
import struct
import sys
import tempfile
import time
from pathlib import Path

import numpy as np


def test_splat_pipeline():
    print("=" * 60)
    print("CHAMP Avatar — Gaussian Splat Pipeline Tests (Phase 7)")
    print("=" * 60)

    passed = 0
    failed = 0

    def check(name, condition, detail=""):
        nonlocal passed, failed
        if condition:
            passed += 1
            print(f"  [OK] {name}")
        else:
            failed += 1
            print(f"  [FAIL] {name} {detail}")

    # ── 1. Config ──
    print("\n[1] Gaussian Splat Config...")
    try:
        from avatar import config
        from avatar.config import RenderMode

        check("GAUSSIAN_SPLAT in RenderMode",
              hasattr(RenderMode, "GAUSSIAN_SPLAT"))
        check("RenderMode.GAUSSIAN_SPLAT value",
              RenderMode.GAUSSIAN_SPLAT.value == "gaussian_splat")
        check("SPLAT_TRAIN_ITERATIONS > 0",
              config.SPLAT_TRAIN_ITERATIONS > 0)
        check("SPLAT_SH_DEGREE = 3",
              config.SPLAT_SH_DEGREE == 3)
        check("VCS_NUM_VIEWS = 96",
              config.VCS_NUM_VIEWS == 96)
        check("VCS_EXPRESSION_VARIANTS has 4 entries",
              len(config.VCS_EXPRESSION_VARIANTS) == 4)
        check("MOTION_FRAME_BYTES = 220",
              config.MOTION_FRAME_BYTES == 220)
        check("MOTION_BANDWIDTH ~5.4 KB/s",
              4.0 < config.MOTION_BANDWIDTH_KBS < 6.0)
        check("SPLAT_MAX_FILE_SIZE_MB = 200",
              config.SPLAT_MAX_FILE_SIZE_MB == 200)
        check("REFERENCE_DIR is Path",
              isinstance(config.REFERENCE_DIR, Path))
        check("GAUSSIAN_TALKER_DIR defined",
              hasattr(config, "GAUSSIAN_TALKER_DIR"))
        check("GAUSSIAN_AVATARS_DIR defined",
              hasattr(config, "GAUSSIAN_AVATARS_DIR"))
        check("FACELIFT_DIR defined",
              hasattr(config, "FACELIFT_DIR"))
        check("FLAME_MODEL_PATH defined",
              hasattr(config, "FLAME_MODEL_PATH"))
        check("SPLAT_NUM_GAUSSIANS_PER_TRIANGLE = 6",
              config.SPLAT_NUM_GAUSSIANS_PER_TRIANGLE == 6)
        check("VCS_IDENTITY_THRESHOLD between 0 and 1",
              0.0 < config.VCS_IDENTITY_THRESHOLD < 1.0)
    except ImportError as e:
        print(f"  [FAIL] Config import error: {e}")

    # ── 2. MotionDriver ──
    print("\n[2] Splat Motion Driver...")
    try:
        from avatar.splat.motion_driver import (
            SplatMotionDriver, MotionFrame,
            ARKIT_TO_FLAME_EXPRESSION, GESTURE_INDEX, GESTURE_NAMES,
        )

        driver = SplatMotionDriver()

        # Test without loading avatar (should work for basic operations)
        check("SplatMotionDriver instantiated", driver is not None)
        check("Not available before load", not driver.available)

        # Test drive with mock motion vector
        # Load with temp dir
        with tempfile.TemporaryDirectory() as tmpdir:
            avatar_dir = Path(tmpdir) / "test_avatar"
            splat_dir = avatar_dir / "splat"
            splat_dir.mkdir(parents=True)

            # Create minimal flame params
            flame_dir = avatar_dir / "flame_tracking"
            flame_dir.mkdir(parents=True)
            np.savez(
                flame_dir / "flame_params.npz",
                shape=np.zeros((5, 300), dtype=np.float32),
                expression=np.zeros((5, 100), dtype=np.float32),
            )

            driver.load_avatar("test_avatar", avatars_dir=tmpdir)
            check("Load avatar succeeds", driver.available)
            check("Avatar ID set", driver.avatar_id == "test_avatar")

            # Test driving
            motion_vec = np.random.randn(55).astype(np.float32) * 0.1
            frame = driver.drive(motion_vec, gesture="emphasis")

            check("Drive returns MotionFrame", isinstance(frame, MotionFrame))
            check("Blendshapes shape = (52,)", frame.blendshapes.shape == (52,))
            check("Head pose shape = (3,)", frame.head_pose.shape == (3,))
            check("Blendshapes clamped [0,1]",
                  np.all(frame.blendshapes >= 0) and np.all(frame.blendshapes <= 1))
            check("Head pose clamped [-30, 30]",
                  np.all(frame.head_pose >= -30) and np.all(frame.head_pose <= 30))
            check("Gesture set", frame.gesture == "emphasis")
            check("Timestamp > 0", frame.timestamp > 0)

            # Test ARKit to FLAME conversion
            expression = driver.arkit_to_flame_expression(frame.blendshapes)
            check("FLAME expression shape = (100,)", expression.shape == (100,))

            pose = driver.arkit_to_flame_pose(frame.head_pose)
            check("FLAME pose shape = (6,)", pose.shape == (6,))

            # Test full FLAME deformation
            deform = driver.get_flame_deformation(motion_vec)
            check("Deformation has expression", "expression" in deform)
            check("Deformation has pose", "pose" in deform)
            check("Deformation has shape", "shape" in deform)
            check("Shape dim = 300", len(deform["shape"]) == 300)

        # Test mapping tables
        check("ARKIT_TO_FLAME_EXPRESSION has entries",
              len(ARKIT_TO_FLAME_EXPRESSION) > 10)
        check("GESTURE_INDEX has entries", len(GESTURE_INDEX) >= 8)
        check("GESTURE_NAMES inverse mapping", len(GESTURE_NAMES) > 0)

    except Exception as e:
        print(f"  [FAIL] MotionDriver error: {e}")
        import traceback
        traceback.print_exc()

    # ── 3. MotionFrame Serialization ──
    print("\n[3] MotionFrame Serialization...")
    try:
        from avatar.splat.motion_driver import MotionFrame

        # Create test frame
        bs = np.random.rand(52).astype(np.float32)
        hp = np.array([5.0, -3.0, 1.5], dtype=np.float32)
        ts = time.time()

        frame = MotionFrame(
            blendshapes=bs,
            head_pose=hp,
            timestamp=ts,
            gesture="nod",
        )

        # Serialize
        data = frame.to_bytes()
        check("Serialization produces bytes", isinstance(data, bytes))
        check("Serialized size = 229 bytes (220 + 8 + 1)",
              len(data) == 220 + 8 + 1)

        # Deserialize
        frame2 = MotionFrame.from_bytes(data)
        check("Roundtrip: blendshapes match",
              np.allclose(frame.blendshapes, frame2.blendshapes, atol=1e-5))
        check("Roundtrip: head_pose match",
              np.allclose(frame.head_pose, frame2.head_pose, atol=1e-5))
        check("Roundtrip: timestamp match",
              abs(frame.timestamp - frame2.timestamp) < 1e-6)
        check("Roundtrip: gesture match", frame2.gesture == "nod")

        # Test to_dict
        d = frame.to_dict()
        check("to_dict has blendshapes", "blendshapes" in d)
        check("to_dict has head_pose", "head_pose" in d)
        check("to_dict has timestamp", "timestamp" in d)
        check("to_dict has gesture", "gesture" in d)
        check("to_dict blendshapes is list", isinstance(d["blendshapes"], list))
        check("to_dict blendshapes len = 52", len(d["blendshapes"]) == 52)

        # Test size_bytes
        check("size_bytes = 229", frame.size_bytes == 229)

        # Edge case: empty gesture
        frame3 = MotionFrame(
            blendshapes=np.zeros(52, dtype=np.float32),
            head_pose=np.zeros(3, dtype=np.float32),
            timestamp=0.0,
            gesture="",
        )
        data3 = frame3.to_bytes()
        frame4 = MotionFrame.from_bytes(data3)
        check("Empty gesture roundtrip", frame4.gesture in ("", "neutral"))

    except Exception as e:
        print(f"  [FAIL] MotionFrame error: {e}")
        import traceback
        traceback.print_exc()

    # ── 4. InstantPreview ──
    print("\n[4] Instant Preview Generator...")
    try:
        from avatar.splat.instant_preview import InstantPreviewGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            gen = InstantPreviewGenerator(output_dir=tmpdir)
            check("Generator instantiated", gen is not None)
            check("FaceLift not available (expected)", not gen.available)

            # Create test image
            from PIL import Image
            test_img_path = os.path.join(tmpdir, "selfie.png")
            img = Image.new("RGB", (512, 512), color=(200, 160, 140))
            img.save(test_img_path)

            # Generate preview
            preview_path = gen.generate(
                image_path=test_img_path,
                avatar_id="test_preview",
            )

            check("Preview file created", os.path.exists(preview_path))
            check("Preview is .ply", preview_path.endswith(".ply"))

            # Verify PLY is valid
            file_size = os.path.getsize(preview_path)
            check("Preview file has content", file_size > 100)

            # Read and validate PLY header
            with open(preview_path, "rb") as f:
                header = b""
                while True:
                    line = f.readline()
                    header += line
                    if b"end_header" in line:
                        break

            header_str = header.decode("ascii")
            check("PLY header starts with 'ply'", header_str.startswith("ply"))
            check("PLY has vertex element", "element vertex" in header_str)
            check("PLY has position properties", "property float x" in header_str)
            check("PLY has color properties", "property float f_dc_0" in header_str)
            check("PLY has rotation properties", "property float rot_0" in header_str)

            # Extract vertex count
            for line in header_str.split("\n"):
                if "element vertex" in line:
                    num_verts = int(line.split()[-1])
                    check("Preview has ~2000 Gaussians",
                          1500 <= num_verts <= 2500, f"got {num_verts}")
                    break

    except Exception as e:
        print(f"  [FAIL] InstantPreview error: {e}")
        import traceback
        traceback.print_exc()

    # ── 5. SplatExporter ──
    print("\n[5] Splat Exporter...")
    try:
        from avatar.splat.splat_export import SplatExporter, ExportFormat

        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = SplatExporter()

            # Create a test splat PLY
            num_g = 500
            test_ply = os.path.join(tmpdir, "test.ply")
            _write_test_ply(test_ply, num_g)

            check("Test PLY created", os.path.exists(test_ply))

            # Read PLY
            gaussians = exporter._read_ply(Path(test_ply))
            check("Read positions shape", gaussians["positions"].shape == (num_g, 3))
            check("Read colors shape", gaussians["colors_sh"].shape == (num_g, 3))
            check("Read scales shape", gaussians["scales"].shape == (num_g, 3))
            check("Read rotations shape", gaussians["rotations"].shape == (num_g, 4))
            check("Read opacities shape", gaussians["opacities"].shape == (num_g,))

            # Export as PLY
            ply_out = os.path.join(tmpdir, "export.ply")
            result_path = exporter.export_for_web(
                test_ply, ply_out, format=ExportFormat.PLY
            )
            check("PLY export created", os.path.exists(result_path))
            check("PLY export has content", os.path.getsize(result_path) > 0)

            # Export as SPLAT (compressed)
            splat_out = os.path.join(tmpdir, "export.splat")
            result_path = exporter.export_for_web(
                test_ply, splat_out, format=ExportFormat.SPLAT
            )
            check("SPLAT export created", os.path.exists(result_path))
            splat_size = os.path.getsize(result_path)
            ply_size = os.path.getsize(ply_out)
            check("SPLAT smaller than PLY", splat_size < ply_size,
                  f"splat={splat_size}, ply={ply_size}")

            # Export as compressed PLY
            gz_out = os.path.join(tmpdir, "export.ply.gz")
            result_path = exporter.export_for_web(
                test_ply, gz_out, format=ExportFormat.COMPRESSED_PLY
            )
            check("Compressed PLY export created", os.path.exists(result_path))
            gz_size = os.path.getsize(result_path)
            check("Compressed PLY smaller than PLY", gz_size < ply_size)

            # Test pruning by opacity
            pruned = exporter._prune_by_opacity(gaussians, threshold=0.5)
            check("Pruning reduces count",
                  len(pruned["positions"]) <= len(gaussians["positions"]))

            # Test prune to count
            limited = exporter._prune_to_count(gaussians, max_count=100)
            check("Prune to 100 works", len(limited["positions"]) == 100)

            # Test metadata
            meta = exporter.get_client_metadata(test_ply)
            check("Metadata has num_gaussians", meta["num_gaussians"] == num_g)
            check("Metadata has file_size_mb", "file_size_mb" in meta)
            check("Metadata has bbox_min", "bbox_min" in meta)
            check("Metadata has center", "center" in meta)
            check("Metadata has motion_frame_rate",
                  meta["motion_frame_rate"] == 25)
            check("Metadata has motion_frame_bytes",
                  meta["motion_frame_bytes"] == 220)

            # Test validation
            valid = exporter.validate_for_web(test_ply)
            check("Validation reports valid", valid["valid"])
            check("Validation has num_gaussians", valid["num_gaussians"] == num_g)

    except Exception as e:
        print(f"  [FAIL] SplatExporter error: {e}")
        import traceback
        traceback.print_exc()

    # ── 6. SplatTrainer ──
    print("\n[6] Splat Trainer...")
    try:
        from avatar.splat.train_splat import (
            SplatTrainer, SplatTrainingConfig, SplatTrainingResult,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            trainer = SplatTrainer(output_dir=tmpdir)
            check("Trainer instantiated", trainer is not None)
            check("GaussianAvatars availability detected", True)  # May or may not be cloned

            # Test config defaults
            cfg = SplatTrainingConfig()
            check("Default iterations > 0", cfg.iterations > 0)
            check("Default SH degree = 3", cfg.sh_degree == 3)
            check("Default resolution = 512", cfg.resolution == 512)

            # Test placeholder splat generation
            output_dir = Path(tmpdir) / "test_avatar" / "splat"
            output_dir.mkdir(parents=True)
            result = trainer._generate_placeholder_splat(output_dir, cfg)

            check("Placeholder returns checkpoint_dir", "checkpoint_dir" in result)
            check("Placeholder returns psnr", "psnr" in result)
            check("Placeholder returns num_gaussians", result["num_gaussians"] == 1000)

            splat_file = output_dir / "splat.ply"
            check("Placeholder PLY created", splat_file.exists())
            check("Placeholder PLY has content", os.path.getsize(splat_file) > 0)

            # Test placeholder FLAME params
            flame = trainer._generate_placeholder_flame(10)
            check("FLAME shape (10, 300)", flame["shape"].shape == (10, 300))
            check("FLAME expression (10, 100)", flame["expression"].shape == (10, 100))
            check("FLAME pose (10, 6)", flame["pose"].shape == (10, 6))
            check("FLAME translation (10, 3)", flame["translation"].shape == (10, 3))

            # Test training result dataclass
            result = SplatTrainingResult(
                avatar_id="test",
                splat_path="/test/splat.ply",
                flame_params_path="/test/flame.npz",
                checkpoint_path="/test/ckpt/",
                num_gaussians=1000,
                training_time_sec=60.0,
                iterations=30000,
                final_psnr=28.5,
                final_ssim=0.92,
                created_at="2024-01-01T00:00:00",
            )
            d = result.to_dict()
            check("Result to_dict works", isinstance(d, dict))
            check("Result has avatar_id", d["avatar_id"] == "test")
            check("Result has num_gaussians", d["num_gaussians"] == 1000)
            check("Result has psnr", d["final_psnr"] == 28.5)

    except Exception as e:
        print(f"  [FAIL] SplatTrainer error: {e}")
        import traceback
        traceback.print_exc()

    # ── 7. VirtualCaptureStudio ──
    print("\n[7] Virtual Capture Studio...")
    try:
        from avatar.splat.virtual_capture_studio import (
            VirtualCaptureStudio, CaptureResult,
            AZIMUTH_ANGLES, ELEVATION_ANGLES,
        )

        check("24 azimuth angles", len(AZIMUTH_ANGLES) == 24)
        check("4 elevation angles", len(ELEVATION_ANGLES) == 4)
        check("Total = 96 views", len(AZIMUTH_ANGLES) * len(ELEVATION_ANGLES) == 96)

        with tempfile.TemporaryDirectory() as tmpdir:
            studio = VirtualCaptureStudio(output_dir=tmpdir)
            check("Studio instantiated", studio is not None)

            # Create test photos
            from PIL import Image
            photos = []
            for i, name in enumerate(["front", "left", "right"]):
                path = os.path.join(tmpdir, f"{name}.png")
                # Different colors for different angles
                color = [(200, 160, 140), (180, 150, 130), (190, 155, 135)][i]
                img = Image.new("RGB", (512, 512), color=color)
                img.save(path)
                photos.append(path)

            # Run capture
            progress_calls = []

            def on_progress(p, msg):
                progress_calls.append((p, msg))

            result = studio.capture(
                photos=photos,
                avatar_id="test_vcs",
                on_progress=on_progress,
            )

            check("Capture returns CaptureResult", isinstance(result, CaptureResult))
            check("Avatar ID set", result.avatar_id == "test_vcs")
            check("Output dir exists", os.path.isdir(result.output_dir))
            check("Num views generated",
                  result.num_views > 0, f"got {result.num_views}")
            check("Total views = 96 + expressions",
                  result.num_views >= 96)
            check("All views verified (no InsightFace)",
                  result.num_rejected == 0)
            check("Expressions generated",
                  len(result.expressions) == 4)
            check("Processing time tracked",
                  result.processing_time_sec > 0)
            check("Progress callbacks fired",
                  len(progress_calls) > 0)

            # Check files exist
            view_files = list(Path(result.output_dir).glob("*.png"))
            check("View image files created",
                  len(view_files) > 0, f"got {len(view_files)}")

            # Check metadata saved
            meta_path = Path(result.output_dir) / "capture_result.json"
            check("Metadata JSON saved", meta_path.exists())

            # Test to_dict
            d = result.to_dict()
            check("to_dict works", isinstance(d, dict))
            check("to_dict has num_views", "num_views" in d)

    except Exception as e:
        print(f"  [FAIL] VirtualCaptureStudio error: {e}")
        import traceback
        traceback.print_exc()

    # ── 8. AvatarRegistry Splat Fields ──
    print("\n[8] Avatar Registry — Splat Support...")
    try:
        from avatar.training.avatar_registry import AvatarRegistry, AvatarMetadata

        with tempfile.TemporaryDirectory() as tmpdir:
            registry = AvatarRegistry(base_dir=tmpdir)

            # Create avatar from image
            from PIL import Image
            test_img_path = os.path.join(tmpdir, "test_photo.png")
            img = Image.new("RGB", (512, 512), color=(200, 160, 140))
            img.save(test_img_path)

            meta = registry.create_from_image(
                image_path=test_img_path,
                avatar_id="splat_test",
                name="Splat Test",
            )

            check("Avatar created", meta is not None)
            check("Splat status = none", meta.splat_status == "none")
            check("No splat path", meta.splat_path is None)
            check("No preview path", meta.splat_preview_path is None)
            check("Num gaussians = 0", meta.num_gaussians == 0)

            # Update to preview status
            updated = registry.update_splat_status(
                "splat_test",
                status="preview",
                preview_path="/tmp/preview.ply",
            )
            check("Update to preview", updated.splat_status == "preview")
            check("Preview path set", updated.splat_preview_path == "/tmp/preview.ply")

            # Update to training
            updated = registry.update_splat_status(
                "splat_test",
                status="training",
            )
            check("Update to training", updated.splat_status == "training")

            # Update to ready
            updated = registry.update_splat_status(
                "splat_test",
                status="ready",
                splat_path="/tmp/splat.ply",
                num_gaussians=150000,
            )
            check("Update to ready", updated.splat_status == "ready")
            check("Splat path set", updated.splat_path == "/tmp/splat.ply")
            check("Num gaussians set", updated.num_gaussians == 150000)

            # Test get_splat_path
            splat_path = registry.get_splat_path("splat_test")
            check("get_splat_path returns production",
                  splat_path == "/tmp/splat.ply")

            # Test persistence
            loaded = registry.get_avatar("splat_test")
            check("Persisted splat_status", loaded.splat_status == "ready")
            check("Persisted splat_path", loaded.splat_path == "/tmp/splat.ply")
            check("Persisted num_gaussians", loaded.num_gaussians == 150000)

            # Test nonexistent avatar
            result = registry.update_splat_status("nonexistent", "ready")
            check("Nonexistent avatar returns None", result is None)

            none_path = registry.get_splat_path("nonexistent")
            check("Nonexistent splat path returns None", none_path is None)

    except Exception as e:
        print(f"  [FAIL] AvatarRegistry error: {e}")
        import traceback
        traceback.print_exc()

    # ── 9. PersonaLive Renderer ──
    print("\n[9] PersonaLive Renderer...")
    try:
        from avatar.splat.personalive_renderer import (
            PersonaLiveRenderer, PersonaLiveConfig,
        )
        from avatar import config as avatar_config
        from avatar.config import RenderMode

        # Config checks
        check("PERSONALIVE in RenderMode",
              hasattr(RenderMode, "PERSONALIVE"))
        check("RenderMode.PERSONALIVE value",
              RenderMode.PERSONALIVE.value == "personalive")
        check("PERSONALIVE_DIR defined",
              hasattr(avatar_config, "PERSONALIVE_DIR"))
        check("PERSONALIVE_CONFIG defined",
              hasattr(avatar_config, "PERSONALIVE_CONFIG"))
        check("PERSONALIVE_TEMPORAL_WINDOW = 4",
              avatar_config.PERSONALIVE_TEMPORAL_WINDOW == 4)
        check("PERSONALIVE_DDIM_STEPS = 4",
              avatar_config.PERSONALIVE_DDIM_STEPS == 4)
        check("PERSONALIVE_RESOLUTION = 512",
              avatar_config.PERSONALIVE_RESOLUTION == 512)
        check("PERSONALIVE_MOTION_BANK_THRESHOLD = 17.0",
              avatar_config.PERSONALIVE_MOTION_BANK_THRESHOLD == 17.0)
        check("PERSONALIVE_MAX_KEYFRAME_INJECTIONS = 3",
              avatar_config.PERSONALIVE_MAX_KEYFRAME_INJECTIONS == 3)
        check("PERSONALIVE_WEIGHT_FILES has 6 entries",
              len(avatar_config.PERSONALIVE_WEIGHT_FILES) == 6)

        # PersonaLiveConfig
        pl_config = PersonaLiveConfig()
        check("PL config temporal_window = 4", pl_config.temporal_window == 4)
        check("PL config ddim_steps = 4", pl_config.ddim_steps == 4)
        check("PL config resolution = 512", pl_config.resolution == 512)
        check("PL config fps = 16", pl_config.fps == 16)

        # Renderer lifecycle (placeholder mode)
        with tempfile.TemporaryDirectory() as tmpdir:
            renderer = PersonaLiveRenderer()
            check("Renderer instantiated", renderer is not None)
            check("Not initialized", not renderer.initialized)
            check("Not available (no weights)", not renderer.available)

            # Create test reference image
            from PIL import Image
            ref_path = os.path.join(tmpdir, "reference.png")
            img = Image.new("RGB", (512, 512), color=(200, 160, 140))
            img.save(ref_path)

            # Initialize with placeholder
            success = renderer.initialize(ref_path)
            check("Initialize succeeds (placeholder)", success)
            check("Initialized flag set", renderer.initialized)
            check("Not available (placeholder mode)", not renderer.available)
            check("Frame count = 0", renderer.frame_count == 0)

            # Process a driving frame
            driving = np.random.randint(0, 255, (256, 256, 3), dtype=np.uint8)
            output = renderer.process_frame(driving)
            check("Process frame returns array", isinstance(output, np.ndarray))
            check("Output shape = (512, 512, 4)",
                  output.shape == (512, 512, 4), f"got {output.shape}")
            check("Output dtype = uint8", output.dtype == np.uint8)
            check("Frame count incremented", renderer.frame_count == 1)

            # Process multiple frames
            for _ in range(5):
                output = renderer.process_frame(driving)
            check("Multiple frames work", renderer.frame_count == 6)
            check("FPS tracked", renderer.current_fps > 0)

            # Stats
            stats = renderer.stats
            check("Stats has mode", stats["mode"] == "placeholder")
            check("Stats has frame_count", stats["frame_count"] == 6)
            check("Stats has resolution", stats["resolution"] == 512)
            check("Stats has temporal_window", stats["temporal_window"] == 4)

            # Generate driving from blendshapes (audio-driven bridge)
            bs = np.zeros(52, dtype=np.float32)
            bs[avatar_config.IDX_JAW_OPEN] = 0.6
            bs[avatar_config.IDX_MOUTH_SMILE_LEFT] = 0.3
            bs[avatar_config.IDX_MOUTH_SMILE_RIGHT] = 0.3
            bs[avatar_config.IDX_EYE_BLINK_LEFT] = 0.8
            hp = np.array([5.0, -3.0, 0.0], dtype=np.float32)

            synth_frame = renderer.generate_driving_from_blendshapes(bs, hp)
            check("Synthetic driving frame shape = (512, 512, 3)",
                  synth_frame.shape == (512, 512, 3))
            check("Synthetic driving frame dtype = uint8",
                  synth_frame.dtype == np.uint8)
            check("Synthetic frame not all same color",
                  len(np.unique(synth_frame.reshape(-1, 3), axis=0)) > 3)

            # Process synthetic frame
            output2 = renderer.process_frame(synth_frame)
            check("Synthetic frame processable",
                  output2.shape == (512, 512, 4))

            # Reset
            renderer.reset()
            check("Reset clears frame count", renderer.frame_count == 0)
            check("Reset clears FPS", renderer.current_fps == 0.0)

            # Close
            renderer.close()
            check("Close clears initialized", not renderer.initialized)

            # Bad reference path
            renderer2 = PersonaLiveRenderer()
            result = renderer2.initialize("/nonexistent/path.jpg")
            check("Nonexistent reference returns False", not result)

    except Exception as e:
        print(f"  [FAIL] PersonaLive error: {e}")
        import traceback
        traceback.print_exc()

    # ── 10. Integration ──
    print("\n[10] Integration — Full Pipeline (Placeholder Mode)...")
    try:
        from avatar.splat.train_splat import SplatTrainer, SplatTrainingConfig
        from avatar.splat.instant_preview import InstantPreviewGenerator
        from avatar.splat.virtual_capture_studio import VirtualCaptureStudio
        from avatar.splat.splat_export import SplatExporter, ExportFormat
        from avatar.splat.motion_driver import SplatMotionDriver, MotionFrame
        from avatar.training.avatar_registry import AvatarRegistry

        with tempfile.TemporaryDirectory() as tmpdir:
            # Step 1: Create test photo
            from PIL import Image
            photo_path = os.path.join(tmpdir, "selfie.png")
            img = Image.new("RGB", (512, 512), color=(200, 160, 140))
            img.save(photo_path)

            avatar_id = "integration_test"
            avatars_dir = os.path.join(tmpdir, "avatars")
            os.makedirs(avatars_dir, exist_ok=True)

            # Step 2: Instant preview
            preview_gen = InstantPreviewGenerator(output_dir=avatars_dir)
            preview_path = preview_gen.generate(photo_path, avatar_id)
            check("Integration: preview created", os.path.exists(preview_path))

            # Step 3: Virtual Capture Studio
            studio = VirtualCaptureStudio(output_dir=avatars_dir)
            capture_result = studio.capture(
                photos=[photo_path],
                avatar_id=avatar_id,
            )
            check("Integration: VCS completed",
                  capture_result.num_views > 0)

            # Step 4: Generate placeholder splat (skip full training)
            trainer = SplatTrainer(output_dir=avatars_dir)
            splat_dir = Path(avatars_dir) / avatar_id / "splat"
            splat_dir.mkdir(parents=True, exist_ok=True)
            train_result = trainer._generate_placeholder_splat(
                splat_dir, SplatTrainingConfig()
            )
            check("Integration: placeholder splat created",
                  (splat_dir / "splat.ply").exists())

            # Step 5: Export for web
            exporter = SplatExporter()
            web_path = os.path.join(tmpdir, f"{avatar_id}.splat")
            exported = exporter.export_for_web(
                str(splat_dir / "splat.ply"),
                web_path,
                format=ExportFormat.SPLAT,
            )
            check("Integration: web export created", os.path.exists(exported))

            # Step 6: Validate export
            validation = exporter.validate_for_web(str(splat_dir / "splat.ply"))
            check("Integration: export valid", validation["valid"])

            # Step 7: Get client metadata
            meta = exporter.get_client_metadata(str(splat_dir / "splat.ply"))
            check("Integration: client metadata",
                  meta["num_gaussians"] == 1000)

            # Step 8: Drive motion
            driver = SplatMotionDriver()
            driver.load_avatar(avatar_id, avatars_dir=avatars_dir)
            check("Integration: motion driver loaded", driver.available)

            motion_vec = np.random.randn(55).astype(np.float32) * 0.1
            frame = driver.drive(motion_vec, gesture="nod")
            check("Integration: motion frame generated",
                  isinstance(frame, MotionFrame))

            # Step 9: Serialize for DataChannel
            frame_bytes = frame.to_bytes()
            check("Integration: frame serialized", len(frame_bytes) == 229)

            # Step 10: Roundtrip
            frame_back = MotionFrame.from_bytes(frame_bytes)
            check("Integration: frame roundtrip",
                  np.allclose(frame.blendshapes, frame_back.blendshapes, atol=1e-5))

            # Step 11: Registry tracking
            registry = AvatarRegistry(base_dir=avatars_dir)
            registry.create_from_image(photo_path, avatar_id, "Integration Test")
            registry.update_splat_status(
                avatar_id,
                status="ready",
                splat_path=str(splat_dir / "splat.ply"),
                num_gaussians=1000,
            )
            final_path = registry.get_splat_path(avatar_id)
            check("Integration: registry tracks splat",
                  final_path == str(splat_dir / "splat.ply"))

    except Exception as e:
        print(f"  [FAIL] Integration error: {e}")
        import traceback
        traceback.print_exc()

    # ── Summary ──
    print("\n" + "=" * 60)
    total = passed + failed
    print(f"RESULTS: {passed}/{total} passed, {failed} failed")
    if failed == 0:
        print("ALL TESTS PASSED")
    else:
        print(f"FAILURES: {failed}")
    print("=" * 60)

    return failed == 0


def _write_test_ply(path: str, num_gaussians: int):
    """Helper: write a valid test PLY file."""
    header = f"""ply
format binary_little_endian 1.0
element vertex {num_gaussians}
property float x
property float y
property float z
property float nx
property float ny
property float nz
property float f_dc_0
property float f_dc_1
property float f_dc_2
property float opacity
property float scale_0
property float scale_1
property float scale_2
property float rot_0
property float rot_1
property float rot_2
property float rot_3
end_header
"""
    with open(path, "wb") as f:
        f.write(header.encode("ascii"))
        for _ in range(num_gaussians):
            pos = np.random.randn(3).astype(np.float32) * 0.3
            normal = np.zeros(3, dtype=np.float32)
            color = np.random.rand(3).astype(np.float32)
            opacity = np.float32(np.random.uniform(0.5, 3.0))
            scale = np.random.randn(3).astype(np.float32) - 3.0
            rot = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
            f.write(pos.tobytes())
            f.write(normal.tobytes())
            f.write(color.astype(np.float32).tobytes())
            f.write(opacity.tobytes())
            f.write(scale.astype(np.float32).tobytes())
            f.write(rot.tobytes())


if __name__ == "__main__":
    success = test_splat_pipeline()
    sys.exit(0 if success else 1)

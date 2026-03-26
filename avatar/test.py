"""
CHAMP Avatar — Standalone Pipeline Test
Tests the split renderer without LiveKit, GPU, or ML models.
Verifies: state machine, audio processing, motion prediction,
          idle animation, smoothing, frame generation.

Usage:
    cd champ_v3
    python -m avatar.test
"""

import time
import numpy as np
import sys


def test_pipeline():
    print("=" * 60)
    print("CHAMP Avatar — Split Pipeline Test (no GPU required)")
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

    # ── 1. Imports ──
    print("\n[1] Module imports...")
    try:
        from avatar import config
        from avatar.states import AvatarState, AvatarStateMachine, StateTransition
        from avatar.audio import PlaceholderAudioExtractor
        from avatar.motion import MotionPredictor
        from avatar.idle import IdleAnimator
        from avatar.smoothing import MotionSmoother, TransitionBlender, AnticipatoryMotion
        check("All imports", True)
    except ImportError as e:
        print(f"  [FAIL] Import error: {e}")
        print("  Run from champ_v3/ directory: python -m avatar.test")
        return False

    # ── 2. Config ──
    print("\n[2] Configuration...")
    check("MOTION_DIM = 55", config.MOTION_DIM == 55)
    check("NUM_BLENDSHAPES = 52", config.NUM_BLENDSHAPES == 52)
    check("HEAD_POSE_DIM = 3", config.HEAD_POSE_DIM == 3)
    check("VIDEO_FPS = 25 (FlashHead native)", config.VIDEO_FPS == 25.0)

    # ── 3. State machine ──
    print("\n[3] State machine...")
    sm = AvatarStateMachine()
    check("Initial state = IDLE", sm.state == AvatarState.IDLE)
    check("Not transitioning initially", not sm.is_transitioning)

    sm.to_listening(duration=0.1)
    check("Transition to LISTENING", sm.state == AvatarState.LISTENING)
    check("Is transitioning", sm.is_transitioning)
    check("Blend factor < 1.0", sm.blend_factor < 1.0)

    sm.to_speaking(duration=0.0)
    check("Transition to SPEAKING (instant)", sm.state == AvatarState.SPEAKING)
    check("Instant transition complete", sm.blend_factor == 1.0)

    sm.to_idle(duration=0.0)  # Instant transition
    check("Transition to IDLE", sm.state == AvatarState.IDLE)

    # No-op test — already in IDLE with no active transition
    import time as _time
    _time.sleep(0.01)  # Let transition settle
    result = sm.to_idle()
    check("No-op transition returns False", result == False)

    # ── 4. Idle animation ──
    print("\n[4] Idle animation...")
    idle = IdleAnimator(seed=42)

    motion_idle = idle.generate("idle", t=0.0)
    check("Idle motion shape", motion_idle.shape == (config.MOTION_DIM,))
    check("Idle motion has values", not np.allclose(motion_idle, 0))

    motion_listen = idle.generate("listening", t=0.0)
    check("Listening motion shape", motion_listen.shape == (config.MOTION_DIM,))

    # Listening should have more activity than idle
    idle_energy = np.abs(motion_idle).sum()
    listen_energy = np.abs(motion_listen).sum()
    check("Listening more active than idle", listen_energy >= idle_energy,
          f"idle={idle_energy:.4f}, listen={listen_energy:.4f}")

    # Blink test — advance time past blink interval
    blink_found = False
    for t_val in np.arange(0, 10, 0.04):  # 250 frames over 10 seconds
        m = idle.generate("idle", t=t_val)
        if m[config.IDX_EYE_BLINK_LEFT] > 0.1:
            blink_found = True
            break
    check("Blink occurs within 10s", blink_found)

    # ── 5. Audio extractor (placeholder) ──
    print("\n[5] Audio extractor (placeholder)...")
    audio = PlaceholderAudioExtractor()
    check("No audio initially", not audio.has_audio)

    # Simulate 24kHz int16 audio (1 second)
    fake_audio = np.random.randint(-16000, 16000, 24000, dtype=np.int16).tobytes()
    audio.push_audio(fake_audio)
    check("Has audio after push", audio.has_audio)

    features = audio.extract()
    check("Features not None", features is not None)
    check("Features shape = (768,)", features.shape == (768,))

    audio.clear()
    check("Clear resets state", not audio.has_audio)

    # ── 6. Motion predictor (placeholder) ──
    print("\n[6] Motion predictor (placeholder)...")
    predictor = MotionPredictor()
    fake_features = np.random.randn(768).astype(np.float32)

    motion = predictor.predict(fake_features)
    check("Motion shape = (55,)", motion.shape == (config.MOTION_DIM,))

    # Predict multiple frames to test context accumulation
    for _ in range(5):
        predictor.predict(fake_features)
    check("Context accumulates", len(predictor._context) > 0)

    predictor.clear_context()
    check("Clear context works", len(predictor._context) == 0)

    # ── 7. Motion smoothing ──
    print("\n[7] Motion smoothing...")
    smoother = MotionSmoother()

    m1 = np.ones(config.MOTION_DIM, dtype=np.float32)
    m2 = np.zeros(config.MOTION_DIM, dtype=np.float32)

    s1 = smoother.smooth(m1, AvatarState.SPEAKING)
    check("First frame passes through", np.allclose(s1, m1))

    s2 = smoother.smooth(m2, AvatarState.SPEAKING)
    # With alpha=0.7: smoothed = 0.7*0 + 0.3*1 = 0.3
    expected = 0.7 * 0 + 0.3 * 1
    check("EMA smoothing correct", np.allclose(s2[0], expected, atol=0.01),
          f"got {s2[0]:.3f}, expected {expected:.3f}")

    # Idle alpha should be smoother (less responsive)
    smoother.reset()
    smoother.smooth(m1, AvatarState.IDLE)
    s3 = smoother.smooth(m2, AvatarState.IDLE)
    # With alpha=0.2: smoothed = 0.2*0 + 0.8*1 = 0.8
    expected_idle = 0.2 * 0 + 0.8 * 1
    check("Idle smoothing more conservative", s3[0] > s2[0],
          f"idle={s3[0]:.3f} should be > speaking={s2[0]:.3f}")

    # ── 8. Transition blending ──
    print("\n[8] Transition blending...")
    blender = TransitionBlender()
    sm2 = AvatarStateMachine()

    # No transition — pass through
    m_test = np.ones(config.MOTION_DIM, dtype=np.float32) * 0.5
    blended = blender.blend(m_test, sm2)
    check("No transition = passthrough", np.allclose(blended, m_test))

    # Start speaking, then transition to idle
    sm2.to_speaking(duration=0.0)
    speaking_motion = np.ones(config.MOTION_DIM, dtype=np.float32)
    blender.blend(speaking_motion, sm2)  # Register speaking motion

    sm2.to_idle(duration=1.0)  # 1 second transition for testing
    idle_motion = np.zeros(config.MOTION_DIM, dtype=np.float32)
    blended = blender.blend(idle_motion, sm2)
    check("Blend during transition", not np.allclose(blended, idle_motion),
          "should be between speaking and idle")

    # ── 9. Anticipatory motion ──
    print("\n[9] Anticipatory motion...")
    anticipation = AnticipatoryMotion()
    sm3 = AvatarStateMachine()
    sm3.to_speaking(duration=5.0)  # Long duration so we catch early phase
    _time.sleep(0.3)  # Let transition progress past 0

    m_before = np.zeros(config.MOTION_DIM, dtype=np.float32)
    m_after = anticipation.apply(m_before, sm3)
    check("Jaw opens during speak transition",
          m_after[config.IDX_JAW_OPEN] > 0,
          f"jaw_open={m_after[config.IDX_JAW_OPEN]:.4f}")

    # ── 10. Full pipeline (placeholder) ──
    print("\n[10] Full pipeline integration (placeholder)...")
    sm_full = AvatarStateMachine()
    idle_anim = IdleAnimator(seed=1)
    smoother_full = MotionSmoother()
    blender_full = TransitionBlender()
    antic_full = AnticipatoryMotion()
    pred_full = MotionPredictor()
    audio_full = PlaceholderAudioExtractor()

    # Simulate 30 frames across state transitions
    frames = []

    # 10 frames IDLE
    for i in range(10):
        raw = idle_anim.generate("idle", t=i * 0.033)
        smoothed = smoother_full.smooth(raw, AvatarState.IDLE)
        blended = blender_full.blend(smoothed, sm_full)
        frames.append(blended.copy())

    # Transition to SPEAKING
    sm_full.to_speaking(duration=0.05)
    audio_full.push_audio(fake_audio)

    # 10 frames SPEAKING
    for i in range(10):
        features = audio_full.extract()
        raw = pred_full.predict(features)
        smoothed = smoother_full.smooth(raw, AvatarState.SPEAKING)
        blended = blender_full.blend(smoothed, sm_full)
        final = antic_full.apply(blended, sm_full)
        frames.append(final.copy())

    # Transition to IDLE
    sm_full.to_idle(duration=0.3)

    # 10 frames settling back to IDLE
    for i in range(10):
        raw = idle_anim.generate("idle", t=(20 + i) * 0.033)
        smoothed = smoother_full.smooth(raw, AvatarState.IDLE)
        blended = blender_full.blend(smoothed, sm_full)
        frames.append(blended.copy())

    check("Generated 30 frames", len(frames) == 30)
    check("All frames correct shape",
          all(f.shape == (config.MOTION_DIM,) for f in frames))
    check("Frames are not all identical",
          not all(np.allclose(f, frames[0]) for f in frames))

    # Check temporal coherence — consecutive frames shouldn't jump too much
    max_jump = 0
    for i in range(1, len(frames)):
        jump = np.abs(frames[i] - frames[i - 1]).max()
        max_jump = max(max_jump, jump)
    check("Temporal coherence (max frame jump)",
          max_jump < 1.0, f"max_jump={max_jump:.4f}")

    # ── Summary ──
    total = passed + failed
    print(f"\n{'=' * 60}")
    print(f"Results: {passed}/{total} passed, {failed} failed")
    print("=" * 60)

    if failed == 0:
        print("\nAll tests passed! Pipeline works in placeholder mode.")
        print("\nNext steps:")
        print("  1. Run Avatar Lab:  python avatar/agent_avatar.py dev")
        print("  2. Open browser:    http://localhost:3000/avatar-lab")
        print("  3. For GPU mode:    python -m avatar.setup")
    else:
        print(f"\n{failed} test(s) failed — check errors above.")

    return failed == 0


def test_chunk_pipeline():
    """Test the FlashHead chunk-based pipeline components (no GPU required)."""
    print("\n" + "=" * 60)
    print("CHAMP Avatar — Chunk Pipeline Test (no GPU required)")
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

    # ── 1. New imports ──
    print("\n[1] Chunk pipeline imports...")
    try:
        from avatar import config
        from avatar.config import RenderMode
        from avatar.audio import ChunkAudioAccumulator
        from avatar.renderer import FlashHeadChunkGenerator, AudioSegmentEnd
        check("All chunk imports", True)
    except ImportError as e:
        print(f"  [FAIL] Import error: {e}")
        return False

    # ── 2. RenderMode enum ──
    print("\n[2] RenderMode configuration...")
    check("RenderMode.FLASHHEAD_FULL exists",
          RenderMode.FLASHHEAD_FULL.value == "flashhead_full")
    check("RenderMode.SPLIT_PIPELINE exists",
          RenderMode.SPLIT_PIPELINE.value == "split_pipeline")
    check("RenderMode.PLACEHOLDER exists",
          RenderMode.PLACEHOLDER.value == "placeholder")
    check("RENDER_MODE is a RenderMode",
          isinstance(config.RENDER_MODE, RenderMode))

    # ── 3. FlashHead config values ──
    print("\n[3] FlashHead config values...")
    check("VIDEO_FPS = 25", config.VIDEO_FPS == 25.0)
    check("FLASHHEAD_CHUNK_FRAMES = 33", config.FLASHHEAD_CHUNK_FRAMES == 33)
    check("FLASHHEAD_CACHED_AUDIO_DURATION = 8", config.FLASHHEAD_CACHED_AUDIO_DURATION == 8)
    check("FLASHHEAD_MODEL_TYPE is lite or pro",
          config.FLASHHEAD_MODEL_TYPE in ("lite", "pro"))
    check("FLASHHEAD_USABLE_FRAMES = 28", config.FLASHHEAD_USABLE_FRAMES == 28)
    check("FLASHHEAD_CHUNK_AUDIO_SAMPLES > 0",
          config.FLASHHEAD_CHUNK_AUDIO_SAMPLES > 0,
          f"got {config.FLASHHEAD_CHUNK_AUDIO_SAMPLES}")
    check("FLASHHEAD_CHUNK_DURATION_SEC ~ 1.12",
          abs(config.FLASHHEAD_CHUNK_DURATION_SEC - 1.12) < 0.1,
          f"got {config.FLASHHEAD_CHUNK_DURATION_SEC:.3f}")

    # ── 4. ChunkAudioAccumulator ──
    print("\n[4] ChunkAudioAccumulator...")
    acc = ChunkAudioAccumulator()

    check("Initial state: no audio", not acc.has_audio)
    check("Initial state: no chunk ready", not acc.has_chunk_ready())
    check("Initial state: buffer 0s", acc.buffer_duration_sec == 0.0)

    # Push some audio (simulate 24kHz int16 PCM)
    # 0.5 seconds at 24kHz = 12000 samples = 24000 bytes
    fake_audio = np.zeros(12000, dtype=np.int16).tobytes()
    acc.push_audio(fake_audio)

    check("After push: has audio", acc.has_audio)
    check("After 0.5s push: buffer > 0", acc.buffer_duration_sec > 0.0)
    check("After 0.5s push: no chunk yet", not acc.has_chunk_ready())

    # Push enough audio for one full chunk (~1.12s total at 24kHz)
    # Need ~17920 samples at 16kHz = ~26880 samples at 24kHz = ~53760 bytes
    big_audio = np.zeros(30000, dtype=np.int16).tobytes()
    acc.push_audio(big_audio)

    check("After ~1.7s total push: chunk ready", acc.has_chunk_ready())

    # Consume the chunk
    audio_array = acc.consume_chunk()
    check("consume_chunk returns float32 array",
          isinstance(audio_array, np.ndarray) and audio_array.dtype == np.float32)
    check("consume_chunk returns non-empty", len(audio_array) > 0)
    check("After consume: no chunk ready", not acc.has_chunk_ready())
    check("After consume: still has audio", acc.has_audio)

    # Clear
    acc.clear()
    check("After clear: no audio", not acc.has_audio)
    check("After clear: buffer 0s", acc.buffer_duration_sec == 0.0)

    # ── 5. FlashHeadChunkGenerator (init only — no GPU) ──
    print("\n[5] FlashHeadChunkGenerator structure...")
    gen = FlashHeadChunkGenerator()
    check("Generator created", gen is not None)
    check("Not available before load", not gen.available)
    gen.reset()
    check("Reset succeeds without pipeline", True)

    # ── Summary ──
    total = passed + failed
    print(f"\n{'=' * 60}")
    print(f"Chunk Pipeline Results: {passed}/{total} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


def test_training_pipeline():
    """Test the avatar training / registry components (no GPU required)."""
    print("\n" + "=" * 60)
    print("CHAMP Avatar — Training Pipeline Test (no GPU required)")
    print("=" * 60)

    import tempfile
    import os
    import json

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

    # ── 1. Training imports ──
    print("\n[1] Training module imports...")
    try:
        from avatar.training import extract_keyframes as ek_module
        from avatar.training.avatar_registry import AvatarRegistry, AvatarMetadata
        check("Training imports", True)
    except ImportError as e:
        print(f"  [FAIL] Import error: {e}")
        return False

    # ── 2. Keyframe utilities ──
    print("\n[2] Keyframe extraction utilities...")
    check("POSE_CLUSTERS defined", len(ek_module.POSE_CLUSTERS) == 9)
    check("MIN_TOTAL_FRAMES = 8", ek_module.MIN_TOTAL_FRAMES == 8)
    check("MAX_TOTAL_FRAMES = 20", ek_module.MAX_TOTAL_FRAMES == 20)

    # Test pose assignment
    cluster = ek_module._assign_cluster(0.0, 0.0)
    check("Center pose ->front cluster", cluster == "front")
    cluster = ek_module._assign_cluster(-30.0, 0.0)
    check("Left pose ->left cluster", cluster == "left")
    cluster = ek_module._assign_cluster(30.0, 0.0)
    check("Right pose ->right cluster", cluster == "right")

    # Test head pose estimation
    yaw, pitch = ek_module._estimate_head_pose_simple([200, 200, 300, 300], 500, 500)
    check("Center face ->near-zero yaw", abs(yaw) < 10)
    check("Center face ->near-zero pitch", abs(pitch) < 10)

    yaw, pitch = ek_module._estimate_head_pose_simple([50, 200, 150, 300], 500, 500)
    check("Left face ->negative yaw", yaw < -5)

    # ── 3. Avatar Registry (in temp dir) ──
    print("\n[3] Avatar Registry...")
    with tempfile.TemporaryDirectory() as tmpdir:
        registry = AvatarRegistry(base_dir=tmpdir)

        # Initially empty
        avatars = registry.list_avatars()
        check("Registry starts empty", len(avatars) == 0)

        # Create from image
        # Make a tiny test image
        test_img_path = os.path.join(tmpdir, "test_face.png")
        try:
            from PIL import Image
            img = Image.new("RGB", (256, 256), color=(128, 128, 128))
            img.save(test_img_path)
            has_pil = True
        except ImportError:
            has_pil = False

        if has_pil:
            meta = registry.create_from_image(
                image_path=test_img_path,
                avatar_id="test_avatar",
                name="Test Avatar",
            )
            check("Created avatar from image", meta is not None)
            check("Avatar ID correct", meta.avatar_id == "test_avatar")
            check("Source type = image", meta.source_type == "image")
            check("Frame count = 1", meta.frame_count == 1)
            check("Name correct", meta.name == "Test Avatar")

            # List should have 1 avatar
            avatars = registry.list_avatars()
            check("Registry has 1 avatar", len(avatars) == 1)

            # Get avatar
            loaded = registry.get_avatar("test_avatar")
            check("Get avatar returns metadata", loaded is not None)
            check("Loaded ID matches", loaded.avatar_id == "test_avatar")

            # Get reference path
            ref_path = registry.get_reference_path("test_avatar")
            check("Reference path exists", os.path.exists(ref_path))
            check("Reference is a file", os.path.isfile(ref_path))

            # Metadata file exists on disk
            meta_path = os.path.join(tmpdir, "test_avatar", "metadata.json")
            check("Metadata JSON saved", os.path.exists(meta_path))
            with open(meta_path) as f:
                data = json.load(f)
            check("Metadata has avatar_id", data["avatar_id"] == "test_avatar")

            # Delete avatar
            deleted = registry.delete_avatar("test_avatar")
            check("Delete returns True", deleted)
            check("Avatar dir removed", not os.path.exists(os.path.join(tmpdir, "test_avatar")))
            check("Registry empty after delete", len(registry.list_avatars()) == 0)

            # Get nonexistent
            check("Get nonexistent returns None", registry.get_avatar("nope") is None)
        else:
            print("  [SKIP] PIL not available, skipping image registry tests")

    # ── Summary ──
    total = passed + failed
    print(f"\n{'=' * 60}")
    print(f"Training Pipeline Results: {passed}/{total} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


def test_upscale_pipeline():
    """Test the upscaling components (bilinear fallback, no GPU required)."""
    print("\n" + "=" * 60)
    print("CHAMP Avatar -- Upscale Pipeline Test (no GPU required)")
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

    # ── 1. Imports ──
    print("\n[1] Upscale imports...")
    try:
        from avatar.upscale import FrameUpscaler
        from avatar import config
        check("FrameUpscaler import", True)
    except ImportError as e:
        print(f"  [FAIL] Import error: {e}")
        return False

    # ── 2. Config values ──
    print("\n[2] Upscale config...")
    check("VIDEO_UPSCALE_FACTOR exists", hasattr(config, 'VIDEO_UPSCALE_FACTOR'))
    check("VIDEO_UPSCALE_FACTOR is 2 or 4", config.VIDEO_UPSCALE_FACTOR in (2, 4))

    # ── 3. FrameUpscaler creation ──
    print("\n[3] FrameUpscaler (bilinear fallback)...")
    upscaler = FrameUpscaler(scale=2)
    check("Created with scale=2", upscaler.scale == 2)
    check("Not available before load", not upscaler.available)

    # Don't call load() — Real-ESRGAN likely not installed
    # Test bilinear fallback directly
    check("Output size correct", upscaler.output_size == (1024, 1024))

    upscaler4 = FrameUpscaler(scale=4)
    check("Created with scale=4", upscaler4.scale == 4)
    check("Output size 4x correct", upscaler4.output_size == (2048, 2048))

    # ── 4. Bilinear upscale (always works) ──
    print("\n[4] Bilinear upscale (fallback)...")

    # Create a test RGBA frame
    test_frame = np.random.randint(0, 255, (512, 512, 4), dtype=np.uint8)

    # 2x upscale
    result_2x = upscaler.upscale(test_frame)
    check("2x output shape", result_2x.shape == (1024, 1024, 4),
          f"got {result_2x.shape}")
    check("2x output dtype uint8", result_2x.dtype == np.uint8)

    # 4x upscale
    result_4x = upscaler4.upscale(test_frame)
    check("4x output shape", result_4x.shape == (2048, 2048, 4),
          f"got {result_4x.shape}")
    check("4x output dtype uint8", result_4x.dtype == np.uint8)

    # RGB frame (no alpha)
    test_rgb = np.random.randint(0, 255, (512, 512, 3), dtype=np.uint8)
    result_rgb = upscaler.upscale(test_rgb)
    check("RGB upscale shape", result_rgb.shape == (1024, 1024, 3),
          f"got {result_rgb.shape}")

    # Batch upscale
    batch = [test_frame, test_frame, test_frame]
    results = upscaler.upscale_batch(batch)
    check("Batch returns 3 frames", len(results) == 3)
    check("Batch frames correct shape",
          all(r.shape == (1024, 1024, 4) for r in results))

    # ── Summary ──
    total = passed + failed
    print(f"\n{'=' * 60}")
    print(f"Upscale Pipeline Results: {passed}/{total} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success1 = test_pipeline()
    success2 = test_chunk_pipeline()
    success3 = test_training_pipeline()
    success4 = test_upscale_pipeline()
    sys.exit(0 if (success1 and success2 and success3 and success4) else 1)

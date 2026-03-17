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
    check("VIDEO_FPS = 30", config.VIDEO_FPS == 30.0)

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


if __name__ == "__main__":
    success = test_pipeline()
    sys.exit(0 if success else 1)

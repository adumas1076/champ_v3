"""
CHAMP Avatar — Voice Engine Tests

Tests the dual-engine voice system without GPU or TTS models.
All components have placeholder/fallback modes for testing.

Usage:
    cd champ_v3
    python -m avatar.voice.test_voice

Test Suites:
  1. VoiceRegistry — CRUD, profiles, modes, persistence
  2. VoiceCloner — Audio extraction, clip splitting, centroid, enrollment
  3. VoiceDesigner — Design from description, templates, placeholder
  4. VoiceEngine — Routing logic, synthesis, placeholder output
  5. Integration — Full pipeline: video → clone → synthesize → WAV
"""

import json
import os
import shutil
import sys
import tempfile
import wave

import numpy as np


def test_voice_pipeline():
    print("=" * 60)
    print("CHAMP Avatar — Voice Engine Tests")
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

    # ── 1. VoiceRegistry ──
    print("\n[1] Voice Registry...")
    try:
        from avatar.voice.voice_registry import VoiceRegistry, VoiceProfile

        with tempfile.TemporaryDirectory() as tmpdir:
            registry = VoiceRegistry(base_dir=tmpdir)
            check("Registry instantiated", registry is not None)

            # Create from audio
            audio_path = os.path.join(tmpdir, "test_audio.wav")
            _create_test_wav(audio_path)

            profile = registry.create_from_audio(
                audio_path=audio_path,
                operator_id="test_op",
                language="en",
                engine="auto",
            )

            check("Profile created", profile is not None)
            check("Profile operator_id", profile.operator_id == "test_op")
            check("Profile mode = clone", profile.mode == "clone")
            check("Profile language = en", profile.language == "en")
            check("Profile engine = auto", profile.engine == "auto")
            check("Reference audio path set", profile.reference_audio is not None)
            check("Reference audio exists", os.path.exists(profile.reference_audio))

            # Load profile
            loaded = registry.get_profile("test_op")
            check("Load profile works", loaded is not None)
            check("Loaded operator_id matches", loaded.operator_id == "test_op")
            check("Loaded mode matches", loaded.mode == "clone")

            # Create designed voice
            designed = registry.create_designed(
                operator_id="designed_op",
                design_prompt="warm female, 30s, professional",
                language="en",
            )
            check("Designed profile created", designed is not None)
            check("Designed mode = design", designed.mode == "design")
            check("Design prompt stored", designed.design_prompt == "warm female, 30s, professional")
            check("Designed engine = qwen3", designed.engine == "qwen3")

            # Set emotion mode
            emotion = registry.set_emotion_mode("test_op", enabled=True)
            check("Emotion mode enabled", emotion.engine == "orpheus")
            check("Emotion mode = emotion", emotion.mode == "emotion")

            emotion_off = registry.set_emotion_mode("test_op", enabled=False)
            check("Emotion mode disabled", emotion_off.engine == "qwen3")
            check("Mode reverted to clone", emotion_off.mode == "clone")

            # List profiles
            profiles = registry.list_profiles()
            check("List profiles", len(profiles) >= 2)

            # Get reference audio
            ref = registry.get_reference_audio("test_op")
            check("Get reference audio", ref is not None)

            ref_none = registry.get_reference_audio("nonexistent")
            check("Nonexistent returns None", ref_none is None)

            # Delete
            deleted = registry.delete_profile("test_op")
            check("Delete returns True", deleted)
            check("Profile gone", registry.get_profile("test_op") is None)

            # Delete nonexistent
            check("Delete nonexistent returns False",
                  not registry.delete_profile("nonexistent"))

            # VoiceProfile serialization
            p = VoiceProfile(
                operator_id="test",
                mode="clone",
                engine="qwen3",
                language="en",
                reference_audio="/tmp/ref.wav",
                centroid_path="/tmp/centroid.npy",
                design_prompt=None,
                sample_count=10,
                created_at="2024-01-01",
                speaker_similarity=0.95,
            )
            d = p.to_dict()
            check("to_dict works", isinstance(d, dict))
            check("to_dict has operator_id", d["operator_id"] == "test")

            p2 = VoiceProfile.from_dict(d)
            check("from_dict roundtrip", p2.operator_id == "test")
            check("from_dict similarity", p2.speaker_similarity == 0.95)

    except Exception as e:
        print(f"  [FAIL] VoiceRegistry error: {e}")
        import traceback
        traceback.print_exc()

    # ── 2. VoiceCloner ──
    print("\n[2] Voice Cloner...")
    try:
        from avatar.voice.voice_cloner import VoiceCloner

        with tempfile.TemporaryDirectory() as tmpdir:
            cloner = VoiceCloner()
            check("Cloner instantiated", cloner is not None)

            # Create test audio (longer, for splitting)
            audio_path = os.path.join(tmpdir, "long_audio.wav")
            _create_test_wav(audio_path, duration_sec=15)

            # Enroll from audio
            output_dir = os.path.join(tmpdir, "enrollment")
            result = cloner.enroll_from_audio(audio_path, output_dir)

            check("Enrollment returns dict", isinstance(result, dict))
            check("Has reference_path", "reference_path" in result)
            check("Has centroid_path", "centroid_path" in result)
            check("Has sample_count", "sample_count" in result)
            check("Has speaker_similarity", "speaker_similarity" in result)
            check("Reference file exists",
                  os.path.exists(result["reference_path"]))
            check("Centroid file exists",
                  os.path.exists(result["centroid_path"]))
            check("Sample count > 0", result["sample_count"] > 0)
            check("Similarity is float",
                  isinstance(result["speaker_similarity"], float))

            # Load centroid
            centroid = np.load(result["centroid_path"])
            check("Centroid is numpy array", isinstance(centroid, np.ndarray))
            check("Centroid is unit vector",
                  abs(np.linalg.norm(centroid) - 1.0) < 0.01)

            # Check samples directory
            samples_dir = os.path.join(output_dir, "samples")
            check("Samples dir exists", os.path.isdir(samples_dir))
            sample_files = [f for f in os.listdir(samples_dir) if f.endswith(".wav")]
            check("Sample WAV files created", len(sample_files) > 0)

            # Test placeholder audio generation
            placeholder_path = os.path.join(tmpdir, "placeholder.wav")
            cloner._generate_placeholder_audio(placeholder_path)
            check("Placeholder audio created", os.path.exists(placeholder_path))

            with wave.open(placeholder_path, "r") as wf:
                check("Placeholder is 16kHz", wf.getframerate() == 16000)
                check("Placeholder is mono", wf.getnchannels() == 1)

    except Exception as e:
        print(f"  [FAIL] VoiceCloner error: {e}")
        import traceback
        traceback.print_exc()

    # ── 3. VoiceDesigner ──
    print("\n[3] Voice Designer...")
    try:
        from avatar.voice.voice_designer import (
            VoiceDesigner, DesignedVoice, VOICE_TEMPLATES,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            designer = VoiceDesigner()
            check("Designer instantiated", designer is not None)
            check("Qwen not available (expected)", not designer.available)

            # Design from description
            voice = designer.design(
                name="test_voice",
                description="warm male voice, 35, professional",
                output_dir=tmpdir,
            )

            check("Design returns DesignedVoice", isinstance(voice, DesignedVoice))
            check("Voice name set", voice.name == "test_voice")
            check("Voice description set",
                  "warm male" in voice.description)
            check("Voice language = en", voice.language == "en")
            check("Design config has model",
                  "model" in voice.design_config)

            # to_dict
            d = voice.to_dict()
            check("to_dict works", isinstance(d, dict))
            check("to_dict has name", d["name"] == "test_voice")

            # Templates
            templates = designer.list_templates()
            check("Has templates", len(templates) >= 5)
            check("Has professional_male", "professional_male" in templates)
            check("Has professional_female", "professional_female" in templates)
            check("Has friendly_assistant", "friendly_assistant" in templates)

            # From template
            tmpl_voice = designer.from_template(
                "professional_male",
                output_dir=tmpdir,
            )
            check("Template voice created", tmpl_voice is not None)
            check("Template name set",
                  tmpl_voice.name == "professional_male")

            # Invalid template
            try:
                designer.from_template("nonexistent")
                check("Invalid template raises", False)
            except ValueError:
                check("Invalid template raises", True)

            # All templates in VOICE_TEMPLATES
            check("6 templates defined", len(VOICE_TEMPLATES) == 6)

    except Exception as e:
        print(f"  [FAIL] VoiceDesigner error: {e}")
        import traceback
        traceback.print_exc()

    # ── 4. VoiceEngine ──
    print("\n[4] Voice Engine...")
    try:
        from avatar.voice.voice_engine import (
            VoiceEngine, VoiceEngineConfig, VoiceMode,
        )
        from avatar.voice.voice_registry import VoiceProfile

        with tempfile.TemporaryDirectory() as tmpdir:
            engine = VoiceEngine()
            check("Engine instantiated", engine is not None)

            # Available engines (only placeholder without models)
            engines = engine.available_engines
            check("Placeholder always available", "placeholder" in engines)

            # Stats
            stats = engine.stats
            check("Stats has qwen3_available", "qwen3_available" in stats)
            check("Stats has orpheus_available", "orpheus_available" in stats)
            check("Stats has best_of_n", stats["best_of_n"] == 12)

            # VoiceMode enum
            check("VoiceMode.CLONE", VoiceMode.CLONE.value == "clone")
            check("VoiceMode.DESIGN", VoiceMode.DESIGN.value == "design")
            check("VoiceMode.EMOTION", VoiceMode.EMOTION.value == "emotion")
            check("VoiceMode.AUTO", VoiceMode.AUTO.value == "auto")

            # Create test profile
            ref_audio = os.path.join(tmpdir, "ref.wav")
            _create_test_wav(ref_audio)

            profile = VoiceProfile(
                operator_id="test",
                mode="clone",
                engine="auto",
                language="en",
                reference_audio=ref_audio,
                centroid_path=None,
                design_prompt=None,
                sample_count=1,
                created_at="2024-01-01",
            )

            # Synthesize (placeholder mode)
            output_path = os.path.join(tmpdir, "output.wav")
            result = engine.synthesize(
                text="Hello, welcome to our service!",
                voice_profile=profile,
                output_path=output_path,
            )

            check("Synthesize returns path", isinstance(result, str))
            check("Output WAV exists", os.path.exists(result))

            with wave.open(result, "r") as wf:
                check("Output is 16kHz", wf.getframerate() == 16000)
                check("Output is mono", wf.getnchannels() == 1)
                check("Output is 16-bit", wf.getsampwidth() == 2)
                check("Output has content", wf.getnframes() > 0)
                duration = wf.getnframes() / wf.getframerate()
                check("Output duration > 0.5s", duration > 0.5)

            # Auto-generated output path
            result2 = engine.synthesize(
                text="Another test sentence.",
                voice_profile=profile,
            )
            check("Auto path works", os.path.exists(result2))
            os.unlink(result2)

            # Empty text raises
            try:
                engine.synthesize("", profile)
                check("Empty text raises", False)
            except ValueError:
                check("Empty text raises", True)

            # Emotion tag detection
            check("Detects <laugh>",
                  engine._has_emotion_tags("That's <laugh> funny!"))
            check("Detects <sigh>",
                  engine._has_emotion_tags("I <sigh> understand."))
            check("No tags in normal text",
                  not engine._has_emotion_tags("Hello there."))

            # Routing logic
            route = engine._route("Hello", profile, VoiceMode.AUTO)
            check("Auto routes to placeholder (no models)",
                  route == "placeholder")

            # Design mode profile
            design_profile = VoiceProfile(
                operator_id="designed",
                mode="design",
                engine="qwen3",
                language="en",
                reference_audio=None,
                centroid_path=None,
                design_prompt="warm female voice",
                sample_count=0,
                created_at="2024-01-01",
            )
            result3 = engine.synthesize(
                text="Designed voice test.",
                voice_profile=design_profile,
            )
            check("Design profile synthesis works", os.path.exists(result3))
            os.unlink(result3)

    except Exception as e:
        print(f"  [FAIL] VoiceEngine error: {e}")
        import traceback
        traceback.print_exc()

    # ── 5. Integration ──
    print("\n[5] Integration — Full Voice Pipeline...")
    try:
        from avatar.voice import (
            VoiceEngine, VoiceCloner, VoiceDesigner, VoiceRegistry,
            VoiceMode,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            # Step 1: Create "reference video" audio
            audio_path = os.path.join(tmpdir, "video_audio.wav")
            _create_test_wav(audio_path, duration_sec=10)

            # Step 2: Clone voice from audio
            cloner = VoiceCloner()
            avatars_dir = os.path.join(tmpdir, "avatars")
            os.makedirs(avatars_dir, exist_ok=True)

            registry = VoiceRegistry(base_dir=avatars_dir)
            profile = registry.create_from_audio(
                audio_path=audio_path,
                operator_id="integration_test",
                language="en",
            )
            check("Integration: voice profile created", profile is not None)
            check("Integration: profile persisted",
                  registry.get_profile("integration_test") is not None)

            # Step 3: Synthesize with engine
            engine = VoiceEngine()
            wav_path = engine.synthesize(
                text="Hello, I'm your Live Creatiq Operator.",
                voice_profile=profile,
            )
            check("Integration: synthesis complete", os.path.exists(wav_path))

            with wave.open(wav_path, "r") as wf:
                check("Integration: valid WAV", wf.getnframes() > 0)
            os.unlink(wav_path)

            # Step 4: Design a voice for another operator
            designer = VoiceDesigner()
            designed = designer.from_template("professional_female")
            registry.create_designed(
                operator_id="designed_op",
                design_prompt=designed.description,
            )
            check("Integration: designed voice registered",
                  registry.get_profile("designed_op") is not None)

            # Step 5: List all profiles
            all_profiles = registry.list_profiles()
            check("Integration: multiple profiles",
                  len(all_profiles) >= 2)

            # Step 6: Toggle emotion mode
            registry.set_emotion_mode("integration_test", enabled=True)
            updated = registry.get_profile("integration_test")
            check("Integration: emotion mode set",
                  updated.engine == "orpheus")

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


def _create_test_wav(path: str, duration_sec: float = 5.0, sample_rate: int = 16000):
    """Create a test WAV file with slight noise."""
    num_samples = int(sample_rate * duration_sec)
    # Sine wave + noise (simulates speech-like audio)
    t = np.linspace(0, duration_sec, num_samples, dtype=np.float32)
    audio = np.sin(2 * np.pi * 200 * t) * 2000
    audio += np.random.randn(num_samples) * 200
    audio = audio.astype(np.int16)

    with wave.open(path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio.tobytes())


if __name__ == "__main__":
    success = test_voice_pipeline()
    sys.exit(0 if success else 1)

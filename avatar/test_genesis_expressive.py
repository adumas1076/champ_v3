"""
Test: Generate Genesis saying the Skipper credit pitch with expressive emotion.

1. Generate WAV audio via Qwen3-TTS on Modal
2. Render with Ditto at emo=6 (happy/confident) on Modal A100
3. Save output video
"""

import base64
import os
import sys
import wave
import io

import modal

SCRIPT = (
    "Alright - credit can feel complicated and overwhelming. "
    "Honestly, it was designed that way, and nobody teaches this in school. "
    "That's why Skipper exists - to level the playing field for those action "
    "takers who want to get a second chance at having excellent credit."
)

GENESIS_IMAGE = os.path.join(
    os.path.dirname(__file__),
    "..", "..", "reference", "skipper_app_v5-livekit",
    "frontend", "src", "assets", "genesis-avatar.png",
)

OUTPUT_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "models", "avatars", "genesis",
)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # ── Step 1: Generate audio with TTS ──
    print(f"[1/3] Generating audio for: {SCRIPT[:60]}...")

    try:
        tts_cls = modal.Cls.from_name("champ-tts", "QwenTTSEngine")
        tts = tts_cls()

        result = tts.synthesize.remote(
            text=SCRIPT,
            design_prompt="A confident, warm female voice in her 30s, speaking clearly and persuasively",
            temperature=0.3,
        )

        if result.get("error"):
            print(f"[TTS] Error: {result['error']}")
            print("[TTS] Falling back to Ditto example audio...")
            example_audio = os.path.join(
                os.path.dirname(__file__), "..", "..", "reference", "ditto", "example", "audio.wav"
            )
            with open(example_audio, "rb") as f:
                audio_bytes = f.read()
        else:
            audio_bytes = base64.b64decode(result["audio_b64"])
            print(f"[TTS] Generated {result.get('duration_sec', '?')}s audio")

    except Exception as e:
        print(f"[TTS] Failed: {e}")
        print("[TTS] Falling back to Ditto example audio...")
        example_audio = os.path.join(
            os.path.dirname(__file__), "..", "..", "reference", "ditto", "example", "audio.wav"
        )
        with open(example_audio, "rb") as f:
            audio_bytes = f.read()

    # Save audio
    audio_path = os.path.join(OUTPUT_DIR, "genesis_credit_pitch.wav")
    with open(audio_path, "wb") as f:
        f.write(audio_bytes)
    print(f"[1/3] Audio saved: {audio_path} ({len(audio_bytes) // 1024} KB)")

    # ── Step 2: Load Genesis photo ──
    print(f"[2/3] Loading Genesis photo...")
    with open(GENESIS_IMAGE, "rb") as f:
        source_b64 = base64.b64encode(f.read()).decode()
    audio_b64 = base64.b64encode(audio_bytes).decode()

    # ── Step 3: Render with Ditto (emo=6 = expressive/confident) ──
    print(f"[3/3] Rendering with Ditto (emo=6, expressive)...")

    renderer_cls = modal.Cls.from_name("champ-ditto-avatar", "DittoAvatarRenderer")
    renderer = renderer_cls()

    result = renderer.render.remote(
        audio_b64=audio_b64,
        source_image_b64=source_b64,
        emo=6,  # more expressive than default 4
    )

    print(f"Rendered: {result['num_frames']} frames, "
          f"{result['duration_sec']}s, "
          f"{result['fps']} FPS")

    # Save video
    video_path = os.path.join(OUTPUT_DIR, "genesis_credit_pitch_expressive.mp4")
    video_bytes = base64.b64decode(result["video_b64"])
    with open(video_path, "wb") as f:
        f.write(video_bytes)
    print(f"Saved: {video_path} ({len(video_bytes) // 1024} KB)")
    print("DONE — open the video!")


if __name__ == "__main__":
    main()

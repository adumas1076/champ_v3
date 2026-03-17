"""
CHAMP Avatar — Fake Video Track Test
Joins the LiveKit room as an "avatar" participant and publishes
a test video track (animated gradient) so you can verify the
frontend renders it correctly.

Usage:
    cd champ_v3
    python -m avatar.test_video_track

Requires: livekit, livekit-api, numpy, Pillow
The agent must be running and a call must be active at localhost:3000/call.
"""

import asyncio
import os
import time
import math
import numpy as np
from dotenv import load_dotenv

load_dotenv()

LIVEKIT_URL = os.getenv("LIVEKIT_URL", "")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY", "")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "")
ROOM_NAME = "champ-room"
WIDTH = 512
HEIGHT = 512
FPS = 25


async def publish_test_video():
    from livekit import rtc, api

    if not LIVEKIT_URL or not LIVEKIT_API_KEY:
        print("[ERROR] Missing LIVEKIT_URL or LIVEKIT_API_KEY in .env")
        print("  Required env vars: LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET")
        return

    print("=" * 60)
    print("CHAMP Avatar — Fake Video Track Test")
    print("=" * 60)
    print(f"  LiveKit URL: {LIVEKIT_URL}")
    print(f"  Room: {ROOM_NAME}")
    print(f"  Resolution: {WIDTH}x{HEIGHT} @ {FPS}fps")
    print()

    # Generate a token for the avatar participant
    print("[1] Generating token for avatar participant...")
    token = (
        api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
        .with_identity("champ-avatar")
        .with_name("Champ Avatar")
        .with_grants(api.VideoGrants(
            room_join=True,
            room=ROOM_NAME,
            can_publish=True,
        ))
        .to_jwt()
    )
    print("    [OK] Token generated")

    # Connect to room
    print("[2] Connecting to LiveKit room...")
    room = rtc.Room()
    await room.connect(LIVEKIT_URL, token)
    print(f"    [OK] Connected as 'champ-avatar' to '{ROOM_NAME}'")

    # Create video source and track
    print("[3] Creating video source and publishing track...")
    source = rtc.VideoSource(WIDTH, HEIGHT)
    track = rtc.LocalVideoTrack.create_video_track("avatar-video", source)

    options = rtc.TrackPublishOptions(
        source=rtc.TrackSource.SOURCE_CAMERA,
    )
    await room.local_participant.publish_track(track, options)
    print("    [OK] Video track published")
    print()
    print("    Open localhost:3000/call — you should see animated video!")
    print("    Press Ctrl+C to stop.")
    print()

    # Load reference image if available
    ref_image = None
    ref_path = "frontend/public/operators/champ/champ_bio_01.png"
    try:
        from PIL import Image
        if os.path.exists(ref_path):
            img = Image.open(ref_path).convert("RGBA")
            img = img.resize((WIDTH, HEIGHT), Image.LANCZOS)
            ref_image = np.array(img)
            print(f"    Using reference image: {ref_path}")
        else:
            print(f"    Reference image not found, using gradient animation")
    except ImportError:
        print("    Pillow not installed, using gradient animation")

    # Push frames continuously
    frame_count = 0
    try:
        while True:
            t = time.monotonic()
            frame_count += 1

            if ref_image is not None:
                # Animate the reference image with a pulsing effect
                frame = ref_image.copy()
                pulse = math.sin(t * 2.0) * 0.08 + 1.0
                frame_rgb = frame[:, :, :3].astype(np.float32) * pulse
                frame[:, :, :3] = np.clip(frame_rgb, 0, 255).astype(np.uint8)

                # Add a colored border that cycles hue to prove it's animated
                hue = (t * 30) % 360
                r = int(128 + 127 * math.sin(math.radians(hue)))
                g = int(128 + 127 * math.sin(math.radians(hue + 120)))
                b = int(128 + 127 * math.sin(math.radians(hue + 240)))
                border = 4
                frame[:border, :, :3] = [r, g, b]
                frame[-border:, :, :3] = [r, g, b]
                frame[:, :border, :3] = [r, g, b]
                frame[:, -border:, :3] = [r, g, b]
            else:
                # Generate animated gradient
                frame = np.zeros((HEIGHT, WIDTH, 4), dtype=np.uint8)
                hue = (t * 20) % 360
                for y in range(HEIGHT):
                    r = int(128 + 127 * math.sin(math.radians(hue + y * 0.5)))
                    g = int(128 + 127 * math.sin(math.radians(hue + y * 0.5 + 120)))
                    b = int(128 + 127 * math.sin(math.radians(hue + y * 0.5 + 240)))
                    frame[y, :, 0] = r
                    frame[y, :, 1] = g
                    frame[y, :, 2] = b
                frame[:, :, 3] = 255

            # Publish frame
            video_frame = rtc.VideoFrame(
                WIDTH, HEIGHT,
                rtc.VideoBufferType.RGBA,
                frame.tobytes(),
            )
            source.capture_frame(video_frame)

            if frame_count % (FPS * 5) == 0:
                print(f"    ... {frame_count} frames published ({frame_count // FPS}s)")

            # Sleep to maintain FPS
            elapsed = time.monotonic() - t
            sleep_time = max(0, (1.0 / FPS) - elapsed)
            await asyncio.sleep(sleep_time)

    except KeyboardInterrupt:
        print(f"\n    Stopped after {frame_count} frames")

    await room.disconnect()
    print("    [OK] Disconnected from room")


if __name__ == "__main__":
    asyncio.run(publish_test_video())

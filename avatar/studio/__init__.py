"""
CHAMP Avatar Studio — Async Video Generation

The HeyGen-equivalent "video creation" feature:
  User provides: script text + avatar_id + voice config
  System returns: rendered MP4 video

Pipeline:
  1. RenderJob — orchestrates the full render
  2. Voice synthesis — TTS generates audio from script (via voice interface)
  3. FlashHead — generates video frames from audio + avatar reference
  4. VideoAssembler — stitches frames + audio into final MP4
  5. Templates — pre-built video configs (intro, demo, pitch, etc.)

This is the ASYNC counterpart to the real-time avatar (avatar/renderer.py).
Real-time = live video call. Studio = pre-rendered downloadable video.
"""

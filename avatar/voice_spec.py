"""
CHAMP Avatar — Voice Interface Specification

This file documents the contract between the Avatar system and the Voice system.
The Avatar session (this codebase) CONSUMES audio. The Main session PRODUCES audio.

═══════════════════════════════════════════════════════════════════════════════════
THIS FILE IS A SPEC — NOT AN IMPLEMENTATION.
The main session should implement a class matching VoiceProvider below.
═══════════════════════════════════════════════════════════════════════════════════

Two modes:

1. REAL-TIME MODE (live avatar calls)
   - Audio arrives frame-by-frame via LiveKit
   - push_audio(frame) receives raw bytes
   - No changes needed — whatever TTS the agent uses, audio flows through LiveKit

2. STUDIO MODE (async video rendering)
   - RenderJob needs a VoiceInterface that takes text -> WAV file
   - The main session implements this interface
   - See avatar/studio/render_job.py VoiceInterface class

═══════════════════════════════════════════════════════════════════════════════════

AUDIO FORMAT CONTRACT:

  Input to avatar pipeline:
    - Sample rate: 24000 Hz (OpenAI Realtime) or 16000 Hz (direct)
    - Channels: 1 (mono)
    - Format: int16 PCM (real-time) or float32 WAV (studio)
    - The ChunkAudioAccumulator handles resampling 24kHz -> 16kHz internally

  Output from TTS (what main session should produce):
    - WAV file at 16000 Hz, mono, 16-bit PCM
    - OR WAV file at 24000 Hz (will be resampled)
    - OR WAV file at 44100 Hz (will be resampled)
    - Minimum duration: 1 second
    - Maximum duration: 5 minutes (for studio renders)

═══════════════════════════════════════════════════════════════════════════════════

RECOMMENDED TTS STACK — DUAL ENGINE (Updated Phase 7):

  PRIMARY ENGINE: Qwen3-TTS (clone + multilingual + voice design)
    Model: Qwen/Qwen3-TTS-12Hz-1.7B-Base (Apache 2.0, pip install qwen-tts)
    Latency: 97ms to first audio (streaming)
    Clone: 3-second reference audio, ICL mode
    Selection: Best-of-12 with WavLM scoring at temperature 0.3
    Enrollment: 50-clip centroid from reference recordings
    Languages: 10
    Quality: 0.961 SECS with ClipCannon pipeline

  EMOTION ENGINE: Orpheus TTS (English, emotional expressiveness)
    Model: canopylabs/orpheus-tts-0.1-finetune-prod (Apache 2.0, pip install orpheus-speech)
    Latency: 25-50ms to first audio (streaming)
    Emotion tags: <laugh>, <sigh>, <chuckle>, <gasp>, <cough>, <yawn>
    Use case: English live calls where avatar needs to feel alive

  ROUTING: Auto-detect by language + emotion tags
    English + emotion tags → Orpheus
    English + clone → Qwen3-TTS ICL
    Multilingual + clone → Qwen3-TTS ICL
    Designed voice (no real person) → Qwen3-TTS VoiceDesign

  THREE VOICE MODES:
    CLONE  — Real person's voice from 2-min video audio
    DESIGN — AI-designed voice from text description ("warm female, 30s")
    EMOTION — Emotional English with laughs/sighs

  References:
    https://github.com/QwenLM/Qwen3-TTS (10K stars)
    https://github.com/canopyai/Orpheus-TTS (6K stars)
    https://huggingface.co/cabdru/clipcannon-voice-clone

═══════════════════════════════════════════════════════════════════════════════════

IMPLEMENTATION — ALREADY BUILT IN avatar/voice/:

  The Avatar Session has built the voice engine. Main Session just wires it up.

  from avatar.voice import VoiceEngine, VoiceRegistry, VoiceMode

  # 1. Create voice profile from operator's 2-min video
  registry = VoiceRegistry()
  profile = registry.create_from_video("recording.mp4", "genesis")
  # Audio is extracted from the SAME video used for avatar creation
  # One upload → face + voice. No extra recording needed.

  # 2. Or design a voice (no real person)
  profile = registry.create_designed("support_bot", "warm female, 30s, professional")

  # 3. Synthesize (auto-routes to best engine)
  engine = VoiceEngine()
  wav_path = engine.synthesize("Hello, welcome!", profile)

  # 4. Synthesize with emotion (Orpheus)
  wav_path = engine.synthesize("That's <laugh> amazing!", profile, mode=VoiceMode.EMOTION)

  # 5. Streaming for live calls
  async for chunk in engine.synthesize_stream("Hello!", profile):
      livekit_audio_track.push(chunk)

  # 6. Use with RenderJob (implements VoiceInterface)
  job = RenderJob(
      script="Hello world",
      avatar_id="genesis",
      voice=engine,  # VoiceEngine IS the VoiceInterface
  )
  result = await job.run()

═══════════════════════════════════════════════════════════════════════════════════

WHAT THE AVATAR SESSION OWNS (BUILT):
  - Audio consumption (push_audio, ChunkAudioAccumulator)
  - Video frame generation (FlashHead, upscaling, body composite)
  - Video assembly (frames + audio -> MP4)
  - Avatar management (registry, keyframes, LoRA)
  - Gaussian Splat pipeline (train, preview, export, motion driver)
  - PersonaLive wrapper (zero-training instant avatar)
  - Voice engine (dual-engine router, cloner, designer, registry)

WHAT THE MAIN SESSION OWNS (TO BUILD):
  - Install qwen-tts + orpheus-speech on Modal GPU
  - Deploy TTS inference endpoint (Modal A10G)
  - Wire VoiceEngine into LiveKit audio pipeline (replace OpenAI Realtime "ash")
  - API endpoints for avatar/voice/render operations
  - Frontend pages for video studio UI

═══════════════════════════════════════════════════════════════════════════════════
"""

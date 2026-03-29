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

RECOMMENDED TTS STACK (from ClipCannon research):

  Model: Qwen3-TTS-12Hz-1.7B-Base (HuggingFace, open source, free)
  Mode: Full ICL (pass reference audio + transcript, not just x-vector)
  Selection: Best-of-N with WavLM scoring (N=12, temperature=0.3)
  Enrollment: 50-clip centroid from reference recordings
  Quality gates: Duration ratio, WER via Whisper, SECS threshold

  This achieves 0.961 speaker similarity — indistinguishable from real person.

  Reference: https://huggingface.co/cabdru/clipcannon-voice-clone

═══════════════════════════════════════════════════════════════════════════════════

IMPLEMENTATION GUIDE FOR MAIN SESSION:

  1. Create a class that inherits from avatar.studio.render_job.VoiceInterface
  2. Implement synthesize(text, voice_config) -> str (path to WAV)
  3. Pass it to RenderJob:

     from avatar.studio.render_job import RenderJob

     class MyVoice(VoiceInterface):
         def synthesize(self, text, voice_config):
             # Your TTS logic here (Qwen3, OpenAI, ElevenLabs, etc.)
             return "/path/to/output.wav"

     job = RenderJob(
         script="Hello world",
         avatar_id="anthony",
         voice=MyVoice(),
     )
     result = await job.run()

  4. For real-time mode, no changes needed — audio flows through LiveKit automatically.

═══════════════════════════════════════════════════════════════════════════════════

WHAT THE AVATAR SESSION OWNS:
  - Audio consumption (push_audio, ChunkAudioAccumulator)
  - Video frame generation (FlashHead, upscaling, body composite)
  - Video assembly (frames + audio -> MP4)
  - Avatar management (registry, keyframes, LoRA)

WHAT THE MAIN SESSION OWNS:
  - TTS model loading and inference
  - Voice cloning / enrollment
  - ClipCannon pipeline (best-of-N, WavLM scoring)
  - API endpoints for triggering renders
  - Frontend pages for video studio UI

═══════════════════════════════════════════════════════════════════════════════════
"""

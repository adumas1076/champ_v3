# Avatar System — Handoff Specs for Other Sessions

> Everything in `avatar/` is built and tested (493/493). These specs tell the
> Main Session and UI Session exactly what to call and what to build.

---

## FOR MAIN SESSION (owns: agent.py, brain/, tools.py)

### 1. Voice/TTS Integration — ALREADY BUILT (avatar/voice/)

**What's built:** Dual-engine voice system with cloning, design, and emotion modes.
Main Session just needs to install dependencies and wire it into LiveKit.

```python
# The voice engine is ALREADY BUILT. Main Session uses it like this:
from avatar.voice import VoiceEngine, VoiceRegistry, VoiceMode, VoiceProfile

# Create voice profile from operator's 2-min video (same video as avatar)
registry = VoiceRegistry()
profile = registry.create_from_video("recording.mp4", "genesis")
# OR design a voice (no real person needed)
profile = registry.create_designed("support_bot", "warm female, 30s, professional")

# Synthesize (auto-routes: Qwen3-TTS for clone/multilingual, Orpheus for emotion)
engine = VoiceEngine()
wav_path = engine.synthesize("Hello, welcome!", profile)

# With emotion tags (routes to Orpheus automatically)
wav_path = engine.synthesize("That's <laugh> amazing!", profile)

# Streaming for live calls (replace OpenAI Realtime "ash")
async for chunk in engine.synthesize_stream("Hello!", profile):
    livekit_audio_track.push(chunk)
```

**What Main Session needs to do:**
1. `pip install qwen-tts orpheus-speech` (on Modal A10G or server with GPU)
2. Replace `openai.realtime.RealtimeModel(voice="ash")` in `operators/champ.py`
   with `VoiceEngine.synthesize_stream()` routed through LiveKit
3. That's it — the engine handles routing, scoring, and quality gates

**Audio format produced:**
- WAV file, 16kHz mono, 16-bit PCM
- Streaming: int16 PCM chunks at 16kHz

**Where the avatar consumes it:**
- Real-time: audio flows through LiveKit (engine produces stream chunks)
- Studio: `RenderJob` accepts `VoiceEngine` as its `voice` parameter

---

### 2. API Endpoints

**What to build:** REST routes that call the avatar backend.

**Create avatar from video:**
```python
# POST /api/avatar/create
from avatar.training.avatar_registry import AvatarRegistry

registry = AvatarRegistry()
meta = registry.create_from_video(
    video_path="/uploads/recording.mp4",
    avatar_id="anthony",
    name="Anthony",
)
# Returns: AvatarMetadata (avatar_id, frame_count, created_at, etc.)
```

**Create avatar from image:**
```python
# POST /api/avatar/create-from-image
meta = registry.create_from_image(
    image_path="/uploads/photo.png",
    avatar_id="anthony",
    name="Anthony",
)
```

**List avatars:**
```python
# GET /api/avatars
avatars = registry.list_avatars()
# Returns: list of AvatarMetadata
```

**Delete avatar:**
```python
# DELETE /api/avatar/:id
registry.delete_avatar("anthony")
```

**Start async render:**
```python
# POST /api/render
from avatar.studio.render_job import RenderJob, RenderConfig

job = RenderJob(
    script=request.body.script,
    avatar_id=request.body.avatar_id,
    voice=your_tts_implementation,       # <-- Main session provides this
    render_config=RenderConfig(
        upscale=request.body.upscale,
        include_body=request.body.include_body,
    ),
)
result = await job.run()
# Returns: RenderResult (video_path, duration, resolution, etc.)
```

**Get render status (if using Inngest):**
```python
# GET /api/render/:job_id
# Read from renders/job_{id}/metadata.json
```

**List templates:**
```python
# GET /api/templates
from avatar.studio.templates import list_templates
templates = list_templates()  # or list_templates(category="marketing")
```

---

### 3. Inngest Background Jobs (Antonio Pattern)

**What to build:** Wrap render jobs in Inngest for non-blocking UI.

```python
# Pattern from any Antonio repo's background-jobs branch
await inngest.send({
    "name": "avatar/render.started",
    "data": {
        "job_id": job.job_id,
        "script": script,
        "avatar_id": avatar_id,
        "render_config": {...},
    }
})

# Inngest function handles the heavy work async
@inngest.create_function(
    fn_id="avatar-render",
    trigger=inngest.TriggerEvent(event="avatar/render.started"),
)
async def handle_render(ctx):
    job = RenderJob(
        script=ctx.event.data["script"],
        avatar_id=ctx.event.data["avatar_id"],
        voice=ClipCannonVoice(),
        on_progress=lambda p: update_db(ctx.event.data["job_id"], p),
    )
    result = await job.run()
    await update_db(ctx.event.data["job_id"], result)
```

---

### 4. Auth + Multi-Tenant

**What to build:** Clerk Organizations wrapping avatar registry.

Each organization gets its own avatar namespace:
```python
# Avatar IDs scoped to org: "{org_id}/{avatar_id}"
registry = AvatarRegistry(base_dir=f"models/avatars/{org_id}")
```

**Reference:** Any Antonio repo's `authentication` branch.

---

### 5. Billing (Polar Metered)

**What to build:** Usage tracking per render.

```python
# Two meters (Resonance pattern):
# 1. video_render — Sum over "seconds" field (video duration)
# 2. avatar_creation — Count (per avatar created)

# After each render:
await polar.meters.ingest({
    "meter_name": "video_render",
    "value": result.duration_sec,
    "org_id": org_id,
})
```

**Reference:** Resonance `09-billing` branch.

---

## FOR UI SESSION (owns: frontend/src/)

### 6. Avatar Creation Page

**Route:** `/create-avatar`

**Flow:**
1. User uploads 2-min video (or takes a photo)
2. Frontend sends to POST `/api/avatar/create`
3. Show progress (keyframe extraction takes ~30s)
4. Display extracted keyframes for review
5. User confirms -> avatar is registered

**Backend calls:**
- `POST /api/avatar/create` (video upload)
- `POST /api/avatar/create-from-image` (photo upload)
- `GET /api/avatars` (list user's avatars)

---

### 7. Video Studio Page

**Route:** `/studio`

**Flow:**
1. User selects avatar from gallery
2. User picks a template (product_demo, sales_pitch, etc.) or "custom"
3. User writes/pastes script text
4. User clicks "Render"
5. Frontend sends to POST `/api/render`
6. Show progress bar (render_job sends progress callbacks)
7. When complete, show video player + download button

**Backend calls:**
- `GET /api/templates` (list available templates)
- `POST /api/render` (start render)
- `GET /api/render/:job_id` (poll status/progress)

**UI components needed:**
- Script editor (textarea with word count)
- Template selector (cards with name, description, category)
- Avatar picker (grid of user's avatars with thumbnails)
- Render progress bar (maps to RenderProgress.progress 0-1)
- Video player (HTML5 video with download button)
- Render settings panel (upscale toggle, body toggle, quality)

---

### 8. Dashboard / Landing

**Route:** `/` and `/dashboard`

**Shows:**
- Recent renders (from metadata.json files)
- Avatar gallery
- Quick-action buttons: "New Video", "Create Avatar"
- Usage stats (if billing is wired)

**Reference:** Any Antonio repo's `02-dashboard` branch.

---

## ARCHITECTURE SUMMARY

```
Frontend (UI Session)
  /create-avatar     -> POST /api/avatar/create
  /studio            -> POST /api/render
  /dashboard         -> GET /api/avatars, GET /api/renders
  /live-call         -> gsplat.js + WebRTC DataChannel (Phase 7)

API Layer (Main Session)
  POST /api/avatar/create     -> avatar.training.avatar_registry
  POST /api/avatar/create-splat -> avatar.splat (Phase 7 — full pipeline)
  POST /api/render            -> avatar.studio.render_job (via Inngest)
  GET  /api/render/:id        -> renders/job_{id}/metadata.json
  GET  /api/avatars           -> avatar.training.avatar_registry
  GET  /api/avatar/:id/splat  -> serve .ply/.splat file for browser download
  GET  /api/templates         -> avatar.studio.templates

Avatar Engine (Avatar Session — Phases 1-6 DONE, Phase 7 DONE)
  avatar/training/     <- Avatar creation (keyframes, LoRA)
  avatar/studio/       <- Video rendering (script -> MP4)
  avatar/renderer.py   <- Live avatar (real-time WebRTC)
  avatar/gpu_backend.py <- GPU routing (local/Modal)
  avatar/upscale.py    <- 4K output
  avatar/body/         <- Body + gestures
  avatar/splat/        <- Gaussian Splat pipeline (Phase 7)
    train_splat.py             <- Video → FLAME-rigged 3DGS
    motion_driver.py           <- Blendshapes → MotionFrame → DataChannel
    instant_preview.py         <- Single photo → 3DGS preview in seconds
    virtual_capture_studio.py  <- 3 photos → 96 synthetic views
    splat_export.py            <- Export .ply/.splat for browser delivery

Voice Engine (Main Session — TO BUILD)
  ClipCannonVoice      <- Qwen3-TTS + ICL + best-of-N + WavLM
  Implements avatar.studio.render_job.VoiceInterface
```

---

## PHASE 7 HANDOFF — Gaussian Splat Pipeline

### For Main Session: New API Endpoints

**Create splat avatar (full pipeline):**
```python
# POST /api/avatar/create-splat
from avatar.splat import VirtualCaptureStudio, SplatTrainer, InstantPreviewGenerator
from avatar.splat.motion_driver import SplatMotionDriver
from avatar.training.avatar_registry import AvatarRegistry

registry = AvatarRegistry()

# Step 1: Instant preview (3 seconds)
preview = InstantPreviewGenerator()
preview_path = preview.generate(image_path="selfie.jpg", avatar_id="anthony")
registry.update_splat_status("anthony", "preview", preview_path=preview_path)

# Step 2: Virtual Capture Studio (background, ~2 min)
studio = VirtualCaptureStudio()
capture = studio.capture(photos=["front.jpg", "left.jpg", "right.jpg"], avatar_id="anthony")
registry.update_splat_status("anthony", "training", synthetic_views_dir=capture.output_dir)

# Step 3: Full training (background via Inngest, 20-60 min)
trainer = SplatTrainer()
result = trainer.train(
    video_path="recording.mp4",
    avatar_id="anthony",
    synthetic_views_dir=capture.output_dir,
)
registry.update_splat_status(
    "anthony", "ready",
    splat_path=result.splat_path,
    num_gaussians=result.num_gaussians,
)
```

**Serve splat for browser download:**
```python
# GET /api/avatar/:id/splat
from avatar.splat import SplatExporter, ExportFormat

exporter = SplatExporter()
web_path = exporter.export_for_web(
    splat_path=registry.get_splat_path("anthony"),
    format=ExportFormat.SPLAT,  # Compressed for web (26 bytes/Gaussian)
)
# Serve web_path as binary download with Content-Type: application/octet-stream
```

**Live call motion via WebRTC DataChannel:**
```python
# In LiveKit room handler — replace video track publish with DataChannel
from avatar.splat.motion_driver import SplatMotionDriver, MotionFrame

driver = SplatMotionDriver()
driver.load_avatar("anthony")

# Each frame (25fps):
motion_vec = motion_predictor.predict(audio_features)  # (55,) from avatar/motion.py
gesture = gesture_predictor.predict(audio_features)     # from avatar/body/
frame = driver.drive(motion_vec, gesture=gesture)
datachannel.send(frame.to_bytes())  # 229 bytes per frame = 5.7 KB/s
```

### For UI Session: gsplat.js Integration

**Browser-side 3DGS rendering:**
```typescript
// GaussianSplatAvatar.tsx — new component for live calls
import * as GaussianSplats3D from '@mkkellogg/gaussian-splats-3d';

// 1. Load splat file (cached, one-time download ~50-200MB)
const viewer = new GaussianSplats3D.Viewer({ /* canvas config */ });
await viewer.loadFile('/api/avatar/anthony/splat');

// 2. Receive motion params via WebRTC DataChannel (229 bytes/frame)
dataChannel.onmessage = (event) => {
    const frame = parseMotionFrame(event.data);  // 52 blendshapes + 3 head pose
    // Apply blendshapes to FLAME mesh → deform Gaussians → re-render
    applyMotionToSplat(viewer, frame);
};

// 3. Render at 120+ FPS locally — NO server GPU needed
```

**Client metadata endpoint:**
```python
# GET /api/avatar/:id/splat/meta
from avatar.splat import SplatExporter
meta = SplatExporter().get_client_metadata(splat_path)
# Returns: {num_gaussians, file_size_mb, bbox, center, motion_frame_rate, ...}
```

---

## PERSONALIVE HANDOFF — Zero-Training Instant Avatar

PersonaLive (CVPR 2026, Apache 2.0) provides a zero-training instant avatar mode.
User uploads a single selfie → live animated avatar in seconds (no training wait).
Uses streaming diffusion on server GPU. 2D only, ~10-30 FPS.

### For Main Session: PersonaLive Integration

**Instant avatar (no training, single photo):**
```python
# POST /api/avatar/personalive/start
from avatar.splat import PersonaLiveRenderer, PersonaLiveConfig

renderer = PersonaLiveRenderer()
renderer.initialize("selfie.jpg")  # Identity encoded in ~2 seconds

# In live call loop — two options:
# Option A: Webcam-driven (client sends webcam frames)
output_frame = renderer.process_frame(webcam_frame)  # 512x512 RGBA

# Option B: Audio-driven (bridge from our MotionPredictor)
from avatar.motion import MotionPredictor
motion_vec = motion_predictor.predict(audio_features)
blendshapes = motion_vec[:52]
head_pose = motion_vec[52:]
driving_frame = renderer.generate_driving_from_blendshapes(blendshapes, head_pose)
output_frame = renderer.process_frame(driving_frame)

# Send output_frame via WebRTC video track (NOT DataChannel — this is 2D video)
```

**Lifecycle:**
```
User uploads selfie
  → PersonaLive starts instantly (zero training)
  → Meanwhile: VirtualCaptureStudio + SplatTrainer runs in background
  → When 3DGS training completes: auto-switch to GAUSSIAN_SPLAT mode
  → User gets holographic 3D avatar, no server GPU needed for live calls
```

### For UI Session: Mode Switching

```typescript
// Avatar modes — show appropriate renderer
if (avatar.splat_status === "ready") {
    // Best: 3D Gaussian Splat (client-rendered, 120+ FPS, any angle)
    <GaussianSplatAvatar splatUrl={avatar.splat_url} />
} else {
    // Fallback: PersonaLive (server-rendered, 10-30 FPS, front-facing)
    <VideoStream src={personalive_webrtc_track} />
}
```

---

## RENDER MODES COMPARISON

| Mode | Training | Server GPU | Camera Angles | FPS | Best For |
|---|---|---|---|---|---|
| `PERSONALIVE` | None (instant) | Yes (per session) | Fixed front | 10-30 | Try before you train |
| `GAUSSIAN_SPLAT` | 20-60 min | No (client renders) | Any angle | 120+ | Live calls at scale |
| `FLASHHEAD_FULL` | LoRA optional | Yes (per render) | Fixed front | N/A (async) | Pre-rendered MP4 |
| `PLACEHOLDER` | None | None | Fixed front | 25 | Dev/testing |

---

## QUICK START FOR EACH SESSION

**Main Session:**
```python
# Phase 1-6 (async video):
from avatar.training.avatar_registry import AvatarRegistry
from avatar.studio.render_job import RenderJob, VoiceInterface
from avatar.studio.templates import get_template, list_templates

# Phase 7 (Gaussian Splat):
from avatar.splat import (
    SplatTrainer, InstantPreviewGenerator,
    VirtualCaptureStudio, SplatExporter, ExportFormat,
)
from avatar.splat.motion_driver import SplatMotionDriver, MotionFrame

# Phase 7 (PersonaLive — zero-training):
from avatar.splat import PersonaLiveRenderer, PersonaLiveConfig

# 1. Implement VoiceInterface (ClipCannon + Qwen3-TTS)
# 2. Create API routes (see endpoints above)
# 3. Wrap training in Inngest for async
# 4. Replace video track with DataChannel for 3DGS live calls
# 5. Add PersonaLive as instant fallback during training
```

**UI Session:**
```
Phase 1-6:
  1. Build /create-avatar page (video upload + progress)
  2. Build /studio page (script editor + template picker + render)
  3. Build /dashboard (avatar gallery + recent renders)

Phase 7 (new):
  4. Build GaussianSplatAvatar.tsx — gsplat.js renderer component
  5. Build useSplatMotion.ts — DataChannel motion receiver hook
  6. Add splat status indicators to avatar creation flow
  7. Add PersonaLive ↔ GaussianSplat mode auto-switching
  8. All backend calls are REST — see endpoints above
```

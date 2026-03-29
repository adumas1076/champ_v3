# Avatar System — Handoff Specs for Other Sessions

> Everything in `avatar/` is built and tested (215/215). These specs tell the
> Main Session and UI Session exactly what to call and what to build.

---

## FOR MAIN SESSION (owns: agent.py, brain/, tools.py)

### 1. Voice/TTS Integration (ClipCannon Pattern)

**What to build:** A class that implements `VoiceInterface.synthesize(text, voice_config) -> str`

**Interface contract:** See `avatar/voice_spec.py` for full details.

```python
from avatar.studio.render_job import VoiceInterface

class ClipCannonVoice(VoiceInterface):
    """
    Recommended stack:
    - Model: Qwen3-TTS-12Hz-1.7B-Base (HuggingFace)
    - Mode: Full ICL (reference audio + transcript, NOT x-vector only)
    - Selection: Best-of-12 with WavLM scoring at temperature 0.3
    - Enrollment: 50-clip centroid from avatar reference recordings
    - Quality gates: duration ratio, WER via Whisper, SECS threshold

    Reference: https://huggingface.co/cabdru/clipcannon-voice-clone
    """
    def synthesize(self, text: str, voice_config: dict) -> str:
        # 1. Load Qwen3-TTS model
        # 2. Build ICL prompt with reference audio + transcript
        # 3. Generate N=12 candidates at temperature=0.3
        # 4. Score each with WavLM (microsoft/wavlm-base-plus-sv)
        # 5. Select highest scoring candidate
        # 6. Run quality gates (duration, WER, SECS)
        # 7. Save as WAV (16kHz mono) and return path
        return "/path/to/output.wav"
```

**Audio format required:**
- WAV file, 16kHz mono, 16-bit PCM (preferred)
- 24kHz or 44.1kHz also accepted (auto-resampled)
- Min 1 second, max 5 minutes

**Where the avatar consumes it:**
- Real-time: audio flows through LiveKit automatically (no changes)
- Studio: `RenderJob` calls `voice.synthesize()` then feeds WAV to FlashHead

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

API Layer (Main Session)
  POST /api/avatar/create     -> avatar.training.avatar_registry
  POST /api/render            -> avatar.studio.render_job (via Inngest)
  GET  /api/render/:id        -> renders/job_{id}/metadata.json
  GET  /api/avatars           -> avatar.training.avatar_registry
  GET  /api/templates         -> avatar.studio.templates

Avatar Engine (Avatar Session — DONE)
  avatar/training/     <- Avatar creation (keyframes, LoRA)
  avatar/studio/       <- Video rendering (script -> MP4)
  avatar/renderer.py   <- Live avatar (real-time WebRTC)
  avatar/gpu_backend.py <- GPU routing (local/Modal)
  avatar/upscale.py    <- 4K output
  avatar/body/         <- Body + gestures

Voice Engine (Main Session — TO BUILD)
  ClipCannonVoice      <- Qwen3-TTS + ICL + best-of-N + WavLM
  Implements avatar.studio.render_job.VoiceInterface
```

---

## QUICK START FOR EACH SESSION

**Main Session:**
```python
# 1. Import what you need
from avatar.training.avatar_registry import AvatarRegistry
from avatar.studio.render_job import RenderJob, VoiceInterface
from avatar.studio.templates import get_template, list_templates

# 2. Implement VoiceInterface
# 3. Create API routes calling the above
# 4. Wrap renders in Inngest for async
```

**UI Session:**
```
1. Build /create-avatar page (video upload + progress)
2. Build /studio page (script editor + template picker + render)
3. Build /dashboard (avatar gallery + recent renders)
4. All backend calls are REST — see endpoints above
```

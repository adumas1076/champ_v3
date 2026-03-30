# Live Creatiq Operator — Pipeline Architecture

> How to build a holographic real-time avatar TODAY using AI to replace
> every expensive step in the traditional volumetric capture pipeline.

---

## THE ORIGINAL PROCESS (What 4DV.AI Does)

The "correct" way to create a 4D Gaussian Splat avatar:

```
STEP 1: VOLUMETRIC CAPTURE STUDIO
  - 96 synchronized cameras (4K @ 60fps each)
  - Controlled lighting rig
  - Green/black cyclorama background
  - Subject performs for 2-5 minutes
  - Cost: $500K+ studio build, $1K+ per session
  - Output: 96 × 4K × 60fps = ~23 TB of raw data per minute

STEP 2: MULTI-VIEW RECONSTRUCTION
  - Process all 96 camera feeds simultaneously
  - Structure from motion across 96 viewpoints
  - Dense point cloud → 3D Gaussian Splat
  - Each Gaussian gets: position, shape, opacity, spherical harmonics
  - Cost: Data center GPU cluster, hours of processing
  - Output: 3D Gaussian Splat (.ply file)

STEP 3: 4D TEMPORAL PROCESSING
  - Each frame gets its own 3D reconstruction
  - Compute velocity + time span per Gaussian (4DV.AI's innovation)
  - Enable continuous interpolation (not frame-by-frame)
  - Cost: More GPU time
  - Output: 4D Gaussian Splat (position + motion over time)

STEP 4: COMPRESSION
  - 4DV.AI compresses to 30-60 Mbps (100x smaller than raw video)
  - Moving Gaussians represent hundreds of frames each
  - Output: Streamable 4D hologram file

STEP 5: PLAYBACK
  - Stream to browser/VR/phone
  - Client renders Gaussians in real-time
  - Any camera angle, any frame rate
```

**Total cost to create ONE avatar:** $10,000-$50,000+
**Total time:** Days of processing
**Who can afford this:** Movie studios, huge companies

---

## THE DR. FRANKENSTEIN PROCESS (What AI Replaces)

Every expensive step above has an AI replacement that exists TODAY:

### STEP 1: CAPTURE → Phone Camera (2-min selfie video)

**Original:** 96 cameras in a studio
**AI replacement:** Single phone camera, 2-minute recording

| AI Tech | What It Does | Open Source? | Link |
|---|---|---|---|
| **Mono-Splat** | Monocular webcam → deformable 3DGS avatar | Yes | [Paper](https://sciety.org/articles/activity/10.20944/preprints202512.2774.v1) |
| **HUGS (Apple)** | 50-100 frames → animatable human + scene | Yes | [Apple ML](https://machinelearning.apple.com/research/hugs) |
| **FastAvatar** | Single image → full-head 3DGS in 3 SECONDS | Yes | [Paper](https://arxiv.org/abs/2508.18389) |
| **GaussianAvatars** | Video → FLAME-rigged Gaussians (controllable) | Yes | [GitHub](https://github.com/ShenhanQian/GaussianAvatars) |

**Dr. Frankenstein pick:** FastAvatar (3 seconds from ONE photo) for instant creation,
GaussianAvatars (from video) for higher quality.

**What the user does:** Record a 2-min video on their phone. That's it.

### STEP 2: 3D RECONSTRUCTION → AI Monocular Reconstruction

**Original:** 96-camera triangulation + dense matching
**AI replacement:** Neural network predicts 3D from 2D

| AI Tech | What It Does | Training Time | Quality |
|---|---|---|---|
| **FastAvatar** | Feed-forward encoder → 3DGS in 3 seconds | 3 seconds | Good |
| **Mono-Splat** | Webcam video → deformable 3DGS | 20 minutes | Very good |
| **HUGS** | Monocular video → human + scene | 30 minutes | Very good |
| **GaussianAvatars** | Multi-frame → FLAME-rigged Gaussians | 1-2 hours | Excellent |

**Dr. Frankenstein pick:** Two-stage approach:
1. FastAvatar for instant preview (3 seconds, from first frame)
2. GaussianAvatars training in background (1 hour, from full video) → replaces preview

### STEP 3: AUDIO-DRIVEN ANIMATION → AI Motion From Speech

**Original:** 4DV.AI records actual motion with 96 cameras
**AI replacement:** AI predicts motion from audio alone

| AI Tech | What It Does | FPS | Open Source? |
|---|---|---|---|
| **GaussianTalker** | Audio → deforms 3DGS talking head | 130 FPS | [GitHub](https://github.com/cvlab-kaist/GaussianTalker) |
| **VASA-3D** (Microsoft) | Audio → lifelike 3DGS animation from single image | 75 FPS | Paper only |
| **Our motion.py** | Audio → 52 blendshapes + head pose | CPU-speed | Already built |

**Dr. Frankenstein pick:** GaussianTalker (open source, 130 FPS, audio-driven).
Our existing `motion.py` produces the same 52-blendshape format — can drive GaussianAvatars directly.

### STEP 4: COMPRESSION → Already Tiny

**Original:** 4DV.AI custom compression (30-60 Mbps)
**Our approach:** Even simpler — don't stream video at all

```
We send: 55 floats per frame = 220 bytes × 25fps = 5.5 KB/s
4DV.AI sends: 30-60 Mbps compressed 4D hologram
HeyGen sends: ~4 MB/s video stream

Our approach is 700× smaller than 4DV.AI and 700× smaller than HeyGen.
```

The 3DGS model file (50-200MB) is downloaded ONCE and cached on the client.
After that, only motion parameters flow over the wire.

### STEP 5: CLIENT RENDERING → Browser WebGL/WebGPU

**Original:** Custom renderer
**AI replacement:** Open source browser renderers

| Renderer | Tech | Platform | Link |
|---|---|---|---|
| **gsplat.js** (HuggingFace) | WebGL | Browser | [GitHub](https://github.com/huggingface/gsplat.js/) |
| **GaussianSplats3D** | Three.js | Browser | [GitHub](https://github.com/mkkellogg/GaussianSplats3D) |
| **WebSplatter** | WebGPU | Browser (modern) | [Paper](https://arxiv.org/html/2602.03207) |
| **splat** (antimatter15) | WebGL 1.0 | Browser (any) | [GitHub](https://github.com/antimatter15/splat) |

**Dr. Frankenstein pick:** gsplat.js (HuggingFace, well-maintained) + WebGPU upgrade path via WebSplatter.

---

## THE NEW PIPELINE — Live Creatiq Operator

### User Flow (What The Customer Experiences)

```
1. RECORD (30 seconds)
   User opens app → records 2-min selfie video on phone
   (No studio, no special lighting, no restrictions)

2. PREVIEW (3 seconds)
   FastAvatar creates instant 3D preview from first frame
   User sees their 3D avatar immediately — can rotate, zoom, inspect

3. TRAIN (background, 20-60 minutes)
   Full GaussianAvatars training runs in background (Modal GPU)
   Replaces preview with high-quality FLAME-rigged 3DGS avatar
   User gets notification: "Your Live Creatiq Operator is ready"

4. USE (real-time, forever)
   Avatar joins video calls as a Live Creatiq Operator
   Speaks with cloned voice (ClipCannon/Qwen3-TTS)
   Renders at 120+ FPS in user's browser
   No server GPU needed for live calls
```

### Technical Flow (What Actually Happens)

```
CREATION (one-time):
  Phone video (2 min, any phone)
    │
    ├─→ [FastAvatar] Single frame → 3DGS preview (3 sec, A100)
    │     → Instant preview for user
    │
    ├─→ [GaussianAvatars] Full video → FLAME-rigged 3DGS (20-60 min, Modal A10G)
    │     → Production avatar with expression control
    │     → Replaces preview when done
    │
    ├─→ [ClipCannon] Audio track → voice clone enrollment (5 min)
    │     → 50-clip centroid + Qwen3-TTS ICL reference
    │
    └─→ [Avatar Registry] Store: splat.ply + motion model + voice fingerprint
          → models/avatars/{id}/splat/, lora/, voice/

LIVE CALL (real-time):
  Operator LLM generates response text
    │
    ├─→ [Qwen3-TTS + ClipCannon] Text → cloned voice audio
    │     → Best-of-N + WavLM scoring (server, ~200ms)
    │
    ├─→ [MotionPredictor] Audio → 52 blendshapes + 3 head pose
    │     → Our existing motion.py (server, CPU-only, <2ms)
    │
    ├─→ [Smoothing] EMA + transitions + anticipatory motion
    │     → Our existing smoothing.py (server, CPU-only, <1ms)
    │
    ├─→ [GesturePredictor] Audio energy → gesture class
    │     → Our existing gesture_predictor.py (server, CPU-only, <1ms)
    │
    └─→ WebRTC DataChannel: {blendshapes: [55 floats], gesture: "emphasis"}
          → 220 bytes per frame, 5.5 KB/s total
          │
          CLIENT BROWSER:
          ├─→ [gsplat.js] Load cached .ply → apply motion params → render 3DGS
          │     → 120+ FPS, any camera angle, WebGL/WebGPU
          │
          └─→ <video> element displays holographic Live Creatiq Operator

ASYNC VIDEO STUDIO (pre-rendered MP4):
  Script text + avatar_id
    │
    ├─→ [Qwen3-TTS] Full script → voice audio WAV
    ├─→ [FlashHead] Audio → diffusion video frames (highest quality)
    ├─→ [Real-ESRGAN] 512→4K upscale
    ├─→ [BodyCompositor] Face + body template
    └─→ [ffmpeg] Frames + audio → MP4
          → Download link for user
```

---

## PARTS SHELF — What To Frankenstein

### Avatar Creation

| Part | Source | License | Status |
|---|---|---|---|
| FastAvatar (instant preview) | [arxiv](https://arxiv.org/abs/2508.18389) | Academic | Need to clone |
| GaussianAvatars (production) | [GitHub](https://github.com/ShenhanQian/GaussianAvatars) | Apache 2.0 | Need to clone |
| FLAME face model | [GitHub](https://github.com/TimoBolkart/FLAME-Universe) | Academic | Need to download |
| Our keyframe extraction | `avatar/training/extract_keyframes.py` | Ours | DONE |
| Our avatar registry | `avatar/training/avatar_registry.py` | Ours | DONE |

### Audio-Driven Animation

| Part | Source | License | Status |
|---|---|---|---|
| GaussianTalker | [GitHub](https://github.com/cvlab-kaist/GaussianTalker) | MIT | Need to clone |
| Our MotionPredictor | `avatar/motion.py` | Ours | DONE (52 blendshapes) |
| Our IdleAnimator | `avatar/idle.py` | Ours | DONE |
| Our MotionSmoother | `avatar/smoothing.py` | Ours | DONE |
| Our GesturePredictor | `avatar/body/gesture_predictor.py` | Ours | DONE |

### Voice Cloning

| Part | Source | License | Status |
|---|---|---|---|
| ClipCannon pipeline | [HuggingFace](https://huggingface.co/cabdru/clipcannon-voice-clone) | Open | Main session to build |
| Qwen3-TTS-1.7B | HuggingFace | Apache 2.0 | Main session to build |
| Our voice spec | `avatar/voice_spec.py` | Ours | DONE |

### Client Rendering

| Part | Source | License | Status |
|---|---|---|---|
| gsplat.js | [GitHub](https://github.com/huggingface/gsplat.js/) | MIT | UI session to integrate |
| GaussianSplats3D | [GitHub](https://github.com/mkkellogg/GaussianSplats3D) | MIT | Alternative |
| WebSplatter (WebGPU) | [Paper](https://arxiv.org/html/2602.03207) | Academic | Future upgrade |
| Our useAvatar hook | `frontend/src/hooks/useAvatar.ts` | Ours | DONE (needs splat mode) |

### Infrastructure

| Part | Source | License | Status |
|---|---|---|---|
| Our GPU backend | `avatar/gpu_backend.py` | Ours | DONE |
| Our Modal deploy | `avatar/modal_deploy.py` | Ours | DONE |
| Our render job | `avatar/studio/render_job.py` | Ours | DONE |
| Our video assembler | `avatar/studio/video_assembler.py` | Ours | DONE |
| Our templates | `avatar/studio/templates.py` | Ours | DONE |
| Antonio's billing pattern | Resonance `09-billing` | Reference | Main session |
| Antonio's auth pattern | Any repo `authentication` | Reference | Main session |
| Antonio's Inngest pattern | Any repo `background-jobs` | Reference | Main session |

---

## COST COMPARISON

### Per-Avatar Creation Cost

| Method | Hardware | Time | Cost |
|---|---|---|---|
| 4DV.AI studio | 96 cameras + GPU cluster | Days | $10,000+ |
| HeyGen | Upload 2-min video | Minutes | $0 (included in plan) |
| **Live Creatiq Operator** | Phone + Modal A10G | 20-60 min training | **~$0.50** (Modal GPU time) |

### Per-Minute Live Call Cost

| Platform | Server GPU? | Cost/min | Concurrent sessions |
|---|---|---|---|
| HeyGen | Yes | $0.10 | ~10/GPU |
| Tavus | Yes | $0.32 | ~10/GPU |
| **Live Creatiq Operator** | **No** | **~$0.001** (CPU only) | **1,000+/server** |

### At Scale (1,000 concurrent sessions)

| Platform | Monthly cost |
|---|---|
| HeyGen | ~$432,000 (100 GPUs × $0.10/min × 720 hrs) |
| **Live Creatiq Operator** | ~$500 (1 server + CPU) |

---

## BUILD ORDER

### Phase 7A: Clone + Test GaussianTalker (avatar/ session)
```bash
cd reference/
git clone https://github.com/cvlab-kaist/GaussianTalker.git
# Test: can we drive a 3DGS model with audio?
```

### Phase 7B: Clone + Test GaussianAvatars (avatar/ session)
```bash
cd reference/
git clone https://github.com/ShenhanQian/GaussianAvatars.git
# Test: can we create a FLAME-rigged 3DGS from monocular video?
```

### Phase 7C: Build Splat Creation Pipeline (avatar/ session)
```
avatar/splat/
  train_splat.py      — 2-min video → 3DGS avatar via GaussianAvatars
  motion_driver.py    — Apply blendshapes to rigged Gaussians
```

### Phase 7D: Build Client Renderer (UI session)
```
frontend/src/components/
  GaussianSplatAvatar.tsx   — gsplat.js renderer component
  useSplatMotion.ts         — Receive motion params via DataChannel
```

### Phase 7E: Motion-Only WebRTC Channel (main session)
```
Replace video track publish with DataChannel for motion params
220 bytes/frame instead of video frames
```

### Phase 7F: FastAvatar Instant Preview (avatar/ session)
```
avatar/splat/
  instant_preview.py  — Single image → 3DGS in 3 seconds
```

---

## WHAT'S ALREADY DONE vs WHAT'S LEFT

### DONE (Phases 1-6, this session)
- FlashHead full diffusion renderer (async video, highest quality)
- 2-min video keyframe extraction
- Avatar registry (CRUD, metadata)
- LoRA fine-tuning pipeline
- Real-ESRGAN 4K upscaling
- GPU backend (local + Modal)
- Body motion + gesture prediction
- Async video studio (script → MP4)
- 7 video templates
- Voice interface spec
- Handoff specs for other sessions
- 215 tests, all passing

### LEFT (Phase 7, future sessions)

**Avatar session can build:**
- Clone GaussianTalker + GaussianAvatars to reference/
- Build `avatar/splat/` package (train, drive, preview)
- Test audio-driven 3DGS rendering

**Main session needs to build:**
- ClipCannon voice clone (Qwen3-TTS + best-of-N + WavLM)
- API endpoints (render, avatar CRUD, templates)
- Inngest background jobs for training
- Auth (Clerk) + billing (Polar)
- WebRTC DataChannel for motion params (replacing video track)

**UI session needs to build:**
- gsplat.js integration (GaussianSplatAvatar.tsx component)
- Avatar creation page (upload video → training progress → preview)
- Video studio page (script → template → render → download)
- Dashboard

---

*The Live Creatiq Operator: a holographic AI operator that lives in your browser.*
*No server GPU for live calls. No filming constraints. Any camera angle.*
*Created from a 2-minute phone video. Costs $0.50 to make. $0.001/min to run.*
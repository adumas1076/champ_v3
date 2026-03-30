# Live Operator Avatar — Gaussian Splat Architecture

> The Live Operator is our real-time avatar system.
> This document captures the Phase 7 vision: replacing 2D video rendering
> with 3D/4D Gaussian Splatting for holographic operator presence.

---

## Why Gaussian Splats Beat Everything Else

### The Problem With All Current Approaches (Including Ours)

HeyGen, Tavus, Beyond Presence, and our FlashHead pipeline all generate **flat 2D video frames** on a server GPU, then stream them to the client via WebRTC. This has fundamental limits:

- Camera angle is LOCKED (one viewpoint)
- Server GPU required for EVERY frame of EVERY session
- ~3-10 concurrent sessions per GPU
- No VR/AR support (it's a flat rectangle)
- Cost scales linearly with users

### What Gaussian Splatting Changes

A Gaussian Splat is a **3D point cloud** where each point is a fuzzy blob (Gaussian) with:
- Position (x, y, z)
- Shape (spherical, stretched, flat)
- Opacity (transparent to solid)
- View-dependent color via **spherical harmonics** (different shade from every angle)

Millions of these Gaussians create the illusion of photorealism — like brushstrokes in a painting.

**4D Gaussian Splats** (from 4DV.AI) add:
- Velocity per Gaussian (continuous motion, not frame-by-frame)
- Time span (Gaussians appear and disappear)
- Interpolation to ANY frame rate (1,000+ FPS from 60fps capture)
- Compression: 30-60 Mbps for full hologram (100x smaller than raw video)

### The Architecture Shift

```
CURRENT (2D, server-rendered):
  Audio → [SERVER GPU: FlashHead renders 512x512 per frame] → WebRTC video → Client displays

GAUSSIAN SPLAT (3D, client-rendered):
  Audio → [SERVER CPU: predict motion params ~200 bytes] → WebRTC data → Client renders 3DGS locally
```

The rendering moves to the CLIENT. The server only sends motion parameters.

---

## Comparison Table

| | HeyGen | Our FlashHead | Gaussian Splat (Phase 7) |
|---|---|---|---|
| Representation | 2D video | 2D video | TRUE 3D point cloud |
| Camera angle | Fixed | Fixed | Any angle, real-time |
| Server GPU per session | Yes ($0.10/min) | Yes ($0 local) | NO |
| Client rendering | Just video playback | Just video playback | 3DGS at 120+ FPS |
| Concurrent sessions/server | ~10 | ~3 | 1,000+ (just motion data) |
| VR/AR ready | No | No | YES |
| Quality | Good (2D) | Better (2D diffusion) | Holographic (3D) |
| Reflections/transparency | Baked | Baked | Spherical harmonics (real) |
| Hair/fine detail | Flat | Flat | True 3D depth |
| Motion | Frame-by-frame | Chunk-by-chunk | Continuous (velocity) |
| Cost at scale | $$$$ | $$ | $ |

---

## How It Works For The Live Operator

### Creation Phase (one-time, GPU required)

```
User records 2-min video
  ↓
Monocular 3DGS reconstruction
  (Train Gaussian Splat of person's head/body from single camera)
  ↓
Audio-to-motion model training
  (Learn how THIS person's face moves when speaking)
  ↓
Output:
  - .ply splat file (~50-200MB, person's 3D appearance)
  - motion model weights (~50MB, person-specific deformations)
  - Stored in avatar registry: models/avatars/{avatar_id}/splat/
```

### Real-Time Phase (live calls, NO server GPU)

```
Operator speaks via LLM
  ↓
TTS generates audio (server, Qwen3-TTS)
  ↓
Motion predictor: audio → 52 blendshapes + 3 head pose (server, CPU-only)
  (Uses our existing avatar/motion.py — already built)
  ↓
Send via WebRTC data channel:
  - Motion params: 55 floats = 220 bytes per frame
  - At 25fps = 5.5 KB/s (vs ~4 MB/s for video frames)
  ↓
Client browser:
  - Loads .ply splat file (cached, one-time download)
  - Receives motion params in real-time
  - Deforms Gaussians based on blendshapes
  - Renders at 120+ FPS locally
  - User sees photorealistic holographic operator
```

### Key Numbers

- Motion data bandwidth: **5.5 KB/s** (vs 4,000 KB/s for video)
- Client rendering: **120+ FPS** (GaussianTalker benchmark)
- Server load per session: **~0.1% CPU** (just motion prediction, no GPU)
- Concurrent sessions per server: **1,000+** (no GPU bottleneck)
- Avatar file size: **50-200MB** (cached on client, loaded once)

---

## What Already Exists To Frankenstein

### Open Source / Research

| Project | What It Does | How We Use It |
|---|---|---|
| **GaussianTalker** | Audio-driven 3DGS talking head, 120 FPS | Core renderer |
| **3DGS from monocular video** | Train splat from single camera | Avatar creation from 2-min video |
| **SuperSplat** | WebGL Gaussian Splat viewer (browser) | Client-side rendering |
| **Tavus Phoenix** | 3DGS + diffusion (proprietary) | Architecture reference |
| **4DV.AI** | 4D continuous Gaussian Splats | Motion continuity pattern |
| **gsplat.js / splat.js** | JavaScript Gaussian Splat renderers | Frontend integration |

### What We Already Built (Reusable)

| Our Component | Reuse In Splat Mode |
|---|---|
| `avatar/motion.py` — MotionPredictor | Audio → 52 blendshapes + head pose (same output) |
| `avatar/states.py` — AvatarStateMachine | IDLE/LISTENING/SPEAKING (unchanged) |
| `avatar/idle.py` — IdleAnimator | Procedural idle motion (same output format) |
| `avatar/smoothing.py` — EMA + transitions | Smooth motion params before sending (unchanged) |
| `avatar/controller.py` — LiveKit bridge | Room events → state changes (unchanged) |
| `avatar/body/gesture_predictor.py` | Audio → gesture class (drives body deformations) |
| `avatar/training/extract_keyframes.py` | Video → keyframes (used for splat training too) |
| `avatar/training/avatar_registry.py` | Avatar CRUD + metadata (add splat file paths) |
| `avatar/gpu_backend.py` | GPU routing for training (local/Modal) |

The entire motion + state + smoothing pipeline stays the same.
Only the rendering changes: from "server generates frames" to "client renders splat."

---

## Implementation Path

### Phase 7A: Monocular 3DGS Avatar Creation

New files in `avatar/splat/`:
```
avatar/splat/
  __init__.py
  train_splat.py      — 2-min video → 3D Gaussian Splat (.ply)
  splat_registry.py   — Manage splat files per avatar
  motion_driver.py    — Deform Gaussians from blendshape params
```

### Phase 7B: Client-Side Splat Renderer

Frontend work (UI session):
```
frontend/src/components/
  GaussianSplatAvatar.tsx   — WebGL splat renderer component
  useSplatAvatar.ts         — Hook: load splat + receive motion params
```

### Phase 7C: Motion-Only WebRTC Channel

Replace video track with data channel:
```
Server: motion params → WebRTC DataChannel (220 bytes/frame)
Client: DataChannel → deform splat → render locally
```

### Phase 7D: 4D Continuous Motion (4DV.AI pattern)

Add velocity + time span to Gaussians for smooth motion:
- No frame-by-frame jumping
- Infinite FPS interpolation
- Ultra-smooth lip sync

---

## RenderMode Integration

```python
class RenderMode(Enum):
    GAUSSIAN_SPLAT = "gaussian_splat"    # 3DGS client-side (Phase 7, best for live)
    FLASHHEAD_FULL = "flashhead_full"    # Diffusion server-side (best for async MP4)
    SPLIT_PIPELINE = "split_pipeline"    # Legacy LivePortrait warp
    PLACEHOLDER = "placeholder"          # Dev/testing
```

| Use Case | Best Mode |
|---|---|
| Live operator calls | GAUSSIAN_SPLAT (client-rendered, zero server GPU) |
| Async video studio (MP4) | FLASHHEAD_FULL (highest quality diffusion) |
| VR/AR presence | GAUSSIAN_SPLAT (true 3D, any viewpoint) |
| Low-bandwidth | GAUSSIAN_SPLAT (5.5 KB/s vs 4 MB/s) |
| Offline renders | FLASHHEAD_FULL (best single-frame quality) |

---

## The Business Moat

This is what makes CHAMP's Live Operator fundamentally different from HeyGen:

1. **Zero server GPU for live calls** — HeyGen pays for GPU per minute per user. We don't.
2. **Unlimited concurrency** — Motion params are CPU-only. One server handles 1,000+ sessions.
3. **Holographic, not flat** — Users can view the operator from any angle. VR-ready.
4. **Real 3D transparency** — Glasses, glass tables, hair depth — all rendered correctly.
5. **No filming constraints** — No "remove your glasses" or "don't move your hands." 3D captures everything.
6. **Cost inverts at scale** — HeyGen's cost goes UP with users. Ours stays flat.

HeyGen can't switch to this architecture without rebuilding everything.
We're building from scratch — we build it right.

---

## Source Research

- 4DV.AI: 4D Gaussian Splatting with continuous motion representation
  - 96 cameras, 60fps capture → 30-60 Mbps compressed 4D hologram
  - Gaussians have velocity + time span (not frame-by-frame)
  - 1,000-10,000 FPS interpolation from 60fps source
  - Renders in browser, phone, VR headset

- GaussianTalker: Audio-driven 3D Gaussian Splatting
  - 120 FPS rendering (state of the art)
  - Audio → face deformation on 3DGS model

- Tavus Phoenix: 3DGS for talking heads
  - 60+ FPS, 1080p, Gaussian-diffusion architecture
  - Trained from 2-min video recording

- Spherical harmonics: mathematical minimalism for view-dependent color
  - Single base color + formula for directional variation
  - No infinite color storage needed

- SuperSplat: browser-based Gaussian Splat viewer
  - WebGL rendering, real-time, shareable

---

*This document represents the architecture vision for the Live Operator avatar system.*
*Phases 1-6 (FlashHead pipeline) are built and tested (215/215 tests).*
*Phase 7 (Gaussian Splat) is the next evolution — from 2D video to 3D hologram.*
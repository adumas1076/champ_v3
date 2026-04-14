"""
CHAMP V3 Brain — Avatar API Routes

8 REST endpoints for the avatar + voice + splat pipeline.
All heavy work is done by avatar/ — these are thin wrappers.

Routes:
  POST /api/avatar/create          — Upload video → create avatar + voice profile
  POST /api/avatar/create-image    — Upload photo → create avatar (image only)
  GET  /api/avatars                — List all avatars
  DELETE /api/avatar/{avatar_id}   — Delete avatar + voice profile
  POST /api/render                 — Script → MP4 video render
  GET  /api/render/{job_id}        — Poll render status
  GET  /api/avatar/{avatar_id}/splat      — Download .splat for browser
  GET  /api/avatar/{avatar_id}/splat/meta — Client rendering metadata
"""

import asyncio
import json
import logging
import os
import shutil
import tempfile
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, UploadFile, File, Form, Request
from fastapi.responses import JSONResponse, FileResponse

logger = logging.getLogger("champ.brain.avatar_routes")

router = APIRouter(prefix="/api", tags=["avatar"])

# In-memory render job tracking (maps to disk metadata for persistence)
_render_jobs: dict = {}


# ═══════════════════════════════════════════════════════════════════════
# AVATAR CRUD
# ═══════════════════════════════════════════════════════════════════════

@router.post("/avatar/create")
async def create_avatar(
    file: UploadFile = File(...),
    avatar_id: str = Form(default=""),
    name: str = Form(default=""),
    language: str = Form(default="en"),
):
    """
    Create an avatar from a 2-min video.
    Extracts keyframes for FlashHead AND audio for voice cloning.
    One upload → face + voice.
    """
    from avatar.training.avatar_registry import AvatarRegistry
    from avatar.voice import VoiceRegistry

    if not avatar_id:
        avatar_id = f"avatar-{uuid4().hex[:8]}"

    # Save uploaded file
    tmp_dir = tempfile.mkdtemp()
    file_path = os.path.join(tmp_dir, file.filename or "upload.mp4")
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    try:
        # Create avatar from video
        registry = AvatarRegistry()
        meta = registry.create_from_video(
            video_path=file_path,
            avatar_id=avatar_id,
            name=name or avatar_id,
        )

        # Create voice profile from same video
        voice_registry = VoiceRegistry()
        voice_profile = voice_registry.create_from_video(
            video_path=file_path,
            operator_id=avatar_id,
            language=language,
        )

        # Start instant preview in background
        asyncio.create_task(_generate_preview(avatar_id, file_path))

        logger.info(f"[AVATAR] Created '{avatar_id}' from video")

        return {
            "avatar_id": avatar_id,
            "name": meta.name,
            "frame_count": meta.frame_count,
            "voice_mode": voice_profile.mode,
            "voice_samples": voice_profile.sample_count,
            "speaker_similarity": voice_profile.speaker_similarity,
            "splat_status": meta.splat_status,
        }

    except Exception as e:
        logger.error(f"[AVATAR] Create failed: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@router.post("/avatar/create-image")
async def create_avatar_from_image(
    file: UploadFile = File(...),
    avatar_id: str = Form(default=""),
    name: str = Form(default=""),
):
    """Create an avatar from a single photo. No voice cloning (use design mode)."""
    from avatar.training.avatar_registry import AvatarRegistry
    from avatar.splat.instant_preview import InstantPreviewGenerator

    if not avatar_id:
        avatar_id = f"avatar-{uuid4().hex[:8]}"

    tmp_dir = tempfile.mkdtemp()
    file_path = os.path.join(tmp_dir, file.filename or "upload.png")
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    try:
        registry = AvatarRegistry()
        meta = registry.create_from_image(
            image_path=file_path,
            avatar_id=avatar_id,
            name=name or avatar_id,
        )

        # Generate instant 3DGS preview
        preview_gen = InstantPreviewGenerator()
        preview_path = preview_gen.generate(file_path, avatar_id)
        registry.update_splat_status(avatar_id, "preview", preview_path=preview_path)

        logger.info(f"[AVATAR] Created '{avatar_id}' from image")

        return {
            "avatar_id": avatar_id,
            "name": meta.name,
            "frame_count": meta.frame_count,
            "splat_status": "preview",
            "preview_path": preview_path,
        }

    except Exception as e:
        logger.error(f"[AVATAR] Create from image failed: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@router.get("/avatars")
async def list_avatars():
    """List all registered avatars with their status."""
    from avatar.training.avatar_registry import AvatarRegistry
    from avatar.voice import VoiceRegistry

    registry = AvatarRegistry()
    voice_registry = VoiceRegistry()

    avatars = []
    for meta in registry.list_avatars():
        voice = voice_registry.get_profile(meta.avatar_id)
        avatars.append({
            "avatar_id": meta.avatar_id,
            "name": meta.name,
            "source_type": meta.source_type,
            "frame_count": meta.frame_count,
            "splat_status": meta.splat_status,
            "num_gaussians": meta.num_gaussians,
            "has_voice": voice is not None,
            "voice_mode": voice.mode if voice else None,
            "created_at": meta.created_at,
        })

    return {"avatars": avatars, "count": len(avatars)}


@router.delete("/avatar/{avatar_id}")
async def delete_avatar(avatar_id: str):
    """Delete an avatar and its voice profile."""
    from avatar.training.avatar_registry import AvatarRegistry
    from avatar.voice import VoiceRegistry

    registry = AvatarRegistry()
    voice_registry = VoiceRegistry()

    deleted_avatar = registry.delete_avatar(avatar_id)
    deleted_voice = voice_registry.delete_profile(avatar_id)

    if not deleted_avatar:
        return JSONResponse(
            status_code=404,
            content={"error": f"Avatar '{avatar_id}' not found"},
        )

    return {
        "deleted": True,
        "avatar_id": avatar_id,
        "voice_deleted": deleted_voice,
    }


# ═══════════════════════════════════════════════════════════════════════
# VIDEO RENDERING
# ═══════════════════════════════════════════════════════════════════════

@router.post("/render")
async def start_render(request: Request):
    """
    Start an async video render (script → MP4).
    Returns immediately with job_id. Poll /api/render/{job_id} for progress.
    """
    from avatar.studio.render_job import RenderJob, RenderConfig
    from avatar.voice import VoiceEngine, VoiceRegistry

    body = await request.json()
    script = body.get("script", "")
    avatar_id = body.get("avatar_id", "")
    upscale = body.get("upscale", False)
    include_body = body.get("include_body", True)
    template = body.get("template")

    if not script:
        return JSONResponse(status_code=400, content={"error": "Missing 'script'"})
    if not avatar_id:
        return JSONResponse(status_code=400, content={"error": "Missing 'avatar_id'"})

    # Load voice
    voice_registry = VoiceRegistry()
    voice_profile = voice_registry.get_profile(avatar_id)

    engine = VoiceEngine()
    job_id = f"render-{uuid4().hex[:8]}"

    # Start render in background
    async def _do_render():
        try:
            _render_jobs[job_id] = {"status": "running", "progress": 0}

            job = RenderJob(
                script=script,
                avatar_id=avatar_id,
                voice=engine,
                render_config=RenderConfig(
                    upscale=upscale,
                    include_body=include_body,
                ),
                on_progress=lambda p: _render_jobs[job_id].update({"progress": p.progress}),
            )

            result = await job.run()

            _render_jobs[job_id] = {
                "status": "complete",
                "progress": 1.0,
                "video_path": result.video_path,
                "duration": result.duration_sec,
                "resolution": f"{result.width}x{result.height}",
            }

        except Exception as e:
            _render_jobs[job_id] = {"status": "failed", "error": str(e)}

    asyncio.create_task(_do_render())

    _render_jobs[job_id] = {"status": "started", "progress": 0}

    return {"job_id": job_id, "status": "started", "avatar_id": avatar_id}


@router.get("/render/{job_id}")
async def render_status(job_id: str):
    """Poll render job status."""
    if job_id not in _render_jobs:
        return JSONResponse(
            status_code=404,
            content={"error": f"Render job '{job_id}' not found"},
        )

    return {"job_id": job_id, **_render_jobs[job_id]}


# ═══════════════════════════════════════════════════════════════════════
# GAUSSIAN SPLAT DELIVERY
# ═══════════════════════════════════════════════════════════════════════

@router.get("/avatar/{avatar_id}/image")
async def get_avatar_image(avatar_id: str):
    """Serve the avatar's reference image."""
    from avatar.training.avatar_registry import AvatarRegistry

    registry = AvatarRegistry()
    meta = registry.get_avatar(avatar_id)

    ref_path = meta.reference_image if meta else ""
    # Handle relative paths
    if ref_path and not os.path.isabs(ref_path):
        from avatar import config as avatar_config
        ref_path = str(avatar_config.CHAMP_ROOT / ref_path)

    if not ref_path or not os.path.exists(ref_path):
        return JSONResponse(
            status_code=404,
            content={"error": f"No image for '{avatar_id}'"},
        )

    return FileResponse(
        ref_path,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get("/avatar/{avatar_id}/splat")
async def get_splat(avatar_id: str):
    """
    Download the .splat file for browser-side gsplat.js rendering.
    Returns compressed .splat format (26 bytes per Gaussian).
    """
    from avatar.training.avatar_registry import AvatarRegistry
    from avatar.splat import SplatExporter, ExportFormat

    registry = AvatarRegistry()
    splat_path = registry.get_splat_path(avatar_id)

    if not splat_path or not os.path.exists(splat_path):
        return JSONResponse(
            status_code=404,
            content={"error": f"No splat available for '{avatar_id}'"},
        )

    # Export compressed version for web
    exporter = SplatExporter()
    web_path = splat_path.replace(".ply", "_web.splat")

    if not os.path.exists(web_path):
        exporter.export_for_web(splat_path, web_path, format=ExportFormat.SPLAT)

    return FileResponse(
        web_path,
        media_type="application/octet-stream",
        filename=f"{avatar_id}.splat",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get("/avatar/{avatar_id}/splat/meta")
async def get_splat_meta(avatar_id: str):
    """
    Client metadata for rendering the splat.
    Returns: num_gaussians, file_size, bbox, center, motion_frame_rate, etc.
    """
    from avatar.training.avatar_registry import AvatarRegistry
    from avatar.splat import SplatExporter

    registry = AvatarRegistry()
    splat_path = registry.get_splat_path(avatar_id)

    if not splat_path or not os.path.exists(splat_path):
        return JSONResponse(
            status_code=404,
            content={"error": f"No splat available for '{avatar_id}'"},
        )

    exporter = SplatExporter()
    meta = exporter.get_client_metadata(splat_path)
    meta["avatar_id"] = avatar_id

    # Add avatar status info
    avatar_meta = registry.get_avatar(avatar_id)
    if avatar_meta:
        meta["splat_status"] = avatar_meta.splat_status
        meta["name"] = avatar_meta.name

    return meta


# ═══════════════════════════════════════════════════════════════════════
# BACKGROUND TASKS
# ═══════════════════════════════════════════════════════════════════════

async def _generate_preview(avatar_id: str, source_path: str):
    """Background task: generate instant 3DGS preview + start VCS."""
    try:
        from avatar.splat.instant_preview import InstantPreviewGenerator
        from avatar.splat.virtual_capture_studio import VirtualCaptureStudio
        from avatar.training.avatar_registry import AvatarRegistry

        registry = AvatarRegistry()

        # Instant preview
        preview_gen = InstantPreviewGenerator()
        preview_path = preview_gen.generate(source_path, avatar_id)
        registry.update_splat_status(avatar_id, "preview", preview_path=preview_path)
        logger.info(f"[AVATAR] Preview generated for '{avatar_id}'")

        # Virtual Capture Studio (96 views)
        studio = VirtualCaptureStudio()
        result = studio.capture(photos=[source_path], avatar_id=avatar_id)
        registry.update_splat_status(
            avatar_id, "training",
            synthetic_views_dir=result.output_dir,
        )
        logger.info(
            f"[AVATAR] VCS complete for '{avatar_id}': "
            f"{result.num_views} views"
        )

    except Exception as e:
        logger.error(f"[AVATAR] Background preview failed for '{avatar_id}': {e}")

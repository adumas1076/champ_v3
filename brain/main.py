# ============================================
# CHAMP V3 — Brain Entry Point
# Phase 2: THE BRAIN
# FastAPI server that wires persona + mode
# detection + LiteLLM proxy together.
# ============================================
# "Built to build. Born to create."

import asyncio
import json
import logging
from contextlib import asynccontextmanager

import requests

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

from brain.config import load_settings
from brain.models import ChatCompletionRequest
from brain.pipeline import BrainPipeline
from mind.learning import LearningLoop
from self_mode.engine import SelfModeEngine
from self_mode.heartbeat import Heartbeat
from self_mode.nlp_to_goal import generate_goal_card

settings = load_settings()

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    pipeline = BrainPipeline(settings)
    await pipeline.startup()
    app.state.pipeline = pipeline
    app.state.learning = LearningLoop(settings)
    app.state.self_mode_tasks = {}  # run_id -> asyncio.Task

    # Start Self Mode heartbeat (polls for queued runs every 30 min)
    heartbeat = Heartbeat(settings, memory=pipeline.memory)
    await heartbeat.start()
    app.state.heartbeat = heartbeat

    logger.info(
        f"CHAMP V3 Brain ready on port {settings.port} | "
        f"LiteLLM upstream: {settings.litellm_base_url} | "
        f"Self Mode heartbeat: ON"
    )
    yield
    await heartbeat.stop()
    await pipeline.shutdown()
    logger.info("CHAMP V3 Brain shut down")


app = FastAPI(
    title="CHAMP V3 Brain",
    description="Phase 2: Persona + Mode Detection + LiteLLM Router",
    version="3.0.0",
    lifespan=lifespan,
)


# ---- Health Check ----
@app.get("/health")
async def health():
    return {"status": "ok", "service": "champ-v3-brain", "phase": 2, "memory": True}


# ---- Session Lifecycle ----
@app.post("/v1/session/start")
async def session_start(request: Request):
    """Start a new conversation session. Returns conversation_id."""
    pipeline: BrainPipeline = request.app.state.pipeline
    body = await request.json() if request.headers.get("content-length", "0") != "0" else {}
    channel = body.get("channel", "voice")
    conversation_id = await pipeline.memory.start_session(channel=channel)
    return {"conversation_id": conversation_id}


@app.post("/v1/session/end")
async def session_end(request: Request):
    """End a conversation session. Triggers learning extraction."""
    pipeline: BrainPipeline = request.app.state.pipeline
    learning: LearningLoop = request.app.state.learning
    body = await request.json()
    conversation_id = body.get("conversation_id")
    if conversation_id:
        # Run learning extraction before ending session
        try:
            await learning.capture(conversation_id, pipeline.memory)
        except Exception as e:
            logger.error(f"Learning capture failed (non-fatal): {e}")
        await pipeline.memory.end_session(conversation_id)
    return {"status": "ok"}


# ---- Chat Completions (OpenAI-compatible) ----
@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """
    OpenAI-compatible chat completions endpoint.
    Voice agent or gate test hits this.
    Brain enriches with persona + mode, forwards to LiteLLM.
    """
    pipeline: BrainPipeline = request.app.state.pipeline

    # Parse request
    try:
        body = await request.json()
        logger.info(
            f"Incoming: model={body.get('model')}, "
            f"stream={body.get('stream')}, "
            f"messages={len(body.get('messages', []))} msgs"
        )
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={"error": {"message": f"Invalid JSON: {e}"}},
        )

    try:
        chat_request = ChatCompletionRequest(**body)
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={"error": {"message": f"Validation error: {e}"}},
        )

    if chat_request.stream:
        # Streaming response (primary path for voice)
        async def event_stream():
            try:
                async for raw_line in pipeline.handle_stream(chat_request):
                    yield f"{raw_line}\n\n"
            except Exception as e:
                logger.error(f"Stream error: {e}", exc_info=True)
                error_data = json.dumps({"error": str(e)})
                yield f"data: {error_data}\n\n"
                yield "data: [DONE]\n\n"

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    else:
        # Non-streaming response (gate test path)
        try:
            response = await pipeline.handle_request(chat_request)
            return JSONResponse(content=response.model_dump())
        except Exception as e:
            logger.error(f"Request error: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"error": {"message": str(e)}},
            )


# ---- Self Mode Endpoints (Brick 8.5) ----

@app.post("/v1/self_mode/submit")
async def self_mode_submit(request: Request):
    """
    Submit a natural language task to Self Mode.
    Brain generates a Goal Card from the request and starts autonomous execution.
    Returns immediately with run_id -- execution happens in the background.
    """
    pipeline: BrainPipeline = request.app.state.pipeline

    try:
        body = await request.json()
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={"error": f"Invalid JSON: {e}"},
        )

    task_text = body.get("task", "").strip()
    if not task_text:
        return JSONResponse(
            status_code=400,
            content={"error": "Missing 'task' field"},
        )

    dry_run = body.get("dry_run", False)

    # Get memory context for richer Goal Card generation
    context = ""
    try:
        context = await pipeline.memory.get_context()
    except Exception:
        pass

    # Generate Goal Card from natural language
    try:
        goal_card_text = generate_goal_card(task_text, settings, context=context)
    except Exception as e:
        logger.error(f"[SELF MODE] Goal Card generation failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to generate Goal Card: {e}"},
        )

    # Create engine and run in background
    engine = SelfModeEngine(settings, memory=pipeline.memory)

    async def _run_self_mode(eng, text, is_dry, rid):
        try:
            return await eng.run(text, dry_run=is_dry, run_id=rid)
        except Exception as exc:
            logger.error(f"[SELF MODE] Background run failed: {exc}")
            return None

    from uuid import uuid4
    from datetime import datetime, timezone
    run_id = (
        f"RUN-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
        f"-{uuid4().hex[:6]}"
    )

    task = asyncio.create_task(
        _run_self_mode(engine, goal_card_text, dry_run, run_id)
    )
    request.app.state.self_mode_tasks[run_id] = task

    logger.info(f"[SELF MODE] Submitted run {run_id} for: {task_text[:80]}")

    return {
        "run_id": run_id,
        "status": "started" if not dry_run else "dry_run_started",
        "task": task_text,
        "goal_card_text": goal_card_text,
    }


@app.get("/v1/self_mode/status/{run_id}")
async def self_mode_status(run_id: str, request: Request):
    """Check the status of a Self Mode run."""
    pipeline: BrainPipeline = request.app.state.pipeline

    # Check in-memory task first
    task = request.app.state.self_mode_tasks.get(run_id)
    in_memory_status = None
    result_pack = None
    if task:
        if task.done():
            in_memory_status = "finished"
            try:
                rp = task.result()
                if rp:
                    result_pack = rp.to_dict()
            except Exception as e:
                in_memory_status = "error"
                result_pack = {"error": str(e)}
        else:
            in_memory_status = "running"

    # Also check Supabase for persistent state
    db_record = None
    try:
        db_record = await pipeline.memory.get_self_mode_run(run_id)
    except Exception:
        pass

    if not db_record and not task:
        return JSONResponse(
            status_code=404,
            content={"error": f"Run {run_id} not found"},
        )

    return {
        "run_id": run_id,
        "in_memory_status": in_memory_status,
        "db_status": db_record.get("status") if db_record else None,
        "current_step": db_record.get("current_step") if db_record else None,
        "result_pack": result_pack or (db_record.get("result_pack") if db_record else None),
    }


@app.get("/v1/self_mode/runs")
async def self_mode_runs(request: Request):
    """List recent Self Mode runs."""
    pipeline: BrainPipeline = request.app.state.pipeline

    runs = []
    try:
        if pipeline.memory._client:
            result = await pipeline.memory._client.table(
                "self_mode_runs"
            ).select(
                "id, status, current_step, created_at, updated_at"
            ).order(
                "created_at", desc=True
            ).limit(20).execute()
            runs = result.data or []
    except Exception as e:
        logger.error(f"[SELF MODE] Failed to list runs: {e}")

    return {"runs": runs, "count": len(runs)}


@app.post("/v1/self_mode/approve/{run_id}")
async def self_mode_approve(run_id: str, request: Request):
    """Approve a Self Mode run that is awaiting approval, then resume."""
    pipeline: BrainPipeline = request.app.state.pipeline

    db_record = await pipeline.memory.get_self_mode_run(run_id)
    if not db_record:
        return JSONResponse(
            status_code=404,
            content={"error": f"Run {run_id} not found"},
        )

    if db_record.get("status") != "awaiting_approval":
        return JSONResponse(
            status_code=400,
            content={
                "error": (
                    f"Run {run_id} is not awaiting approval "
                    f"(status={db_record.get('status')})"
                )
            },
        )

    engine = SelfModeEngine(settings, memory=pipeline.memory)

    async def _resume_approved(eng, rid):
        try:
            return await eng.resume(rid)
        except Exception as exc:
            logger.error(f"[SELF MODE] Resume after approval failed: {exc}")
            return None

    task = asyncio.create_task(_resume_approved(engine, run_id))
    request.app.state.self_mode_tasks[run_id] = task

    logger.info(f"[SELF MODE] Approved and resuming run {run_id}")
    return {"run_id": run_id, "status": "approved_and_resuming"}


@app.post("/v1/self_mode/resume/{run_id}")
async def self_mode_resume(run_id: str, request: Request):
    """Resume a crashed or blocked Self Mode run from its last checkpoint."""
    pipeline: BrainPipeline = request.app.state.pipeline

    db_record = await pipeline.memory.get_self_mode_run(run_id)
    if not db_record:
        return JSONResponse(
            status_code=404,
            content={"error": f"Run {run_id} not found"},
        )

    status = db_record.get("status", "")
    resumable = {
        "awaiting_approval", "blocked", "failed",
        "fixing", "executing", "reviewing",
    }
    if status not in resumable:
        return JSONResponse(
            status_code=400,
            content={
                "error": (
                    f"Run {run_id} has status '{status}' which is not "
                    f"resumable. Resumable: {', '.join(sorted(resumable))}"
                )
            },
        )

    # Reject if already running in memory
    existing = request.app.state.self_mode_tasks.get(run_id)
    if existing and not existing.done():
        return JSONResponse(
            status_code=409,
            content={"error": f"Run {run_id} is already running"},
        )

    engine = SelfModeEngine(settings, memory=pipeline.memory)

    async def _resume_run(eng, rid):
        try:
            return await eng.resume(rid)
        except Exception as exc:
            logger.error(f"[SELF MODE] Resume failed for {rid}: {exc}")
            return None

    task = asyncio.create_task(_resume_run(engine, run_id))
    request.app.state.self_mode_tasks[run_id] = task

    logger.info(
        f"[SELF MODE] Resuming run {run_id} from "
        f"step={db_record.get('current_step')}"
    )
    return {
        "run_id": run_id,
        "status": "resuming",
        "from_step": db_record.get("current_step"),
        "previous_status": status,
    }


@app.get("/v1/ears/status")
async def ears_status():
    """Check if the Ears sidecar is running."""
    ears_url = settings.ears_health_url
    try:
        resp = requests.get(ears_url, timeout=3)
        if resp.status_code == 200:
            return {"ears": "online", **resp.json()}
        return {"ears": "unhealthy", "status_code": resp.status_code}
    except Exception:
        return {"ears": "offline", "detail": "Ears health endpoint unreachable"}


# ---- Models endpoint (satisfies OpenAI client) ----
@app.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [
            {"id": "claude-sonnet", "object": "model", "created": 0, "owned_by": "champ-v3-brain"},
            {"id": "gemini-flash", "object": "model", "created": 0, "owned_by": "champ-v3-brain"},
            {"id": "gpt-4o", "object": "model", "created": 0, "owned_by": "champ-v3-brain"},
        ],
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "brain.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        log_level=settings.log_level.lower(),
    )
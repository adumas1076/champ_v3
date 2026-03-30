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
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import requests

from fastapi import FastAPI, Request, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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


# ---- File Upload & Processing (Brick 10) ----

# In-memory file cache: file_id -> FileProcessResult
_file_cache: dict = {}


@app.post("/v1/upload")
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    message: str = Form(default=""),
):
    """
    Upload a file for processing. Extracts content based on file type.
    Returns extracted text, metadata, and a file_id for use in chat messages.

    Supports: PDF, DOCX, PPTX, XLSX, CSV, images, audio, video, archives,
    email, HTML, code files, JSON, YAML, XML, TOML, Parquet, SQLite, and more.
    """
    from brain.file_processor import process_file
    from uuid import uuid4

    file_bytes = await file.read()
    filename = file.filename or "unknown"
    content_type = file.content_type

    result = await process_file(file_bytes, filename, content_type)

    # Store in cache with an ID
    file_id = f"file-{uuid4().hex[:8]}"
    _file_cache[file_id] = result

    logger.info(
        f"[UPLOAD] {filename} -> {result.file_type} | "
        f"{len(result.text)} chars | file_id={file_id}"
    )

    response = {
        "file_id": file_id,
        "filename": filename,
        "file_type": result.file_type,
        "text_length": len(result.text),
        "text_preview": result.text[:500],
        "metadata": result.metadata,
        "has_image": result.image_b64 is not None,
    }

    # If a message was included, run it through the chat pipeline with the file content
    if message.strip():
        pipeline: BrainPipeline = request.app.state.pipeline

        # Build message with file context
        file_context = f"[Uploaded file: {filename}]\n\n{result.text[:10000]}"

        if result.image_b64 and result.mime_type:
            # For images, send as multimodal message to use vision model
            messages_content = [
                {"type": "text", "text": f"{message}\n\n{file_context}"},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{result.mime_type};base64,{result.image_b64}"
                    },
                },
            ]
            chat_messages = [{"role": "user", "content": messages_content}]
            model = "gemini-flash"  # Route images to vision model
        else:
            chat_messages = [
                {"role": "user", "content": f"{message}\n\n{file_context}"}
            ]
            model = "claude-sonnet"

        from brain.models import ChatCompletionRequest, ChatMessage
        chat_request = ChatCompletionRequest(
            model=model,
            messages=[ChatMessage(**m) for m in chat_messages],
        )
        chat_response = await pipeline.handle_request(chat_request)
        response["chat_response"] = chat_response.model_dump()

    return JSONResponse(content=response)


@app.get("/v1/files/{file_id}")
async def get_file(file_id: str):
    """Retrieve processed file content by file_id."""
    if file_id not in _file_cache:
        return JSONResponse(
            status_code=404,
            content={"error": f"File {file_id} not found"},
        )

    result = _file_cache[file_id]
    return JSONResponse(content=result.to_dict())


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


# ---- Memory Read Endpoints (for Frontend) ----

@app.get("/v1/memory/profile")
async def get_memory_profile(request: Request, user_id: str = "anthony"):
    """Get all profile entries for a user."""
    pipeline: BrainPipeline = request.app.state.pipeline
    if not pipeline.memory._client:
        return {"entries": [], "count": 0}

    try:
        result = await pipeline.memory._client.table("mem_profile").select(
            "key, value, category, confidence, updated_at"
        ).eq("user_id", user_id).order("updated_at", desc=True).execute()
        entries = result.data or []
        return {"entries": entries, "count": len(entries)}
    except Exception as e:
        logger.error(f"[MEMORY] Profile fetch failed: {e}")
        return {"entries": [], "count": 0, "error": str(e)}


@app.get("/v1/memory/lessons")
async def get_memory_lessons(request: Request, user_id: str = "anthony"):
    """Get all lessons for a user."""
    pipeline: BrainPipeline = request.app.state.pipeline
    if not pipeline.memory._client:
        return {"entries": [], "count": 0}

    try:
        result = await pipeline.memory._client.table("mem_lessons").select(
            "id, lesson, tags, status, times_seen, created_at"
        ).eq("user_id", user_id).order("created_at", desc=True).execute()
        entries = result.data or []
        return {"entries": entries, "count": len(entries)}
    except Exception as e:
        logger.error(f"[MEMORY] Lessons fetch failed: {e}")
        return {"entries": [], "count": 0, "error": str(e)}


@app.get("/v1/memory/healing")
async def get_memory_healing(request: Request, user_id: str = "anthony"):
    """Get all healing records for a user."""
    pipeline: BrainPipeline = request.app.state.pipeline
    if not pipeline.memory._client:
        return {"entries": [], "count": 0}

    try:
        result = await pipeline.memory._client.table("mem_healing").select(
            "id, error_type, severity, trigger_context, prevention_rule, resolved, created_at"
        ).eq("user_id", user_id).order("created_at", desc=True).execute()
        entries = result.data or []
        return {"entries": entries, "count": len(entries)}
    except Exception as e:
        logger.error(f"[MEMORY] Healing fetch failed: {e}")
        return {"entries": [], "count": 0, "error": str(e)}


@app.get("/v1/conversations")
async def get_conversations(request: Request, limit: int = 20):
    """Get recent conversations."""
    pipeline: BrainPipeline = request.app.state.pipeline
    if not pipeline.memory._client:
        return {"conversations": [], "count": 0}

    try:
        result = await pipeline.memory._client.table("conversations").select(
            "id, channel, started_at, ended_at"
        ).order("started_at", desc=True).limit(limit).execute()
        conversations = result.data or []
        return {"conversations": conversations, "count": len(conversations)}
    except Exception as e:
        logger.error(f"[MEMORY] Conversations fetch failed: {e}")
        return {"conversations": [], "count": 0, "error": str(e)}


@app.get("/v1/conversations/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: str, request: Request, limit: int = 50
):
    """Get messages from a specific conversation."""
    pipeline: BrainPipeline = request.app.state.pipeline
    if not pipeline.memory._client:
        return {"messages": [], "count": 0}

    try:
        result = await pipeline.memory._client.table("messages").select(
            "id, role, content, mode, model_used, created_at"
        ).eq(
            "conversation_id", conversation_id
        ).order("created_at", desc=False).limit(limit).execute()
        messages = result.data or []
        return {"messages": messages, "count": len(messages)}
    except Exception as e:
        logger.error(f"[MEMORY] Messages fetch failed: {e}")
        return {"messages": [], "count": 0, "error": str(e)}


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


# ---- LiveKit Dispatch & Token (Brick 9 — Frontend) ----

@app.post("/v1/token")
async def livekit_token(request: Request):
    """Generate a LiveKit token for the frontend to join a room."""
    from livekit.api import AccessToken, VideoGrants

    body = await request.json() if request.headers.get("content-length", "0") != "0" else {}

    identity = body.get("identity", f"user-{os.urandom(4).hex()}")
    name = body.get("name", "User")
    room = body.get("room", "champ-room")

    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")

    if not api_key or not api_secret:
        return JSONResponse(
            status_code=500,
            content={"error": "LiveKit credentials not configured"},
        )

    token = (
        AccessToken(api_key=api_key, api_secret=api_secret)
        .with_identity(identity)
        .with_name(name)
        .with_grants(VideoGrants(room_join=True, room=room))
    )

    jwt = token.to_jwt()
    logger.info(f"[TOKEN] Generated for {identity} in room {room}")

    return {
        "token": jwt,
        "identity": identity,
        "room": room,
        "serverUrl": os.getenv("LIVEKIT_URL", ""),
    }


@app.post("/v1/dispatch")
async def livekit_dispatch(request: Request):
    """Dispatch the CHAMP voice agent to a LiveKit room."""
    from livekit.api import LiveKitAPI
    from livekit.api.agent_dispatch_service import CreateAgentDispatchRequest

    body = await request.json() if request.headers.get("content-length", "0") != "0" else {}

    room = body.get("room", "champ-room")
    agent_name = body.get("agent", "champ")

    livekit_url = os.getenv("LIVEKIT_URL")
    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")

    if not all([livekit_url, api_key, api_secret]):
        return JSONResponse(
            status_code=500,
            content={"error": "LiveKit credentials not configured"},
        )

    try:
        api = LiveKitAPI(url=livekit_url, api_key=api_key, api_secret=api_secret)
        req = CreateAgentDispatchRequest(room=room, agent_name=agent_name)
        dispatch = await api.agent_dispatch.create_dispatch(req)
        await api.aclose()

        logger.info(f"[DISPATCH] Agent '{agent_name}' dispatched to room '{room}'")

        return {
            "success": True,
            "room": room,
            "agent": agent_name,
            "dispatch_id": dispatch.id if hasattr(dispatch, "id") else None,
        }

    except Exception as e:
        logger.error(f"[DISPATCH] Failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)},
        )


# ---- AIOSCP Discovery Endpoints ----

@app.get("/v1/aioscp/operators")
async def aioscp_list_operators():
    """List all registered operators with their AIOSCP manifests."""
    from operators.aioscp_bridge import generate_manifest, get_os_capabilities
    from operators.registry import registry
    from dataclasses import asdict

    operators = []
    for name in registry.list_operators():
        manifest = registry.get_manifest(name)
        if manifest:
            m = asdict(manifest)
            # Clean up handler references (not serializable)
            for cap in m.get("capabilities", []):
                cap.pop("handler", None)
            operators.append(m)

    return {"operators": operators, "count": len(operators)}


@app.get("/v1/aioscp/operators/{operator_name}/capabilities")
async def aioscp_operator_capabilities(operator_name: str):
    """Get AIOSCP capabilities for a specific operator."""
    from operators.registry import registry
    from dataclasses import asdict

    caps = registry.get_capabilities(operator_name)
    if not caps:
        return JSONResponse(
            status_code=404,
            content={"error": f"Operator '{operator_name}' not found"},
        )

    result = []
    for cap in caps:
        c = asdict(cap)
        c.pop("handler", None)
        result.append(c)

    return {"operator": operator_name, "capabilities": result, "count": len(result)}


@app.post("/v1/aioscp/estimate")
async def aioscp_estimate_cost(request: Request):
    """
    Estimate cost before executing a task.
    Pass a list of capability IDs that would be used.

    Example: POST /v1/aioscp/estimate
    {"capabilities": ["browse_url", "analyze_screen", "ask_brain"]}
    """
    from operators.registry import registry

    body = await request.json()
    capability_ids = body.get("capabilities", [])

    if not capability_ids:
        return JSONResponse(
            status_code=400,
            content={"error": "Missing 'capabilities' list"},
        )

    estimate = registry.estimate_task_cost(capability_ids)

    return {
        "capabilities": capability_ids,
        "estimated_cost": estimate,
        "count": len(capability_ids),
    }


# ---- Remote Hands WebSocket (Local Agent Connection) ----

@app.websocket("/ws/hands")
async def hands_websocket(ws: WebSocket):
    """
    WebSocket endpoint for the Local Hands Agent.
    The local agent connects here and receives desktop/browser commands
    from the cloud Brain, executes them locally, and sends results back.
    """
    from hands.remote import set_agent_connection, clear_agent_connection, handle_agent_response

    await ws.accept()
    set_agent_connection(ws)
    logger.info("[HANDS WS] Local agent connected")

    try:
        while True:
            data = await ws.receive_text()
            try:
                parsed = json.loads(data)
                handle_agent_response(parsed)
            except json.JSONDecodeError:
                logger.error(f"[HANDS WS] Invalid JSON from agent: {data[:100]}")
    except WebSocketDisconnect:
        logger.info("[HANDS WS] Local agent disconnected")
    except Exception as e:
        logger.error(f"[HANDS WS] Error: {e}")
    finally:
        clear_agent_connection()


@app.get("/v1/hands/status")
async def hands_status():
    """Check if a local hands agent is connected."""
    from hands.router import get_hands_status
    return get_hands_status()


@app.post("/v1/hands/execute")
async def hands_execute(request: Request):
    """Proxy desktop/browser commands to the connected local agent.
    Used by the Hetzner voice agent to reach the user's desktop."""
    from hands.remote import _send_command, is_agent_connected

    if not is_agent_connected():
        return JSONResponse(
            status_code=503,
            content={"ok": False, "error": "No local hands agent connected"},
        )

    body = await request.json()
    command = body.get("command", "")
    args = body.get("args", {})
    timeout = body.get("timeout", 60.0)

    result = await _send_command(command, args, timeout=timeout)
    return result


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "brain.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        log_level=settings.log_level.lower(),
    )
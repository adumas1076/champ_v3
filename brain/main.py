# ============================================
# CHAMP V3 — Brain Entry Point
# Phase 2: THE BRAIN
# FastAPI server that wires persona + mode
# detection + LiteLLM proxy together.
# ============================================
# "Built to build. Born to create."

import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

from brain.config import load_settings
from brain.models import ChatCompletionRequest
from brain.pipeline import BrainPipeline
from mind.learning import LearningLoop

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
    logger.info(
        f"CHAMP V3 Brain ready on port {settings.port} | "
        f"LiteLLM upstream: {settings.litellm_base_url}"
    )
    yield
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
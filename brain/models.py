# ============================================
# CHAMP V3 — Data Models
# OpenAI-compatible types for request/response
# ============================================

from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Optional, Union

from pydantic import BaseModel, Field


# --- Output Modes (from persona V1.6.1) ---
class OutputMode(str, Enum):
    VIBE = "vibe"
    BUILD = "build"
    SPEC = "spec"


# --- OpenAI-Compatible Request ---
class ChatMessage(BaseModel):
    model_config = {"extra": "allow"}

    role: str
    content: Optional[Union[str, list]] = None


class ChatCompletionRequest(BaseModel):
    model_config = {"extra": "allow"}

    model: str = "claude-sonnet"
    messages: list[ChatMessage]
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    stream: bool = False
    top_p: Optional[float] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    stop: Optional[Union[str, list[str]]] = None
    user: Optional[str] = None


# --- OpenAI-Compatible Response ---
class Choice(BaseModel):
    index: int = 0
    message: ChatMessage
    finish_reason: Optional[str] = "stop"


class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionResponse(BaseModel):
    id: str = Field(
        default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex[:12]}"
    )
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: list[Choice]
    usage: Usage = Field(default_factory=Usage)
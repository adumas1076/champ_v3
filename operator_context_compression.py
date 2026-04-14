# ============================================
# Cocreatiq V1 — Context Compression
# Summarize long conversations to stay in context window
# Pattern: Hermes structured summaries (Goal/Progress/Decisions)
# ============================================

import logging
import os
import json
from typing import Optional

logger = logging.getLogger(__name__)


def compress_context(transcript_text: str, max_chars: int = 2000) -> str:
    """
    Compress a long transcript into a structured summary.
    Used when conversation exceeds context window.

    Format: Goal / Progress / Decisions / Open Items
    """
    if len(transcript_text) <= max_chars:
        return transcript_text  # No compression needed

    try:
        import requests
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            # Fallback: just take last N chars
            return f"[COMPRESSED — showing last {max_chars} chars]\n{transcript_text[-max_chars:]}"

        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": """Compress this conversation transcript into a structured summary.
Use this EXACT format:

GOAL: What the user is trying to accomplish (1 sentence)
PROGRESS: What has been done so far (2-3 bullets)
DECISIONS: Key decisions made (2-3 bullets)
OPEN ITEMS: What still needs to be done (2-3 bullets)
LAST EXCHANGE: The most recent user message and agent response (verbatim, last 2 messages)

Keep it under 500 words. Preserve critical details. Drop filler."""},
                    {"role": "user", "content": transcript_text}
                ],
                "temperature": 0.2,
                "max_tokens": 800,
            },
            timeout=15,
        )
        response.raise_for_status()
        compressed = response.json()["choices"][0]["message"]["content"].strip()
        logger.info(f"[COMPRESS] {len(transcript_text)} chars → {len(compressed)} chars")
        return compressed

    except Exception as e:
        logger.warning(f"[COMPRESS] Failed (non-fatal): {e}")
        return f"[COMPRESSED — showing last {max_chars} chars]\n{transcript_text[-max_chars:]}"


def should_compress(message_count: int, transcript_length: int, threshold_messages: int = 50, threshold_chars: int = 15000) -> bool:
    """Check if compression is needed based on conversation size."""
    return message_count >= threshold_messages or transcript_length >= threshold_chars


def build_compressed_context(
    transcript_text: str,
    message_count: int,
    operator_name: str,
) -> Optional[str]:
    """
    Build compressed context if the conversation is long enough.
    Returns compressed summary or None if not needed.
    """
    if not should_compress(message_count, len(transcript_text)):
        return None

    logger.info(f"[COMPRESS] Compressing {operator_name} context: {message_count} messages, {len(transcript_text)} chars")
    return compress_context(transcript_text)
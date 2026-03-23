# ============================================
# CHAMP V3 — Context Builder Unit Tests
# Run: python -m pytest tests/test_context_builder.py -v
# ============================================

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from brain.context_builder import ContextBuilder
from brain.models import ChatMessage, OutputMode


builder = ContextBuilder()
FAKE_PERSONA = "You are Champ. Be real."


def test_builds_vibe_context():
    messages = [ChatMessage(role="user", content="What's good?")]
    result = builder.build(messages, FAKE_PERSONA, OutputMode.VIBE)

    assert result[0].role == "system"
    assert "VIBE" in result[0].content
    assert "2-6 sentences" in result[0].content
    assert result[1].role == "user"


def test_builds_build_context():
    messages = [ChatMessage(role="user", content="Let's build something")]
    result = builder.build(messages, FAKE_PERSONA, OutputMode.BUILD)

    assert "BUILD" in result[0].content
    assert "headers and steps" in result[0].content


def test_builds_spec_context():
    messages = [ChatMessage(role="user", content="Give me the code")]
    result = builder.build(messages, FAKE_PERSONA, OutputMode.SPEC)

    assert "SPEC" in result[0].content
    assert "copy/paste" in result[0].content


def test_strips_existing_system_messages():
    messages = [
        ChatMessage(role="system", content="Old system prompt"),
        ChatMessage(role="user", content="Hey"),
    ]
    result = builder.build(messages, FAKE_PERSONA, OutputMode.VIBE)

    system_msgs = [m for m in result if m.role == "system"]
    assert len(system_msgs) == 1
    assert FAKE_PERSONA in system_msgs[0].content


def test_preserves_conversation_order():
    messages = [
        ChatMessage(role="user", content="First message"),
        ChatMessage(role="assistant", content="First response"),
        ChatMessage(role="user", content="Second message"),
    ]
    result = builder.build(messages, FAKE_PERSONA, OutputMode.VIBE)

    assert len(result) == 4  # system + 3 conversation
    assert result[1].content == "First message"
    assert result[2].content == "First response"
    assert result[3].content == "Second message"


def test_compaction_triggers_on_large_context():
    """Should drop older messages when context exceeds 80% of window."""
    # Create a conversation with lots of long messages
    messages = []
    for i in range(100):
        messages.append(ChatMessage(role="user", content=f"Message {i}: " + "x" * 2000))
        messages.append(ChatMessage(role="assistant", content=f"Response {i}: " + "y" * 2000))

    # Use a small context window model to trigger compaction
    result = builder.build(
        messages, FAKE_PERSONA, OutputMode.VIBE, model="deepseek"
    )

    # Should have fewer messages than original (200 messages → compacted)
    non_system = [m for m in result if m.role != "system" or "COMPACTED" in (m.content or "")]
    assert len(non_system) < 200, "Should have dropped older messages"

    # Should have compaction notice
    compaction_msgs = [m for m in result if "COMPACTED" in (m.content or "")]
    assert len(compaction_msgs) == 1, "Should include compaction notice"

    # Most recent message should be preserved
    assert result[-1].content.startswith("Response 99")


def test_no_compaction_on_short_context():
    """Should NOT compact when context is small."""
    messages = [
        ChatMessage(role="user", content="Hey"),
        ChatMessage(role="assistant", content="What's good, champ"),
    ]
    result = builder.build(messages, FAKE_PERSONA, OutputMode.VIBE)

    assert len(result) == 3  # system + 2 conversation
    compaction_msgs = [m for m in result if "COMPACTED" in (m.content or "")]
    assert len(compaction_msgs) == 0


def test_compaction_keeps_minimum_messages():
    """Should keep at least MIN_MESSAGES_AFTER_COMPACT messages."""
    from brain.context_builder import MIN_MESSAGES_AFTER_COMPACT

    messages = []
    for i in range(50):
        messages.append(ChatMessage(role="user", content=f"Msg {i}: " + "x" * 5000))

    result = builder.build(
        messages, FAKE_PERSONA, OutputMode.VIBE, model="deepseek"
    )

    non_system = [m for m in result if m.role != "system" or "COMPACTED" in (m.content or "")]
    # Subtract 1 for compaction notice
    compaction_notices = [m for m in non_system if "COMPACTED" in (m.content or "")]
    actual_msgs = len(non_system) - len(compaction_notices)
    assert actual_msgs >= MIN_MESSAGES_AFTER_COMPACT


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
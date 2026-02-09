# ============================================
# CHAMP V3 — Healing Loop Tests
# Brick 6 Step 4: Unit tests for HealingLoop
# Run: python -m pytest tests/test_healing.py -v
# ============================================

from brain.models import OutputMode
from mind.healing import HealingLoop


loop = HealingLoop()


# ---- Test 1: Clean message, no issues ----

def test_no_issues_clean_message():
    """Normal message → empty issues, no override."""
    result = loop.detect(
        user_message="How's the weather today?",
        mode=OutputMode.VIBE,
        recent_messages=[],
    )
    assert result.issues == []
    assert result.mode_override is None
    assert result.warning_text == ""


# ---- Test 2: Wrong mode — code request in VIBE ----

def test_wrong_mode_code_request_in_vibe():
    """"give me the code" + VIBE → SPEC override."""
    result = loop.detect(
        user_message="give me the code for a Python hello world",
        mode=OutputMode.VIBE,
        recent_messages=[],
    )
    assert len(result.issues) == 1
    assert result.issues[0]["type"] == "wrong_mode"
    assert result.mode_override == OutputMode.SPEC


# ---- Test 3: Wrong mode — explain in SPEC ----

def test_wrong_mode_explain_in_spec():
    """"explain this" + SPEC → VIBE override."""
    result = loop.detect(
        user_message="explain how this works",
        mode=OutputMode.SPEC,
        recent_messages=[],
    )
    assert len(result.issues) == 1
    assert result.issues[0]["type"] == "wrong_mode"
    assert result.mode_override == OutputMode.VIBE


# ---- Test 4: Looping detected ----

def test_looping_detected():
    """2 identical assistant messages → looping flagged."""
    recent = [
        {"role": "assistant", "content": "Here is the answer to your question about Python lists."},
        {"role": "user", "content": "ok"},
        {"role": "assistant", "content": "Here is the answer to your question about Python lists."},
    ]
    result = loop.detect(
        user_message="ok",
        mode=OutputMode.VIBE,
        recent_messages=recent,
    )
    looping_issues = [i for i in result.issues if i["type"] == "looping"]
    assert len(looping_issues) == 1
    assert looping_issues[0]["severity"] == "high"


# ---- Test 5: Looping NOT triggered for different messages ----

def test_looping_not_triggered_different():
    """Different assistant messages → no looping."""
    recent = [
        {"role": "assistant", "content": "Python uses indentation for blocks."},
        {"role": "user", "content": "what about JavaScript?"},
        {"role": "assistant", "content": "JavaScript uses curly braces for blocks."},
    ]
    result = loop.detect(
        user_message="cool",
        mode=OutputMode.VIBE,
        recent_messages=recent,
    )
    looping_issues = [i for i in result.issues if i["type"] == "looping"]
    assert len(looping_issues) == 0


# ---- Test 6: Tool failure detected ----

def test_tool_failure_detected():
    """"it didn't work" → tool_failure flagged."""
    result = loop.detect(
        user_message="it didn't work, I got an error",
        mode=OutputMode.VIBE,
        recent_messages=[],
    )
    tool_issues = [i for i in result.issues if i["type"] == "tool_failure"]
    assert len(tool_issues) == 1
    assert tool_issues[0]["severity"] == "medium"


# ---- Test 7: User friction detected ----

def test_user_friction_detected():
    """"you're spinning" → user_friction flagged."""
    result = loop.detect(
        user_message="you're spinning, that's not what I asked",
        mode=OutputMode.VIBE,
        recent_messages=[],
    )
    friction_issues = [i for i in result.issues if i["type"] == "user_friction"]
    assert len(friction_issues) >= 1
    assert friction_issues[0]["severity"] == "high"


# ---- Test 8: Warning text generated ----

def test_warning_text_generated():
    """Issues present → warning_text is non-empty with [HEALING WARNING]."""
    result = loop.detect(
        user_message="give me the code for a web scraper",
        mode=OutputMode.VIBE,
        recent_messages=[],
    )
    assert result.warning_text != ""
    assert "[HEALING WARNING]" in result.warning_text
    assert "wrong_mode" in result.warning_text

# ============================================
# CHAMP V3 — Brick 6 Gate Test (Mind)
# Tests Learning + Healing end-to-end
# Run: python gate_test_mind.py
# ============================================

import json
from unittest.mock import MagicMock, AsyncMock, patch

import asyncio

from brain.models import OutputMode
from mind.learning import LearningLoop
from mind.healing import HealingLoop


async def run_gate_tests():
    print("=" * 60)
    print("CHAMP V3 — BRICK 6 GATE TEST (MIND)")
    print("Built to build. Born to create.")
    print("=" * 60)

    passed = 0
    failed = 0

    # ---- Test 1: Learning extraction prompt sent ----
    print("\n[1/5] Learning: 5-message transcript -> extraction prompt sent...")
    try:
        settings = MagicMock()
        settings.litellm_base_url = "http://127.0.0.1:4000/v1"
        settings.litellm_api_key = "test"
        settings.default_model = "claude-sonnet"

        loop = LearningLoop(settings)
        memory = AsyncMock()
        memory.get_recent_messages = AsyncMock(return_value=[
            {"role": "user", "content": "I prefer dark mode"},
            {"role": "assistant", "content": "Noted! Dark mode it is."},
            {"role": "user", "content": "Also I like using Puppeteer"},
            {"role": "assistant", "content": "Great choice for browser automation."},
            {"role": "user", "content": "Thanks Champ"},
        ])
        memory.upsert_profile = AsyncMock()
        memory.increment_lesson = AsyncMock()
        memory.insert_lesson = AsyncMock()

        extraction = {
            "profile_updates": [
                {"key": "theme", "value": "dark mode", "category": "ui", "confidence": "high"}
            ],
            "lesson_matches": [],
            "new_lessons": [],
        }
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": json.dumps(extraction)}}]
        }

        with patch("mind.learning.requests.post", return_value=mock_resp) as mock_post:
            await loop.capture("conv-123", memory)
            if mock_post.called:
                prompt = mock_post.call_args[1]["json"]["messages"][0]["content"]
                if "dark mode" in prompt and "Puppeteer" in prompt:
                    print("  PASSED: Extraction prompt contains transcript")
                    passed += 1
                else:
                    print(f"  FAILED: Prompt missing transcript content")
                    failed += 1
            else:
                print("  FAILED: LLM not called")
                failed += 1
    except Exception as e:
        print(f"  FAILED: {e}")
        failed += 1

    # ---- Test 2: Learning profile upsert ----
    print("\n[2/5] Learning: profile upsert called with extracted data...")
    try:
        if memory.upsert_profile.called:
            call_kwargs = memory.upsert_profile.call_args[1]
            if call_kwargs["key"] == "theme" and call_kwargs["value"] == "dark mode":
                print(f"  PASSED: Profile upserted: {call_kwargs}")
                passed += 1
            else:
                print(f"  FAILED: Wrong upsert args: {call_kwargs}")
                failed += 1
        else:
            print("  FAILED: upsert_profile not called")
            failed += 1
    except Exception as e:
        print(f"  FAILED: {e}")
        failed += 1

    # ---- Test 3: Healing wrong mode detection ----
    print('\n[3/5] Healing: "give me the code" + VIBE -> SPEC override...')
    try:
        healer = HealingLoop()
        result = healer.detect(
            user_message="give me the code for a Python web scraper",
            mode=OutputMode.VIBE,
            recent_messages=[],
        )
        if result.mode_override == OutputMode.SPEC:
            print(f"  PASSED: Mode override -> SPEC")
            passed += 1
        else:
            print(f"  FAILED: Mode override = {result.mode_override}")
            failed += 1
    except Exception as e:
        print(f"  FAILED: {e}")
        failed += 1

    # ---- Test 4: Healing looping detection ----
    print("\n[4/5] Healing: 2 identical assistant messages -> looping...")
    try:
        result = healer.detect(
            user_message="ok",
            mode=OutputMode.VIBE,
            recent_messages=[
                {"role": "assistant", "content": "Python is a great language for scripting."},
                {"role": "user", "content": "ok"},
                {"role": "assistant", "content": "Python is a great language for scripting."},
            ],
        )
        looping = [i for i in result.issues if i["type"] == "looping"]
        if looping:
            print(f"  PASSED: Looping detected ({looping[0]['severity']})")
            passed += 1
        else:
            print(f"  FAILED: Looping not detected")
            failed += 1
    except Exception as e:
        print(f"  FAILED: {e}")
        failed += 1

    # ---- Test 5: Healing user friction detection ----
    print('\n[5/5] Healing: "you\'re spinning" -> user_friction...')
    try:
        result = healer.detect(
            user_message="you're spinning, that's not what I asked",
            mode=OutputMode.VIBE,
            recent_messages=[],
        )
        friction = [i for i in result.issues if i["type"] == "user_friction"]
        if friction:
            print(f"  PASSED: User friction detected ({friction[0]['severity']})")
            passed += 1
        else:
            print(f"  FAILED: User friction not detected")
            failed += 1
    except Exception as e:
        print(f"  FAILED: {e}")
        failed += 1

    # Summary
    print("\n" + "=" * 60)
    print(f"BRICK 6 GATE TEST: {passed}/5 passed, {failed}/5 failed")
    if failed == 0:
        print("\nBRICK 6 GATE: PASSED")
        print("Mind is wired. Champ can LEARN and HEAL now.")
    else:
        print("\nBRICK 6 GATE: NEEDS WORK")
    print("=" * 60)

    return failed


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(run_gate_tests()))

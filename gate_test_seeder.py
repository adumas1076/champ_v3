# ============================================
# CHAMP V3 -- Brick 6.5 Gate Test (Memory Seeder)
# Tests that ChatGPT extraction -> Supabase seed
# produces correct profile + lesson entries
# Run: python gate_test_seeder.py
# ============================================

import json
import asyncio
from unittest.mock import AsyncMock

from mind.memory_seeder import (
    load_extract,
    build_profile_entries,
    build_lesson_entries,
    seed_memory,
)


async def run_gate_tests():
    print("=" * 60)
    print("CHAMP V3 -- BRICK 6.5 GATE TEST (MEMORY SEEDER)")
    print("628 conversations -> foundational memory")
    print("=" * 60)

    passed = 0
    failed = 0

    # Load real extraction file
    data = load_extract()

    # ---- Test 1: Profile entries generated ----
    print("\n[1/6] Profile entries from real extraction data...")
    try:
        profiles = build_profile_entries(data)
        keys = [p["key"] for p in profiles]
        required = ["history_depth", "businesses", "tech_stack", "greeting_style"]
        missing = [k for k in required if k not in keys]
        if not missing and len(profiles) >= 5:
            print(f"  PASSED: {len(profiles)} profile entries, all required keys present")
            passed += 1
        else:
            print(f"  FAILED: Missing keys: {missing}, total: {len(profiles)}")
            failed += 1
    except Exception as e:
        print(f"  FAILED: {e}")
        failed += 1

    # ---- Test 2: History depth is accurate ----
    print("\n[2/6] History depth matches extraction stats...")
    try:
        history = [p for p in profiles if p["key"] == "history_depth"][0]
        if "628" in history["value"] and "52,676" in history["value"]:
            print(f"  PASSED: {history['value']}")
            passed += 1
        else:
            print(f"  FAILED: Value = {history['value']}")
            failed += 1
    except Exception as e:
        print(f"  FAILED: {e}")
        failed += 1

    # ---- Test 3: Lesson entries from deep sessions ----
    print("\n[3/6] Lessons from deep sessions (100+ messages)...")
    try:
        lessons = build_lesson_entries(data)
        deep = [l for l in lessons if l["lesson"].startswith("Deep session:")]
        deep_sessions = data["key_conversations"]["deepest_sessions"]
        expected = len([s for s in deep_sessions if s["message_count"] >= 100])
        if len(deep) == expected:
            print(f"  PASSED: {len(deep)} deep session lessons (expected {expected})")
            passed += 1
        else:
            print(f"  FAILED: Got {len(deep)} deep session lessons, expected {expected}")
            failed += 1
    except Exception as e:
        print(f"  FAILED: {e}")
        failed += 1

    # ---- Test 4: Voice pattern lessons from signature exchanges ----
    print("\n[4/6] Voice pattern lessons from signature exchanges...")
    try:
        voice = [l for l in lessons if "Voice pattern" in l["lesson"]]
        exchanges = data.get("signature_exchanges", [])
        unique_convos = len(set(e["conversation"] for e in exchanges))
        if len(voice) == unique_convos:
            print(f"  PASSED: {len(voice)} voice patterns from {unique_convos} conversations")
            passed += 1
        else:
            print(f"  FAILED: Got {len(voice)} voice patterns, expected {unique_convos}")
            failed += 1
    except Exception as e:
        print(f"  FAILED: {e}")
        failed += 1

    # ---- Test 5: Agent roster detected ----
    print("\n[5/6] Agent roster from key conversations...")
    try:
        roster = [p for p in profiles if p["key"] == "agent_roster"]
        if roster:
            agents = roster[0]["value"]
            detected = []
            for name in ["Genesis", "Billy", "ARIA"]:
                if name in agents:
                    detected.append(name)
            if len(detected) >= 2:
                print(f"  PASSED: Roster includes {', '.join(detected)}")
                passed += 1
            else:
                print(f"  FAILED: Only found {detected} in roster: {agents}")
                failed += 1
        else:
            print("  FAILED: No agent_roster entry")
            failed += 1
    except Exception as e:
        print(f"  FAILED: {e}")
        failed += 1

    # ---- Test 6: seed_memory writes to mock Supabase ----
    print("\n[6/6] seed_memory writes profiles + lessons to memory...")
    try:
        memory = AsyncMock()
        memory.upsert_profile = AsyncMock()
        memory.insert_lesson = AsyncMock()

        summary = await seed_memory(memory, data)
        if (summary["profiles"] > 0
                and summary["lessons"] > 0
                and memory.upsert_profile.called
                and memory.insert_lesson.called):
            print(f"  PASSED: {summary['profiles']} profiles, {summary['lessons']} lessons written")
            passed += 1
        else:
            print(f"  FAILED: summary={summary}")
            failed += 1
    except Exception as e:
        print(f"  FAILED: {e}")
        failed += 1

    # Summary
    print("\n" + "=" * 60)
    print(f"BRICK 6.5 GATE TEST: {passed}/6 passed, {failed}/6 failed")
    if failed == 0:
        print("\nBRICK 6.5 GATE: PASSED")
        print("Memory seeder ready. Champ's 628 sessions -> Supabase.")
    else:
        print("\nBRICK 6.5 GATE: NEEDS WORK")
    print("=" * 60)

    return failed


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(run_gate_tests()))

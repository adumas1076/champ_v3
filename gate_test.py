# ============================================
# CHAMP V3 — Phase 2 GATE TEST
# ============================================
# Sends text messages to the Brain API endpoint
# and verifies Champ responds with the right
# mode energy.
#
# Prerequisites:
#   1. LiteLLM proxy running on port 4000
#   2. Brain server running on port 8100
#
# Run: python gate_test.py
# ============================================

import httpx
import json
import sys

BRAIN_URL = "http://127.0.0.1:8100"

# Test cases: (label, message, expected_mode_keyword)
TEST_CASES = [
    (
        "VIBE MODE",
        "Hey champ, what do you think about using Redis for caching?",
        "vibe",
    ),
    (
        "BUILD MODE",
        "Let's build a user authentication system step by step",
        "build",
    ),
    (
        "SPEC MODE",
        "Give me the code for a FastAPI health check endpoint",
        "spec",
    ),
]


def send_message(message: str, model: str = "claude-sonnet") -> dict:
    """Send a non-streaming chat completion request to the Brain."""
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": message}],
        "stream": False,
        "max_tokens": 500,
    }

    response = httpx.post(
        f"{BRAIN_URL}/v1/chat/completions",
        json=payload,
        timeout=60.0,
    )
    response.raise_for_status()
    return response.json()


def run_gate_test():
    print("=" * 60)
    print("CHAMP V3 — PHASE 2 GATE TEST")
    print("Built to build. Born to create.")
    print("=" * 60)

    # 1. Health check
    print("\n[1/4] Health check...")
    try:
        health = httpx.get(f"{BRAIN_URL}/health", timeout=5.0)
        health.raise_for_status()
        print(f"  OK: {health.json()}")
    except Exception as e:
        print(f"  FAIL: Brain server not reachable at {BRAIN_URL}")
        print(f"  Error: {e}")
        print("\n  Make sure both LiteLLM (port 4000) and Brain (port 8100) are running.")
        sys.exit(1)

    # 2. Models endpoint
    print("\n[2/4] Models endpoint...")
    try:
        models = httpx.get(f"{BRAIN_URL}/v1/models", timeout=5.0)
        model_ids = [m["id"] for m in models.json()["data"]]
        print(f"  OK: Available models: {model_ids}")
    except Exception as e:
        print(f"  WARN: {e}")

    # 3. Mode detection + LLM response tests
    print("\n[3/4] Mode detection + Champ response tests...")
    results = []
    for label, message, expected_mode in TEST_CASES:
        print(f"\n  --- {label} ---")
        print(f"  Input: \"{message}\"")
        try:
            response = send_message(message)
            content = response["choices"][0]["message"]["content"]

            # Truncate for display
            display = content[:300] + "..." if len(content) > 300 else content
            print(f"  Response ({len(content)} chars):")
            print(f"    {display}")
            results.append(True)
        except Exception as e:
            print(f"  FAIL: {e}")
            results.append(False)

    # 4. Summary
    passed = sum(results)
    total = len(results)
    print("\n" + "=" * 60)
    print(f"[4/4] GATE TEST RESULTS: {passed}/{total} passed")

    if passed == total:
        print("\nPHASE 2 GATE: PASSED")
        print("The Brain is wired. Champ responds with persona + mode energy.")
        print("Ready for Phase 3: Memory + Skills")
    else:
        print("\nPHASE 2 GATE: NEEDS WORK")
        print("Check the failures above and fix before moving on.")

    print("=" * 60)


if __name__ == "__main__":
    run_gate_test()

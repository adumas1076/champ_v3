# ============================================
# CHAMP V3 — Brick 5 Bridge Test
# Tests Python-to-Node bridge in isolation
# Run: python hands/test_bridge.py
# ============================================

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hands.bridge import browse, take_screenshot, call_hands


async def run_tests():
    passed = 0
    failed = 0

    # Test 1: Browse example.com
    print("\n[1/4] Browse example.com...")
    result = await browse("https://example.com")
    if result.get("ok") and "Example Domain" in result.get("title", ""):
        print(f"  PASSED: title='{result['title']}'")
        passed += 1
    else:
        print(f"  FAILED: {result}")
        failed += 1

    # Test 2: Screenshot example.com
    print("\n[2/4] Screenshot example.com...")
    result = await take_screenshot("https://example.com")
    if result.get("ok") and result.get("path"):
        print(f"  PASSED: saved to {result['path']}")
        passed += 1
    else:
        print(f"  FAILED: {result}")
        failed += 1

    # Test 3: Unknown command (error handling)
    print("\n[3/4] Unknown command (should fail gracefully)...")
    result = await call_hands("nonexistent", {})
    if not result.get("ok"):
        print(f"  PASSED: correctly returned error")
        passed += 1
    else:
        print(f"  FAILED: should have errored")
        failed += 1

    # Test 4: Browse github.com (real site)
    print("\n[4/4] Browse github.com...")
    result = await browse("https://github.com")
    if result.get("ok") and "GitHub" in result.get("title", ""):
        print(f"  PASSED: title='{result['title']}' ({len(result.get('text', ''))} chars)")
        passed += 1
    else:
        print(f"  FAILED: {result}")
        failed += 1

    # Summary
    total = passed + failed
    print(f"\n{'=' * 55}")
    print(f"HANDS BRIDGE TEST: {passed}/{total} passed")
    if failed == 0:
        print("BRICK 5 BRIDGE GATE: PASSED")
    else:
        print("BRICK 5 BRIDGE GATE: NEEDS WORK")
    print(f"{'=' * 55}")

    return failed


if __name__ == "__main__":
    sys.exit(asyncio.run(run_tests()))

# ============================================
# CHAMP V3 — Brick 5 Full Gate Test (Hands)
# Tests all 5 tools end-to-end
# Run: python gate_test_hands.py
# ============================================

import asyncio
import sys


async def run_gate_tests():
    from tools import browse_url, take_screenshot, run_code, create_file

    print("=" * 60)
    print("CHAMP V3 — BRICK 5 GATE TEST (HANDS)")
    print("Built to build. Born to create.")
    print("=" * 60)

    passed = 0
    failed = 0

    class MockContext:
        pass
    ctx = MockContext()

    # Test 1: browse_url
    print("\n[1/5] browse_url('https://github.com')...")
    result = await browse_url(ctx, "https://github.com")
    if "GitHub" in result and "error" not in result.lower():
        print(f"  PASSED: {result[:100]}...")
        passed += 1
    else:
        print(f"  FAILED: {result[:200]}")
        failed += 1

    # Test 2: take_screenshot
    print("\n[2/5] take_screenshot('https://example.com')...")
    result = await take_screenshot(ctx, "https://example.com")
    if "saved" in result.lower() or "screenshot" in result.lower():
        print(f"  PASSED: {result}")
        passed += 1
    else:
        print(f"  FAILED: {result}")
        failed += 1

    # Test 3: run_code (Python)
    print('\n[3/5] run_code(\'print("Hello from Champ!")\', "python")...')
    result = await run_code(ctx, 'print("Hello from Champ!")', "python")
    if "Hello from Champ!" in result:
        print(f"  PASSED: {result}")
        passed += 1
    else:
        print(f"  FAILED: {result}")
        failed += 1

    # Test 4: create_file
    print("\n[4/5] create_file('hello.py', 'print(\"hello world\")')...")
    result = await create_file(ctx, "hello.py", 'print("hello world")')
    if "saved" in result.lower() or "hello.py" in result:
        print(f"  PASSED: {result}")
        passed += 1
    else:
        print(f"  FAILED: {result}")
        failed += 1

    # Test 5: run_code (JavaScript)
    print("\n[5/5] run_code('console.log(2+2)', 'javascript')...")
    result = await run_code(ctx, "console.log(2+2)", "javascript")
    if "4" in result:
        print(f"  PASSED: {result}")
        passed += 1
    else:
        print(f"  FAILED: {result}")
        failed += 1

    # Summary
    print("\n" + "=" * 60)
    print(f"BRICK 5 GATE TEST: {passed}/5 passed, {failed}/5 failed")
    if failed == 0:
        print("\nBRICK 5 GATE: PASSED")
        print("Hands are wired. Champ can DO things now.")
    else:
        print("\nBRICK 5 GATE: NEEDS WORK")
    print("=" * 60)

    return failed


if __name__ == "__main__":
    sys.exit(asyncio.run(run_gate_tests()))

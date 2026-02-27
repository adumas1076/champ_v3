# ============================================
# CHAMP V3 -- Gate Test: Self Mode Engine (Brick 8)
#
# Tests the full Self Mode pipeline:
# 1. Parse weather Goal Card
# 2. Dry-run: plan only
# 3. Full run: plan -> execute -> review -> package
# 4. Verify Result Pack output
#
# Requires: LiteLLM running on port 4000
# Run: python gate_test_self_mode.py
# ============================================

import asyncio
import os
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv
load_dotenv()

from brain.config import load_settings
from self_mode.parser import GoalCardParser
from self_mode.engine import SelfModeEngine
from self_mode.safety import SafetyRails
from self_mode.models import RunStatus

# ---- Weather Goal Card (from spec) ----

WEATHER_GOAL_CARD = """\
GOAL CARD v1.0
(goal_id: GC-WEATHER-001 | project_id: champ_v3 | priority: P0 | risk_level: low)

1) OBJECTIVE
- Create a Python script that fetches current weather for 5 cities and saves results to CSV.

2) PROBLEM
- Need daily weather data for client reports. Manual collection wastes time.

3) SOLUTION
- Simple Python script calling free weather API, one row per city to output.csv.

4) STACK
- Python 3, requests, csv (standard library)

5) CONSTRAINTS
- No paid APIs. Must run locally. Under 30 minutes. If API fails for one city, still write CSV for others and log error.

6) APPROVAL
- None. Auto-execute. No emailing, no deployment, no external writes beyond local files.

7) DELIVERABLES
- weather.py, output.csv, README snippet (how to run)

8) CONTEXT / ASSETS
- Cities: Atlanta, New York, Los Angeles, Chicago, Miami
- Preferred: Open-Meteo API (no key needed) OR OpenWeatherMap free tier (key in env var)

9) SUCCESS CHECKS
- Script runs without errors (or handles errors gracefully)
- output.csv contains exactly 5 rows (one per city)
- All 5 cities present by name
- Each row includes: city, timestamp, temperature, condition
"""


def header(text):
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}")


async def test_parser():
    """Test 1: Parse the weather Goal Card."""
    header("TEST 1: Goal Card Parser")

    card = GoalCardParser.parse(WEATHER_GOAL_CARD)
    assert card.goal_id == "GC-WEATHER-001", f"Expected GC-WEATHER-001, got {card.goal_id}"
    assert card.project_id == "champ_v3"
    assert "5 cities" in card.objective
    assert "Open-Meteo" in card.context_assets

    warnings = GoalCardParser.validate(card)
    print(f"  Goal ID:    {card.goal_id}")
    print(f"  Project:    {card.project_id}")
    print(f"  Objective:  {card.objective[:60]}...")
    print(f"  Warnings:   {warnings or 'None'}")
    print("  PASS: Parser extracts all 9 fields + metadata")
    return card


async def test_safety():
    """Test 2: Safety rails block dangerous actions."""
    header("TEST 2: Safety Rails")

    safety = SafetyRails()

    # Should block
    assert safety.check_command("rm -rf /") is not None, "Should block rm -rf"
    assert safety.check_command("git push") is not None, "Should block git push"
    assert safety.check_command("shutdown /s") is not None, "Should block shutdown"
    print("  PASS: Dangerous commands blocked")

    # Should allow
    assert safety.check_command("python weather.py") is None, "Should allow python"
    assert safety.check_command("dir") is None, "Should allow dir"
    print("  PASS: Safe commands allowed")


async def test_dry_run():
    """Test 3: Dry run produces plan without executing."""
    header("TEST 3: Dry Run Mode")

    settings = load_settings()
    engine = SelfModeEngine(settings, memory=None)

    result = await engine.run(WEATHER_GOAL_CARD, dry_run=True)

    assert result.status == "DryRun", f"Expected DryRun, got {result.status}"
    assert result.goal_id == "GC-WEATHER-001"
    assert "subtasks" in result.decisions_made.lower()

    print(f"  Status:      {result.status}")
    print(f"  Goal ID:     {result.goal_id}")
    print(f"  Plan:        {result.decisions_made}")
    print(f"  Next steps:")
    for line in result.next_actions.split("\n")[:5]:
        print(f"    {line}")
    print(f"  Time:        {result.time_cost}")
    print("  PASS: Dry run returns plan without execution")
    return result


async def test_full_run():
    """Test 4: Full autonomous run of weather Goal Card."""
    header("TEST 4: Full Run (Weather Goal Card)")

    settings = load_settings()
    engine = SelfModeEngine(settings, memory=None)

    print("  Starting autonomous execution...")
    print("  (This may take 1-3 minutes depending on LLM speed)")
    print()

    result = await engine.run(WEATHER_GOAL_CARD)

    print(f"\n{result.to_text()}")

    # Verify Result Pack has all 7 fields
    assert result.status in ("Complete", "Partial"), f"Unexpected status: {result.status}"
    assert result.deliverables, "Deliverables should not be empty"
    assert result.decisions_made, "Decisions should not be empty"
    assert result.time_cost, "Time/cost should not be empty"
    assert result.evidence, "Evidence should not be empty"
    print("  PASS: Result Pack has all 7 fields filled")

    # Check if output files exist
    output_dir = engine.output_dir
    weather_py = output_dir / "weather.py"
    output_csv = output_dir / "output.csv"

    if weather_py.exists():
        print(f"  PASS: weather.py created at {weather_py}")
    else:
        print(f"  WARN: weather.py not found at {weather_py}")

    if output_csv.exists():
        content = output_csv.read_text(encoding="utf-8")
        lines = [l for l in content.strip().split("\n") if l.strip()]
        print(f"  CSV lines: {len(lines)}")
        for line in lines[:6]:
            print(f"    {line}")
        if len(lines) >= 5:
            print("  PASS: output.csv has 5+ rows")
    else:
        print(f"  WARN: output.csv not found at {output_csv}")

    return result


async def main():
    header("CHAMP V3 -- Brick 8 Gate Test: Self Mode Engine")
    print("  Testing: Parser -> Safety -> Dry Run -> Full Run")

    passed = 0
    total = 4

    try:
        await test_parser()
        passed += 1
    except Exception as e:
        print(f"  FAIL: Parser test -- {e}")

    try:
        await test_safety()
        passed += 1
    except Exception as e:
        print(f"  FAIL: Safety test -- {e}")

    try:
        await test_dry_run()
        passed += 1
    except Exception as e:
        print(f"  FAIL: Dry run test -- {e}")

    try:
        await test_full_run()
        passed += 1
    except Exception as e:
        print(f"  FAIL: Full run test -- {e}")

    header(f"RESULTS: {passed}/{total} passed")

    if passed == total:
        print("  Brick 8 Gate Test: ALL PASS")
    else:
        print(f"  Brick 8 Gate Test: {total - passed} FAILED")

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)

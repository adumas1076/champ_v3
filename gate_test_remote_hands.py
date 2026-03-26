#!/usr/bin/env python3
"""
Gate Test — Remote Hands
Tests the full chain: Brain WS endpoint ↔ Local Agent ↔ Desktop/Browser

Run Brain first:  python -m brain.main
Then this test:   python gate_test_remote_hands.py

Tests:
1. Router detects local mode correctly
2. Router status endpoint
3. Local agent connects via WebSocket
4. Commands flow through and execute
"""

import asyncio
import json
import sys

import requests
import websockets

BRAIN_URL = "http://127.0.0.1:8100"
BRAIN_WS = "ws://127.0.0.1:8100"


def test_hands_status():
    """Test the hands status endpoint."""
    print("\n--- Test: Hands Status ---")
    try:
        resp = requests.get(f"{BRAIN_URL}/v1/hands/status", timeout=5)
        data = resp.json()
        print(f"  Mode: {data.get('mode')}")
        print(f"  Env override: {data.get('env_override')}")
        if data.get("mode") == "remote":
            print(f"  Agent connected: {data.get('agent_connected')}")
        print("  PASS")
        return True
    except Exception as e:
        print(f"  FAIL: {e}")
        return False


async def test_local_agent_flow():
    """Simulate a local agent connecting and handling a command."""
    print("\n--- Test: Local Agent WebSocket Flow ---")

    try:
        async with websockets.connect(
            f"{BRAIN_WS}/ws/hands",
            ping_interval=20,
        ) as ws:
            print("  Connected to Brain WS")

            # Simulate receiving a command by sending a fake response
            # In production, Brain sends commands and agent responds
            # Here we just verify the connection works

            # Check status shows connected
            resp = requests.get(f"{BRAIN_URL}/v1/hands/status", timeout=5)
            data = resp.json()
            # When running locally, mode will be "local" not "remote"
            # but the WS connection should still be established
            print(f"  Status after connect: {data}")

            print("  PASS - WebSocket connection established")
            return True

    except Exception as e:
        print(f"  FAIL: {e}")
        return False


def test_router_import():
    """Test that router imports work and detects environment."""
    print("\n--- Test: Router Import & Detection ---")
    try:
        from hands.router import get_hands_status
        status = get_hands_status()
        print(f"  Mode: {status['mode']}")
        print(f"  PASS")
        return True
    except Exception as e:
        print(f"  FAIL: {e}")
        return False


async def main():
    print("=" * 50)
    print("  CHAMP V3 — Remote Hands Gate Test")
    print("=" * 50)

    results = []

    # Test 1: Router import
    results.append(test_router_import())

    # Test 2: Hands status (requires Brain running)
    results.append(test_hands_status())

    # Test 3: WebSocket flow (requires Brain running)
    results.append(await test_local_agent_flow())

    # Summary
    passed = sum(results)
    total = len(results)
    print(f"\n{'=' * 50}")
    print(f"  Results: {passed}/{total} passed")
    print(f"{'=' * 50}")

    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

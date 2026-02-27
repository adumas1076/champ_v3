# ============================================
# CHAMP V3 -- Self Mode Migration
# Creates the self_mode_runs table in Supabase.
#
# Usage: python migrate_self_mode.py
# ============================================

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv
load_dotenv()

from brain.config import load_settings
from brain.memory import SupabaseMemory


SQL_FILE = Path(__file__).resolve().parent / "self_mode" / "sql" / "create_self_mode_runs.sql"

SUPABASE_SQL_EDITOR = (
    "https://supabase.com/dashboard/project/sephljbfrdqegicfmryv/sql/new"
)


async def check_table_exists(memory: SupabaseMemory) -> bool:
    """Try to query the table. If it exists, return True."""
    if not memory._client:
        return False
    try:
        result = await memory._client.table("self_mode_runs").select(
            "id"
        ).limit(1).execute()
        return True
    except Exception:
        return False


async def try_create_via_rpc(memory: SupabaseMemory) -> bool:
    """Try to create the table via Supabase RPC if available."""
    if not memory._client:
        return False
    try:
        sql = SQL_FILE.read_text(encoding="utf-8")
        # Try the query endpoint (available on some Supabase setups)
        await memory._client.rpc("exec_sql", {"query": sql}).execute()
        return True
    except Exception:
        return False


async def main():
    print("=" * 60)
    print("  CHAMP V3 -- Self Mode Migration")
    print("=" * 60)

    settings = load_settings()
    memory = SupabaseMemory(settings)
    await memory.connect()

    if not memory._client:
        print("\n  ERROR: Could not connect to Supabase.")
        print("  Check SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env")
        return False

    print("\n  Connected to Supabase.")

    # Check if table already exists
    exists = await check_table_exists(memory)
    if exists:
        print("  Table 'self_mode_runs' already exists!")

        # Test a write/read cycle
        test_id = "migration-test-001"
        try:
            await memory.upsert_self_mode_run(
                run_id=test_id,
                goal_card={"goal_id": "test", "objective": "migration check"},
                current_step=0,
                subtasks=[],
                status="queued",
            )
            run = await memory.get_self_mode_run(test_id)
            if run:
                print("  Write/read test: PASS")
                # Clean up test record
                await memory._client.table("self_mode_runs").delete().eq(
                    "id", test_id
                ).execute()
                print("  Cleanup: done")
            else:
                print("  Write/read test: FAIL (could not read back)")
        except Exception as e:
            print(f"  Write/read test: FAIL ({e})")

        await memory.disconnect()
        print("\n  Migration complete -- table is ready.")
        return True

    # Table doesn't exist -- try to create it
    print("\n  Table 'self_mode_runs' does not exist.")
    print("  Attempting to create...")

    created = await try_create_via_rpc(memory)
    if created:
        print("  Table created via RPC!")
        await memory.disconnect()
        return True

    # RPC didn't work -- give the user the SQL to paste
    sql = SQL_FILE.read_text(encoding="utf-8")
    print("\n  Could not auto-create the table (needs direct DB access).")
    print("  Please paste the following SQL in the Supabase SQL Editor:")
    print(f"\n  Dashboard: {SUPABASE_SQL_EDITOR}")
    print(f"\n{'='*60}")
    print(sql)
    print(f"{'='*60}")
    print("\n  After pasting and running, re-run this script to verify.")

    await memory.disconnect()
    return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)

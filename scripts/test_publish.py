"""
Test Publish Harness — Dry-run and live-test the Marketing Machine.

Usage:
    # Dry run — no actual posts, just verify wiring
    python scripts/test_publish.py --dry-run

    # Test one platform with one post
    python scripts/test_publish.py --platform twitter --influencer anthony

    # Run a full daily cycle (test mode)
    python scripts/test_publish.py --full-cycle

    # Verify capture (waitlist + assessment)
    python scripts/test_publish.py --test-capture

    # Check all env vars + API connections
    python scripts/test_publish.py --health

Run this BEFORE the real Wednesday launch to verify everything works.
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

# Add champ_v3 to path
CHAMP_V3 = Path(__file__).parent.parent
sys.path.insert(0, str(CHAMP_V3))

# Load .env file so we actually see configured values
def _load_env():
    env_file = CHAMP_V3 / ".env"
    if not env_file.exists():
        return False
    try:
        from dotenv import load_dotenv
        load_dotenv(env_file)
        return True
    except ImportError:
        # Fallback: parse manually
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                # Strip surrounding quotes if present
                value = value.strip().strip('"').strip("'")
                if key.strip() and value:
                    os.environ.setdefault(key.strip(), value)
        return True


_load_env()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("test_publish")


# ============================================
# Health Check
# ============================================

def check_env_vars():
    """Check which API keys are configured."""
    required = {
        "Supabase": ["SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"],
        "Resend": ["RESEND_API_KEY"],
        "Twitter": ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET"],
        "Instagram": ["INSTAGRAM_ACCESS_TOKEN", "INSTAGRAM_BUSINESS_ID"],
        "LinkedIn": ["LINKEDIN_ACCESS_TOKEN", "LINKEDIN_PERSON_ID"],
        "TikTok": ["TIKTOK_ACCESS_TOKEN", "TIKTOK_OPEN_ID"],
        "YouTube": ["YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN"],
        "Facebook": ["FACEBOOK_PAGE_ACCESS_TOKEN", "FACEBOOK_PAGE_ID"],
        "Nango": ["NANGO_BASE_URL", "NANGO_SECRET_KEY"],
    }

    print("\n" + "="*60)
    print("  ENVIRONMENT VARIABLE CHECK")
    print("="*60)

    all_good = True
    for category, keys in required.items():
        missing = [k for k in keys if not os.getenv(k)]
        if not missing:
            print(f"  [OK] {category}: configured")
        else:
            print(f"  [--] {category}: missing {missing}")
            all_good = False

    return all_good


async def check_supabase():
    """Verify Supabase connection + tables exist."""
    try:
        from content_engine.capture.waitlist import _get_supabase
        client = _get_supabase()
        if not client:
            print("  [--] Supabase: client not available (check credentials)")
            return False

        # Try querying the waitlist table
        try:
            client.table("waitlist").select("id", count="exact").limit(1).execute()
            print("  [OK] Supabase: connected, waitlist table exists")
        except Exception as e:
            if "does not exist" in str(e).lower():
                print("  [--] Supabase: connected, but 'waitlist' table missing — run migration 013")
                return False
            print(f"  [OK] Supabase: connected (query err: {str(e)[:50]})")

        try:
            client.table("assessment_responses").select("id", count="exact").limit(1).execute()
            print("  [OK] Supabase: assessment_responses table exists")
        except Exception as e:
            if "does not exist" in str(e).lower():
                print("  [--] Supabase: assessment_responses table missing — run migration 013")
                return False
        return True
    except Exception as e:
        print(f"  [--] Supabase: error: {e}")
        return False


async def check_graph():
    """Verify MarketingGraph is available."""
    try:
        from content_engine import graph_writer
        view = graph_writer.get_analyst_view()
        if view:
            health = view.get("health", {})
            print(f"  [OK] MarketingGraph: loaded, {health.get('nodes', 0)} nodes, {health.get('edges', 0)} edges")
            return True
        else:
            print("  [--] MarketingGraph: loaded but returning empty")
            return False
    except Exception as e:
        print(f"  [--] MarketingGraph: error: {e}")
        return False


async def check_influencers():
    """Verify influencer YAML profiles load."""
    try:
        from content_engine.influencers.loader import load_all_influencers
        profiles = load_all_influencers()
        if profiles:
            print(f"  [OK] Influencers: {len(profiles)} profiles loaded")
            for p in profiles:
                print(f"       - {p.get('id')}: {p.get('name', 'unnamed')} ({p.get('niche', 'no niche')})")
            return True
        else:
            print("  [--] Influencers: no profiles found")
            return False
    except Exception as e:
        print(f"  [--] Influencers: error: {e}")
        return False


async def check_topic_bank():
    """Verify topic bank loads."""
    try:
        import yaml
        topic_file = CHAMP_V3 / "content_engine" / "topic_bank.yaml"
        if not topic_file.exists():
            print(f"  [--] Topic bank: file not found at {topic_file}")
            return False
        with open(topic_file) as f:
            data = yaml.safe_load(f)
        topics = data.get("topics", [])
        by_stage = {}
        for t in topics:
            stage = t.get("kpi_stage", "unknown")
            by_stage[stage] = by_stage.get(stage, 0) + 1
        print(f"  [OK] Topic bank: {len(topics)} topics loaded")
        for stage, count in by_stage.items():
            print(f"       - {stage}: {count}")
        return True
    except Exception as e:
        print(f"  [--] Topic bank: error: {e}")
        return False


# ============================================
# Dry Run Cycle
# ============================================

async def dry_run_cycle():
    """Run orchestrator cycle in dry-run mode (no actual posts)."""
    from content_engine.orchestrator import run_daily_cycle, OrchestratorConfig

    config = OrchestratorConfig(
        approval_mode="approve_first",  # Nothing posts without approval
        posts_per_face_per_platform=1,  # Just 1 per face per platform for testing
        platforms=["twitter"],  # Just one platform
        content_tiers=["text"],
    )

    print("\n" + "="*60)
    print("  DRY-RUN ORCHESTRATOR CYCLE")
    print("  Platforms: twitter only | 1 post/face/platform")
    print("="*60 + "\n")

    manifest = await run_daily_cycle(config=config)

    print(f"\n  Result: {manifest.total_planned} planned, {manifest.total_passed_qa} passed QA, {manifest.total_posted} posted")
    print(f"  Content by status:")
    by_status = {}
    for item in manifest.items:
        by_status[item.status] = by_status.get(item.status, 0) + 1
    for status, count in by_status.items():
        print(f"    {status}: {count}")

    # Show first item details
    if manifest.items:
        first = manifest.items[0]
        print(f"\n  Sample content piece:")
        print(f"    Topic: {first.topic}")
        print(f"    Face: {first.influencer_id} | Platform: {first.platform}")
        print(f"    Funnel: {first.funnel_stage} | KPI: {first.kpi_stage}")
        print(f"    Script: {first.script[:100]}...")
        print(f"    CTA: {first.cta}")
        print(f"    Status: {first.status}")


# ============================================
# Capture Test
# ============================================

async def test_capture():
    """Test waitlist + assessment capture end-to-end."""
    from content_engine.capture.waitlist import capture_waitlist_lead, WaitlistEntry
    from content_engine.capture.assessment import submit_assessment

    print("\n" + "="*60)
    print("  CAPTURE PIPELINE TEST")
    print("="*60 + "\n")

    test_email = f"test_{os.urandom(4).hex()}@example.com"

    # Test 1: Waitlist
    print(f"  Testing waitlist capture with {test_email}...")
    entry = WaitlistEntry(
        email=test_email,
        name="Test User",
        source_platform="twitter",
        source_influencer="anthony",
        source_campaign="test_cycle",
    )
    result = await capture_waitlist_lead(entry, source_content_id="test_content_001")
    print(f"    Success: {result.success} | New: {result.is_new} | Welcome sent: {result.welcome_sent}")

    # Test 2: Assessment
    test_email_2 = f"buyer_{os.urandom(4).hex()}@example.com"
    print(f"\n  Testing assessment submission with {test_email_2}...")

    # Answer all YES for buyer tier
    from content_engine.capture.assessment import ASSESSMENTS
    ai_ready = ASSESSMENTS["ai_readiness"]
    answers = {q.id: True for q in ai_ready.questions if not q.segmentation}
    answers["sg_1"] = "test bottleneck: content creation"
    answers["sg_2"] = "SaaS"

    result = await submit_assessment(
        assessment_id="ai_readiness",
        email=test_email_2,
        answers=answers,
        name="Test Buyer",
        source_platform="twitter",
        source_influencer="anthony",
        utm_content="test_content_001",
        utm_source="twitter",
        utm_medium="social",
    )

    print(f"    Success: {result.get('success')}")
    print(f"    Tier: {result.get('tier')} ({result.get('percentage'):.0f}%)")
    print(f"    Message: {result.get('message', '')[:100]}")
    print(f"    CTA: {result.get('cta')}")


# ============================================
# Single Post Test
# ============================================

async def test_single_post(platform: str, influencer: str, dry_run: bool = True):
    """Test posting a single piece of content to one platform."""
    from content_engine.publishers import register_all_publishers
    from content_engine.publishers.base import PostPayload
    from content_engine.pipeline.scheduler import ContentScheduler

    print("\n" + "="*60)
    print(f"  SINGLE POST TEST: {platform} | {influencer} | dry_run={dry_run}")
    print("="*60 + "\n")

    scheduler = ContentScheduler(approval_mode="auto_post")
    publishers = register_all_publishers(scheduler)
    publisher = publishers.get(platform)

    if not publisher:
        print(f"  [--] Publisher for {platform} not registered")
        return

    # Check auth
    authenticated = await publisher._authenticate()
    if not authenticated:
        print(f"  [--] {platform}: not authenticated (missing env vars)")
        return
    print(f"  [OK] {platform}: authenticated")

    payload = PostPayload(
        text=f"[TEST POST] Cocreatiq Marketing Machine smoke test at {os.urandom(4).hex()}",
        influencer_id=influencer,
        content_id=f"test_{os.urandom(4).hex()}",
        funnel_stage="cold",
        content_type="text",
        is_ai_generated=True,
    )

    if dry_run:
        print(f"  [DRY RUN] Would post: {payload.text}")
        print(f"  [DRY RUN] No API call made")
    else:
        print(f"  Posting: {payload.text}")
        result = await publisher.post(payload)
        if result.success:
            print(f"  [OK] Posted! URL: {result.post_url}")
        else:
            print(f"  [--] Failed: {result.error}")


# ============================================
# Main
# ============================================

async def main():
    parser = argparse.ArgumentParser(description="Marketing Machine test harness")
    parser.add_argument("--health", action="store_true", help="Run full health check")
    parser.add_argument("--dry-run", action="store_true", help="Run full cycle dry-run")
    parser.add_argument("--full-cycle", action="store_true", help="Run full daily cycle")
    parser.add_argument("--test-capture", action="store_true", help="Test waitlist + assessment capture")
    parser.add_argument("--platform", type=str, help="Test post on single platform")
    parser.add_argument("--influencer", type=str, default="anthony", help="Influencer ID for single post test")
    parser.add_argument("--live", action="store_true", help="Make actual API calls (default is dry-run)")

    args = parser.parse_args()

    if args.health or not any([args.dry_run, args.full_cycle, args.test_capture, args.platform]):
        print("\n" + "="*60)
        print("  MARKETING MACHINE HEALTH CHECK")
        print("="*60)
        check_env_vars()
        print()
        print("  Checking runtime connections...")
        await check_supabase()
        await check_graph()
        await check_influencers()
        await check_topic_bank()
        print()

    if args.dry_run or args.full_cycle:
        await dry_run_cycle()

    if args.test_capture:
        await test_capture()

    if args.platform:
        await test_single_post(args.platform, args.influencer, dry_run=not args.live)


if __name__ == "__main__":
    asyncio.run(main())
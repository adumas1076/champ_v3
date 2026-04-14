"""
Waitlist Capture — V1 Lead Capture for Marketing Machine

Simple flow:
  1. Stranger submits email (from landing page, DM, or bio link)
  2. Store in Supabase (waitlist table)
  3. Send welcome email via Resend
  4. Track source (UTM params — which face, which platform)
  5. Done. They're on the list.

V2 adds: lead scoring, 7-day nurture, behavior triggers, Stripe checkout.
V1 is just capture + welcome + track.

Required env vars:
  SUPABASE_URL              — Supabase project URL
  SUPABASE_SERVICE_ROLE_KEY — Service role key (server-side only)
  RESEND_API_KEY            — Resend API key for sending email

Supabase table: waitlist
  CREATE TABLE waitlist (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    name TEXT,
    source_platform TEXT,        -- twitter, instagram, linkedin, tiktok, youtube, facebook, direct
    source_influencer TEXT,      -- anthony, influencer_1, influencer_2, influencer_3
    source_campaign TEXT,        -- UTM campaign
    utm_source TEXT,
    utm_medium TEXT,
    utm_content TEXT,
    status TEXT DEFAULT 'active', -- active, unsubscribed
    welcome_sent BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
  );
"""

import os
import logging
from datetime import datetime
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

_supabase_client = None


# ============================================
# Data Model
# ============================================

@dataclass
class WaitlistEntry:
    """A single waitlist signup."""
    email: str
    name: Optional[str] = None
    source_platform: Optional[str] = None
    source_influencer: Optional[str] = None
    source_campaign: Optional[str] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_content: Optional[str] = None


@dataclass
class CaptureResult:
    """Result of a waitlist capture attempt."""
    success: bool
    email: str
    is_new: bool = True           # False if already on list
    welcome_sent: bool = False
    error: Optional[str] = None


# ============================================
# Supabase — Store leads
# ============================================

def _get_supabase():
    """Get Supabase client (lazy-loaded)."""
    global _supabase_client
    if _supabase_client:
        return _supabase_client

    try:
        from supabase import create_client

        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

        if not url or not key:
            logger.warning("Supabase credentials not set — waitlist storage unavailable")
            return None

        _supabase_client = create_client(url, key)
        return _supabase_client
    except ImportError:
        logger.warning("supabase-py not installed — run: pip install supabase")
        return None


async def store_lead(entry: WaitlistEntry) -> tuple[bool, bool]:
    """Store a lead in the waitlist table.

    Returns: (success, is_new)
      is_new = True if this is a new email
      is_new = False if email already exists (not an error — just a duplicate)
    """
    client = _get_supabase()
    if not client:
        logger.error("[WAITLIST] Supabase not available — lead not stored")
        return False, False

    try:
        # Check if email already exists
        existing = client.table("waitlist").select("id").eq("email", entry.email).execute()
        if existing.data and len(existing.data) > 0:
            logger.info(f"[WAITLIST] {entry.email} already on waitlist — skipping")
            return True, False  # Success but not new

        # Insert new lead
        data = {
            "email": entry.email,
            "name": entry.name,
            "source_platform": entry.source_platform,
            "source_influencer": entry.source_influencer,
            "source_campaign": entry.source_campaign,
            "utm_source": entry.utm_source,
            "utm_medium": entry.utm_medium,
            "utm_content": entry.utm_content,
            "status": "active",
            "welcome_sent": False,
        }
        # Remove None values
        data = {k: v for k, v in data.items() if v is not None}

        result = client.table("waitlist").insert(data).execute()
        logger.info(f"[WAITLIST] New lead captured: {entry.email} from {entry.source_platform}/{entry.source_influencer}")
        return True, True

    except Exception as e:
        logger.error(f"[WAITLIST] Failed to store lead {entry.email}: {e}")
        return False, False


async def mark_welcome_sent(email: str):
    """Mark that the welcome email was sent for this lead."""
    client = _get_supabase()
    if not client:
        return
    try:
        client.table("waitlist").update({
            "welcome_sent": True,
            "updated_at": datetime.utcnow().isoformat(),
        }).eq("email", email).execute()
    except Exception as e:
        logger.warning(f"[WAITLIST] Failed to mark welcome sent for {email}: {e}")


async def get_waitlist_count() -> int:
    """Get total number of leads on the waitlist."""
    client = _get_supabase()
    if not client:
        return 0
    try:
        result = client.table("waitlist").select("id", count="exact").eq("status", "active").execute()
        return result.count or 0
    except Exception:
        return 0


async def get_waitlist_stats() -> dict:
    """Get waitlist stats grouped by source."""
    client = _get_supabase()
    if not client:
        return {}
    try:
        result = client.table("waitlist").select("source_platform, source_influencer").eq("status", "active").execute()
        stats = {"total": len(result.data), "by_platform": {}, "by_influencer": {}}
        for row in result.data:
            plat = row.get("source_platform", "unknown")
            inf = row.get("source_influencer", "unknown")
            stats["by_platform"][plat] = stats["by_platform"].get(plat, 0) + 1
            stats["by_influencer"][inf] = stats["by_influencer"].get(inf, 0) + 1
        return stats
    except Exception:
        return {}


# ============================================
# Resend — Send welcome email
# ============================================

async def send_welcome_email(email: str, name: Optional[str] = None) -> bool:
    """Send a single welcome email via Resend.

    V1: One email — "You're on the list. Here's what's coming."
    V2: This becomes Day 0 of the 7-day nurture sequence.
    """
    api_key = os.getenv("RESEND_API_KEY")
    if not api_key:
        logger.warning("[WAITLIST] RESEND_API_KEY not set — welcome email not sent")
        return False

    try:
        import httpx

        from_name = os.getenv("RESEND_FROM_NAME", "Cocreatiq")
        from_email = os.getenv("RESEND_FROM_EMAIL", "hello@cocreatiq.com")

        greeting = f"Hey {name}" if name else "Hey"

        html_body = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 40px 20px;">
            <h1 style="font-size: 24px; margin-bottom: 16px;">{greeting} — you're in.</h1>

            <p style="font-size: 16px; line-height: 1.6; color: #333;">
                You just joined the waitlist for the Marketing Machine — an autonomous AI system
                that creates content, posts it across 6 platforms, and turns strangers into clients.
                On autopilot.
            </p>

            <p style="font-size: 16px; line-height: 1.6; color: #333;">
                Here's what's coming:
            </p>

            <ul style="font-size: 16px; line-height: 1.8; color: #333;">
                <li><strong>4 AI influencers</strong> posting 48+ pieces/day</li>
                <li><strong>6 platforms</strong> covered automatically</li>
                <li><strong>Self-improving content</strong> that gets smarter every cycle</li>
                <li><strong>Click to Client pipeline</strong> — every post feeds the funnel</li>
            </ul>

            <p style="font-size: 16px; line-height: 1.6; color: #333;">
                You'll be the first to know when we launch. In the meantime,
                follow our content — you'll see the system in action before you even sign up.
            </p>

            <p style="font-size: 16px; line-height: 1.6; color: #666; margin-top: 32px;">
                — The Cocreatiq Team
            </p>
        </div>
        """

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": f"{from_name} <{from_email}>",
                    "to": [email],
                    "subject": "You're on the list — here's what's coming",
                    "html": html_body,
                },
            )

            if resp.status_code in (200, 201):
                logger.info(f"[WAITLIST] Welcome email sent to {email}")
                return True
            else:
                logger.error(f"[WAITLIST] Resend error {resp.status_code}: {resp.text[:200]}")
                return False

    except ImportError:
        logger.warning("httpx not installed — run: pip install httpx")
        return False
    except Exception as e:
        logger.error(f"[WAITLIST] Failed to send welcome email to {email}: {e}")
        return False


# ============================================
# Main Capture Function
# ============================================

async def capture_waitlist_lead(entry: WaitlistEntry, source_content_id: str = "") -> CaptureResult:
    """Full waitlist capture flow.

    1. Store in Supabase
    2. Send welcome email (if new)
    3. Write to MarketingGraph (the V1 metric edge)
    4. Return result

    This is the single function the landing page API endpoint calls.
    """
    # Step 1: Store in Supabase
    stored, is_new = await store_lead(entry)
    if not stored:
        return CaptureResult(
            success=False,
            email=entry.email,
            error="Failed to store lead — check Supabase connection",
        )

    # Step 2: Welcome email (only for new leads)
    welcome_sent = False
    if is_new:
        welcome_sent = await send_welcome_email(entry.email, entry.name)
        if welcome_sent:
            await mark_welcome_sent(entry.email)

    # Step 3: Write to MarketingGraph (V1 conversion tracking)
    # Graph writes are non-blocking — publish succeeds even if graph is down.
    if is_new:
        try:
            from content_engine import graph_writer
            import uuid
            lead_id = uuid.uuid4().hex[:16]
            graph_writer.record_waitlist_lead(
                lead_id=lead_id,
                email=entry.email,
                source_content_id=source_content_id,
                source_influencer_id=entry.source_influencer or "",
                metadata={
                    "source_platform": entry.source_platform,
                    "utm_source": entry.utm_source,
                    "utm_campaign": entry.source_campaign,
                    "name": entry.name,
                },
            )
        except Exception as e:
            logger.warning(f"[WAITLIST] Graph write failed (non-fatal): {e}")

    return CaptureResult(
        success=True,
        email=entry.email,
        is_new=is_new,
        welcome_sent=welcome_sent,
    )
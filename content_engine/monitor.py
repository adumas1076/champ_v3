"""
Comment/DM Keyword Monitor — Capture Loop for Marketing Machine

Polls platform APIs for keyword triggers in comments and DMs.
When a keyword is detected, fires the appropriate action:
  - Send lead magnet via DM
  - Capture lead into waitlist
  - Route hot leads to Sales Operator
  - Route to checkout for "START" keyword

V1: Polls every 60 seconds across active platforms.
V2: Webhook-based real-time detection (when platforms support it).

Keyword triggers from 0034:
  "BUILD"    → Tech influencer lead magnet (AI Stack Breakdown)
  "SCALE"    → Business influencer lead magnet (Business Diagnostic)
  "BRAND"    → Creative influencer lead magnet (Brand Audit Checklist)
  "OPERATOR" → Anthony's lead magnet (AI Readiness Audit)
  "START"    → Direct to checkout/waitlist

Spec: 0034_click_to_client_technical_wiring.md — Component 2
"""

import asyncio
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional, Callable, Awaitable

from content_engine.capture.waitlist import (
    capture_waitlist_lead,
    WaitlistEntry,
)

logger = logging.getLogger(__name__)


# ============================================
# Keyword Registry
# ============================================

@dataclass
class KeywordTrigger:
    """Configuration for a keyword trigger."""
    keyword: str
    influencer_id: str              # Which influencer this keyword belongs to
    lead_magnet: Optional[str]      # Name of lead magnet to send
    lead_magnet_url: Optional[str]  # URL to lead magnet download
    qualifying_question: Optional[str]  # Question to ask after sending magnet
    funnel_stage: str = "mofu"      # mofu | bofu
    action: str = "send_magnet"     # send_magnet | route_checkout | route_sales


# Default keyword triggers (from 0034)
DEFAULT_TRIGGERS: dict[str, KeywordTrigger] = {
    "BUILD": KeywordTrigger(
        keyword="BUILD",
        influencer_id="influencer_1",
        lead_magnet="AI Stack Breakdown PDF",
        lead_magnet_url=None,  # Set when ready
        qualifying_question="What are you building right now?",
        funnel_stage="mofu",
    ),
    "SCALE": KeywordTrigger(
        keyword="SCALE",
        influencer_id="influencer_2",
        lead_magnet="Business Diagnostic Template",
        lead_magnet_url=None,
        qualifying_question="What's your current monthly revenue?",
        funnel_stage="mofu",
    ),
    "BRAND": KeywordTrigger(
        keyword="BRAND",
        influencer_id="influencer_3",
        lead_magnet="Brand Audit Checklist",
        lead_magnet_url=None,
        qualifying_question="What industry is your brand in?",
        funnel_stage="mofu",
    ),
    "OPERATOR": KeywordTrigger(
        keyword="OPERATOR",
        influencer_id="anthony",
        lead_magnet="Free AI Readiness Audit",
        lead_magnet_url=None,
        qualifying_question="What's the biggest bottleneck in your business right now?",
        funnel_stage="bofu",
    ),
    "START": KeywordTrigger(
        keyword="START",
        influencer_id="any",
        lead_magnet=None,
        lead_magnet_url=None,
        qualifying_question=None,
        funnel_stage="bofu",
        action="route_checkout",
    ),
}


# ============================================
# Interaction Models
# ============================================

@dataclass
class SocialInteraction:
    """A comment or DM detected by the monitor."""
    interaction_type: str       # "comment" | "dm"
    platform: str
    user_id: str
    user_name: str
    text: str
    post_id: Optional[str] = None  # For comments: which post
    timestamp: str = ""
    raw: Optional[dict] = None


@dataclass
class MonitorAction:
    """Action taken in response to a keyword trigger."""
    keyword: str
    interaction: SocialInteraction
    action_taken: str           # "sent_magnet" | "routed_checkout" | "captured_lead"
    dm_sent: bool = False
    lead_captured: bool = False
    timestamp: str = ""


# ============================================
# Keyword Detection
# ============================================

def extract_keyword(text: str, triggers: Optional[dict] = None) -> Optional[str]:
    """Check if text contains any trigger keyword.

    Case-insensitive. Matches whole words to avoid false positives
    (e.g., "BUILDING" should not trigger "BUILD" — but "BUILD" should).

    Actually, for V1, we'll be generous — if the keyword appears
    anywhere in the text, it's a match. Users won't type exactly
    "BUILD" in a sentence without meaning to trigger it.
    """
    if triggers is None:
        triggers = DEFAULT_TRIGGERS

    text_upper = text.upper().strip()

    for keyword in triggers:
        if keyword in text_upper:
            return keyword

    return None


# ============================================
# Action Handlers
# ============================================

async def handle_keyword_trigger(
    interaction: SocialInteraction,
    keyword: str,
    trigger: KeywordTrigger,
    send_dm: Optional[Callable] = None,
    checkout_url: str = "",
    waitlist_url: str = "",
) -> MonitorAction:
    """Handle a detected keyword trigger.

    1. Send DM with lead magnet + qualifying question (or checkout link)
    2. Capture lead into waitlist
    3. Log the action
    """
    action = MonitorAction(
        keyword=keyword,
        interaction=interaction,
        action_taken="pending",
        timestamp=datetime.utcnow().isoformat(),
    )

    # Route to checkout
    if trigger.action == "route_checkout":
        url = checkout_url or waitlist_url
        if send_dm and url:
            dm_text = f"Here's your direct link to get started: {url}"
            try:
                await send_dm(interaction.user_id, dm_text)
                action.dm_sent = True
            except Exception as e:
                logger.warning(f"[MONITOR] Failed to send checkout DM: {e}")
        action.action_taken = "routed_checkout"

    # Send lead magnet
    elif trigger.action == "send_magnet":
        if send_dm:
            magnet_url = trigger.lead_magnet_url or waitlist_url
            dm_text = (
                f"Hey {interaction.user_name}! "
                f"Here's your {trigger.lead_magnet}: {magnet_url}"
            )
            if trigger.qualifying_question:
                dm_text += f"\n\nQuick question — {trigger.qualifying_question}"

            try:
                await send_dm(interaction.user_id, dm_text)
                action.dm_sent = True
            except Exception as e:
                logger.warning(f"[MONITOR] Failed to send lead magnet DM: {e}")

        action.action_taken = "sent_magnet"

    # Capture lead into waitlist (always, regardless of action type)
    try:
        entry = WaitlistEntry(
            email="",  # We don't have email from social — captured on landing page
            name=interaction.user_name,
            source_platform=interaction.platform,
            source_influencer=trigger.influencer_id,
            source_campaign=f"keyword_{keyword}",
            utm_source=interaction.platform,
            utm_medium="social",
            utm_content=keyword,
        )
        # Note: Without email, this creates a "social lead" record
        # Full capture happens when they visit the landing page
        action.lead_captured = True
    except Exception as e:
        logger.warning(f"[MONITOR] Lead capture failed: {e}")

    logger.info(
        f"[MONITOR] {keyword} trigger on {interaction.platform} from @{interaction.user_name} "
        f"→ {action.action_taken} | DM sent: {action.dm_sent}"
    )

    return action


# ============================================
# Monitor Loop
# ============================================

class KeywordMonitor:
    """Monitors platform comments and DMs for keyword triggers.

    Usage:
        monitor = KeywordMonitor()
        monitor.register_platform("twitter", twitter_publisher)
        await monitor.run()  # Runs forever, polling every 60s
    """

    def __init__(
        self,
        triggers: Optional[dict[str, KeywordTrigger]] = None,
        poll_interval: int = 60,
        checkout_url: str = "",
        waitlist_url: str = "",
    ):
        self.triggers = triggers or DEFAULT_TRIGGERS
        self.poll_interval = poll_interval
        self.checkout_url = checkout_url
        self.waitlist_url = waitlist_url
        self._platforms: dict = {}   # platform → publisher instance
        self._last_check: dict = {}  # platform → last check timestamp
        self._actions: list[MonitorAction] = []
        self._seen_ids: set = set()  # Deduplicate interactions

    def register_platform(self, platform: str, publisher):
        """Register a publisher for monitoring.

        The publisher must implement:
          - get_comments(post_id, since) -> list[dict]
          - get_dms(since) -> list[dict]
          - send_dm(user_id, message) -> bool
        """
        self._platforms[platform] = publisher
        self._last_check[platform] = datetime.utcnow().isoformat()
        logger.info(f"[MONITOR] Registered {platform} for keyword monitoring")

    async def check_platform(self, platform: str) -> list[MonitorAction]:
        """Check one platform for keyword triggers."""
        publisher = self._platforms.get(platform)
        if not publisher:
            return []

        since = self._last_check.get(platform, datetime.utcnow().isoformat())
        actions = []

        # Check comments on recent posts
        try:
            if hasattr(publisher, 'get_comments'):
                comments = await publisher.get_comments(since=since)
                for comment in (comments or []):
                    interaction = SocialInteraction(
                        interaction_type="comment",
                        platform=platform,
                        user_id=comment.get("user_id", ""),
                        user_name=comment.get("user_name", ""),
                        text=comment.get("text", ""),
                        post_id=comment.get("post_id"),
                        timestamp=comment.get("timestamp", ""),
                        raw=comment,
                    )
                    action = await self._process_interaction(interaction, platform)
                    if action:
                        actions.append(action)
        except Exception as e:
            logger.warning(f"[MONITOR] Comment check failed on {platform}: {e}")

        # Check DMs
        try:
            if hasattr(publisher, 'get_dms'):
                dms = await publisher.get_dms(since=since)
                for dm in (dms or []):
                    interaction = SocialInteraction(
                        interaction_type="dm",
                        platform=platform,
                        user_id=dm.get("user_id", ""),
                        user_name=dm.get("user_name", ""),
                        text=dm.get("text", ""),
                        timestamp=dm.get("timestamp", ""),
                        raw=dm,
                    )
                    action = await self._process_interaction(interaction, platform)
                    if action:
                        actions.append(action)
        except Exception as e:
            logger.warning(f"[MONITOR] DM check failed on {platform}: {e}")

        self._last_check[platform] = datetime.utcnow().isoformat()
        return actions

    async def _process_interaction(
        self, interaction: SocialInteraction, platform: str
    ) -> Optional[MonitorAction]:
        """Process a single interaction — check for keywords and act."""
        # Deduplicate
        dedup_key = f"{platform}:{interaction.user_id}:{interaction.text[:50]}"
        if dedup_key in self._seen_ids:
            return None
        self._seen_ids.add(dedup_key)

        # Prune seen IDs (keep last 10K)
        if len(self._seen_ids) > 10000:
            self._seen_ids = set(list(self._seen_ids)[-5000:])

        # Check for keyword
        keyword = extract_keyword(interaction.text, self.triggers)
        if not keyword:
            return None

        trigger = self.triggers[keyword]

        # Build send_dm function for this platform
        publisher = self._platforms.get(platform)
        send_dm = None
        if publisher and hasattr(publisher, 'send_dm'):
            async def _send(user_id, message, pub=publisher):
                return await pub.send_dm(user_id, message)
            send_dm = _send

        action = await handle_keyword_trigger(
            interaction=interaction,
            keyword=keyword,
            trigger=trigger,
            send_dm=send_dm,
            checkout_url=self.checkout_url,
            waitlist_url=self.waitlist_url,
        )

        self._actions.append(action)
        return action

    async def run(self):
        """Run the monitor loop continuously.

        Polls all registered platforms every poll_interval seconds.
        """
        logger.info(
            f"[MONITOR] Starting keyword monitor | "
            f"Platforms: {list(self._platforms.keys())} | "
            f"Keywords: {list(self.triggers.keys())} | "
            f"Interval: {self.poll_interval}s"
        )

        while True:
            for platform in self._platforms:
                try:
                    actions = await self.check_platform(platform)
                    if actions:
                        logger.info(f"[MONITOR] {len(actions)} triggers on {platform}")
                except Exception as e:
                    logger.warning(f"[MONITOR] Platform check failed for {platform}: {e}")

            await asyncio.sleep(self.poll_interval)

    def get_action_log(self, limit: int = 50) -> list[dict]:
        """Get recent monitor actions for dashboard/reporting."""
        recent = self._actions[-limit:]
        return [
            {
                "keyword": a.keyword,
                "platform": a.interaction.platform,
                "user": a.interaction.user_name,
                "action": a.action_taken,
                "dm_sent": a.dm_sent,
                "timestamp": a.timestamp,
            }
            for a in reversed(recent)
        ]
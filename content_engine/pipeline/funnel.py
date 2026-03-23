"""
Content Funnel Tracker
Tracks content distribution across funnel stages:
  TOF (Top of Funnel)    — 50% target — awareness, broad reach
  MOF (Middle of Funnel) — 30% target — consideration, education
  BOF (Bottom of Funnel) — 20% target — conversion, sales

Source: Lamar Mistake #3 — "Not translating into sales. Missing buyer's awareness."
All content funnels back to Cocreatiq OS waitlist/landing page.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


# Default funnel targets (from marketing.yaml)
DEFAULT_TARGETS = {
    "tof": 50,
    "mof": 30,
    "bof": 20,
}


@dataclass
class FunnelEntry:
    """A content piece tracked in the funnel."""
    content_id: str
    influencer_id: str
    platform: str
    funnel_stage: str          # tof | mof | bof
    content_type: str
    published_at: Optional[str] = None
    # Performance (filled after analytics pull)
    views: int = 0
    engagement: float = 0.0
    conversions: int = 0       # Clicks to waitlist/landing page
    # Backlink
    links_to_waitlist: bool = False


@dataclass
class FunnelSnapshot:
    """Point-in-time snapshot of funnel distribution."""
    influencer_id: str
    period: str                    # "2026-03-21" or "2026-W12"
    total_pieces: int = 0
    # Counts
    tof_count: int = 0
    mof_count: int = 0
    bof_count: int = 0
    # Percentages
    tof_pct: float = 0.0
    mof_pct: float = 0.0
    bof_pct: float = 0.0
    # Targets
    tof_target: float = 50.0
    mof_target: float = 30.0
    bof_target: float = 20.0
    # Health
    balanced: bool = False
    recommendation: str = ""
    snapshot_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class FunnelTracker:
    """Tracks and balances content across funnel stages.

    Usage:
        tracker = FunnelTracker()
        tracker.add("piece_123", "influencer_1", "instagram", "tof", "micro")
        snapshot = tracker.get_snapshot("influencer_1")
        print(snapshot.recommendation)
    """

    def __init__(self, targets: Optional[dict] = None):
        self.targets = targets or DEFAULT_TARGETS
        self._entries: list[FunnelEntry] = []

    def add(
        self,
        content_id: str,
        influencer_id: str,
        platform: str,
        funnel_stage: str,
        content_type: str,
        links_to_waitlist: bool = False,
        published_at: Optional[str] = None,
    ) -> FunnelEntry:
        """Track a content piece in the funnel."""
        entry = FunnelEntry(
            content_id=content_id,
            influencer_id=influencer_id,
            platform=platform,
            funnel_stage=funnel_stage,
            content_type=content_type,
            links_to_waitlist=links_to_waitlist,
            published_at=published_at or datetime.utcnow().isoformat(),
        )
        self._entries.append(entry)
        return entry

    def get_snapshot(
        self,
        influencer_id: Optional[str] = None,
        platform: Optional[str] = None,
        period: Optional[str] = None,
    ) -> FunnelSnapshot:
        """Get current funnel distribution snapshot."""
        entries = self._entries
        if influencer_id:
            entries = [e for e in entries if e.influencer_id == influencer_id]
        if platform:
            entries = [e for e in entries if e.platform == platform]

        total = len(entries)
        tof = sum(1 for e in entries if e.funnel_stage == "tof")
        mof = sum(1 for e in entries if e.funnel_stage == "mof")
        bof = sum(1 for e in entries if e.funnel_stage == "bof")

        tof_pct = (tof / total * 100) if total else 0
        mof_pct = (mof / total * 100) if total else 0
        bof_pct = (bof / total * 100) if total else 0

        # Check balance
        tof_ok = abs(tof_pct - self.targets["tof"]) <= 10
        mof_ok = abs(mof_pct - self.targets["mof"]) <= 10
        bof_ok = abs(bof_pct - self.targets["bof"]) <= 10
        balanced = tof_ok and mof_ok and bof_ok

        # Generate recommendation
        recommendation = self._generate_recommendation(tof_pct, mof_pct, bof_pct, total)

        return FunnelSnapshot(
            influencer_id=influencer_id or "all",
            period=period or datetime.utcnow().strftime("%Y-%m-%d"),
            total_pieces=total,
            tof_count=tof,
            mof_count=mof,
            bof_count=bof,
            tof_pct=round(tof_pct, 1),
            mof_pct=round(mof_pct, 1),
            bof_pct=round(bof_pct, 1),
            tof_target=self.targets["tof"],
            mof_target=self.targets["mof"],
            bof_target=self.targets["bof"],
            balanced=balanced,
            recommendation=recommendation,
        )

    def get_waitlist_conversion(self, influencer_id: Optional[str] = None) -> dict:
        """Track how many pieces link back to the waitlist/landing page.

        From checklist: 'All content funnels back to Cocreatiq OS waitlist/landing page'
        """
        entries = self._entries
        if influencer_id:
            entries = [e for e in entries if e.influencer_id == influencer_id]

        total = len(entries)
        linked = sum(1 for e in entries if e.links_to_waitlist)
        bof_entries = [e for e in entries if e.funnel_stage == "bof"]
        bof_linked = sum(1 for e in bof_entries if e.links_to_waitlist)

        return {
            "total_pieces": total,
            "linked_to_waitlist": linked,
            "link_rate": round(linked / max(1, total) * 100, 1),
            "bof_pieces": len(bof_entries),
            "bof_linked": bof_linked,
            "bof_link_rate": round(bof_linked / max(1, len(bof_entries)) * 100, 1),
            "recommendation": "All BOF content MUST link to waitlist" if bof_linked < len(bof_entries) else "BOF → waitlist coverage complete",
        }

    def _generate_recommendation(
        self,
        tof_pct: float,
        mof_pct: float,
        bof_pct: float,
        total: int,
    ) -> str:
        if total < 10:
            return "Not enough data — need at least 10 pieces to assess funnel balance."

        issues = []

        if tof_pct > self.targets["tof"] + 10:
            issues.append(f"TOF too high ({tof_pct:.0f}% vs {self.targets['tof']}% target). Producing too much awareness content — audience won't buy. Shift some to MOF/BOF.")
        elif tof_pct < self.targets["tof"] - 10:
            issues.append(f"TOF too low ({tof_pct:.0f}% vs {self.targets['tof']}% target). Not enough awareness content — audience won't grow.")

        if mof_pct > self.targets["mof"] + 10:
            issues.append(f"MOF too high ({mof_pct:.0f}% vs {self.targets['mof']}% target). Too much education without enough awareness or conversion.")
        elif mof_pct < self.targets["mof"] - 10:
            issues.append(f"MOF too low ({mof_pct:.0f}% vs {self.targets['mof']}% target). Gap between awareness and conversion — audience sees you but doesn't understand your value.")

        if bof_pct > self.targets["bof"] + 10:
            issues.append(f"BOF too high ({bof_pct:.0f}% vs {self.targets['bof']}% target). Too salesy — audience will see you as a salesperson, not an authority.")
        elif bof_pct < self.targets["bof"] - 10:
            issues.append(f"BOF too low ({bof_pct:.0f}% vs {self.targets['bof']}% target). Not converting audience to customers. Lamar Mistake #3: 'Not translating into sales.'")

        if not issues:
            return f"Funnel balanced: TOF {tof_pct:.0f}% / MOF {mof_pct:.0f}% / BOF {bof_pct:.0f}%"

        return " | ".join(issues)

    def summary(self, influencer_id: Optional[str] = None) -> str:
        """Human-readable funnel summary."""
        snap = self.get_snapshot(influencer_id)
        waitlist = self.get_waitlist_conversion(influencer_id)

        lines = [
            f"# Content Funnel — {snap.influencer_id}",
            f"Total pieces: {snap.total_pieces}",
            "",
            f"## Distribution (Target: {snap.tof_target}/{snap.mof_target}/{snap.bof_target})",
            f"  TOF: {snap.tof_count} ({snap.tof_pct}%) {'✓' if abs(snap.tof_pct - snap.tof_target) <= 10 else '✗'}",
            f"  MOF: {snap.mof_count} ({snap.mof_pct}%) {'✓' if abs(snap.mof_pct - snap.mof_target) <= 10 else '✗'}",
            f"  BOF: {snap.bof_count} ({snap.bof_pct}%) {'✓' if abs(snap.bof_pct - snap.bof_target) <= 10 else '✗'}",
            f"  Balanced: {'YES' if snap.balanced else 'NO'}",
            "",
            f"## Waitlist Conversion",
            f"  Linked to waitlist: {waitlist['linked_to_waitlist']}/{waitlist['total_pieces']} ({waitlist['link_rate']}%)",
            f"  BOF → waitlist: {waitlist['bof_linked']}/{waitlist['bof_pieces']} ({waitlist['bof_link_rate']}%)",
            "",
            f"## Recommendation",
            f"  {snap.recommendation}",
        ]
        return "\n".join(lines)

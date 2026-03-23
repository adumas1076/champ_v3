"""
Content Eval Scoring System
Binary evaluation criteria from Lamar (retention, growth, mistakes) + Gary Vee (volume).
Every piece of content is scored before publish and after publish (with analytics).

Scoring: Each criterion is YES (1) or NO (0).
Total score = passed / total × 100 = percentage.
Threshold: 75% = publishable. Below = rework. Above 90% = excellent.
"""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


# ============================================
# Evaluation Criteria — Binary (pass/fail)
# ============================================

LAMAR_RETENTION_CRITERIA = [
    {
        "id": "hook_compelling",
        "category": "retention_structure",
        "question": "Is the hook compelling enough to stop the scroll?",
        "source": "Lamar Retention System 1",
        "weight": 2,  # Critical — double weight
    },
    {
        "id": "lead_keeps_watching",
        "category": "retention_structure",
        "question": "Does the lead complement the hook and keep them watching?",
        "source": "Lamar Retention System 1",
        "weight": 1,
    },
    {
        "id": "meat_has_substance",
        "category": "retention_structure",
        "question": "Does the meat deliver actual substance (strategies, tips, stories)?",
        "source": "Lamar Retention System 1",
        "weight": 1,
    },
    {
        "id": "payoff_matches_hook",
        "category": "retention_structure",
        "question": "Does the payoff deliver on the hook's promise (not clickbait)?",
        "source": "Lamar Retention System 1",
        "weight": 2,  # Critical — clickbait = brand death
    },
    {
        "id": "time_frame_visual",
        "category": "retention_phrases",
        "question": "If time-based content: is there a visual timer on screen? (70%+ watch with sound off)",
        "source": "Lamar Retention System 2 — Type A",
        "weight": 1,
        "conditional": True,  # Only applies to time-based content
    },
    {
        "id": "foreshadowing",
        "category": "retention_phrases",
        "question": "Is foreshadowing applied? (hint at what's coming next to prevent scroll-off)",
        "source": "Lamar Retention System 2 — Type B",
        "weight": 1,
    },
    {
        "id": "real_time_thoughts",
        "category": "retention_phrases",
        "question": "Do you tell the audience what they're thinking before they think it?",
        "source": "Lamar Retention System 2 — Type C",
        "weight": 1,
    },
    {
        "id": "every_5_rule",
        "category": "retention_editing",
        "question": "Does something change every 5-10 seconds? (context, titles, captions, angles, editing)",
        "source": "Lamar Retention System 3",
        "weight": 1,
    },
    {
        "id": "visual_variety",
        "category": "retention_editing",
        "question": "Are at least 2 of 5 change types used? (context/b-roll, titles, captions, angles, editing)",
        "source": "Lamar Retention System 3",
        "weight": 1,
    },
    {
        "id": "captions_varied",
        "category": "retention_editing",
        "question": "Are captions varied in style (slide in, fade, enlarge) — not all the same?",
        "source": "Lamar Retention System 3",
        "weight": 1,
    },
    {
        "id": "not_overedited",
        "category": "retention_editing",
        "question": "Is it NOT overedited? (editing enhances, never saves bad content)",
        "source": "Lamar Retention System 4",
        "weight": 1,
    },
]

LAMAR_GROWTH_CRITERIA = [
    {
        "id": "fueled_by_one_thing",
        "category": "growth_pillars",
        "question": "Is this content fueled by the entrepreneur's 'one thing' (unique skill/trait)?",
        "source": "Lamar Growth Pillar 1",
        "weight": 2,  # Core identity — double weight
    },
    {
        "id": "24_hour_rule",
        "category": "growth_pillars",
        "question": "Can the audience implement something within 24 hours of watching?",
        "source": "Lamar Growth Pillar 2",
        "weight": 2,  # Critical — value = implementation
    },
    {
        "id": "quick_win_not_overwhelm",
        "category": "growth_pillars",
        "question": "Does it solve a SMALL problem (quick win staircase) vs. overwhelming with big problems?",
        "source": "Lamar Growth Pillar 2",
        "weight": 1,
    },
    {
        "id": "aha_moment",
        "category": "growth_pillars",
        "question": "Does it contain at least one 'blindly obvious' awareness moment (aha)?",
        "source": "Lamar Growth Pillar 3",
        "weight": 2,  # Aha = authority positioning
    },
    {
        "id": "breaks_invisible_wall",
        "category": "growth_pillars",
        "question": "Does it break the invisible wall between expert and audience?",
        "source": "Lamar Growth Pillar 3",
        "weight": 1,
    },
]

LAMAR_MISTAKES_CRITERIA = [
    {
        "id": "not_chasing_attention",
        "category": "anti_patterns",
        "question": "Is it targeting the RIGHT audience (authority) — not just chasing viral attention?",
        "source": "Lamar Mistake #1 — CRITICAL back-breaker",
        "weight": 3,  # Back-breaker — triple weight
    },
    {
        "id": "transformation_not_tips",
        "category": "anti_patterns",
        "question": "Does it create transformation (mental/belief/perspective shift) — not just list tips?",
        "source": "Lamar Mistake #2",
        "weight": 2,
    },
    {
        "id": "funnel_assigned",
        "category": "anti_patterns",
        "question": "Is it assigned to a funnel stage (TOF / MOF / BOF)?",
        "source": "Lamar Mistake #3",
        "weight": 1,
    },
    {
        "id": "expert_energy",
        "category": "anti_patterns",
        "question": "Does it reflect real-life expert energy (not guru mode / shrinking online)?",
        "source": "Lamar Mistake #4",
        "weight": 1,
    },
    {
        "id": "show_not_tell",
        "category": "anti_patterns",
        "question": "Does it SHOW (visuals, props, screen, demos) — not just talk/yap?",
        "source": "Lamar Mistake #5",
        "weight": 1,
    },
    {
        "id": "audience_not_ego",
        "category": "anti_patterns",
        "question": "Is it serving the audience's needs — not the creator's ego?",
        "source": "Lamar Mistake #6",
        "weight": 1,
    },
    {
        "id": "unique_pov",
        "category": "anti_patterns",
        "question": "Does it have a unique POV — not a pure trend copy without substance?",
        "source": "Lamar Mistake #7",
        "weight": 1,
    },
]

GARYVEE_DISTRIBUTION_CRITERIA = [
    {
        "id": "pillar_exists",
        "category": "distribution",
        "question": "Was this derived from a pillar content piece (15-30 min minimum)?",
        "source": "Gary Vee Reverse Pyramid",
        "weight": 1,
    },
    {
        "id": "long_form_distributed",
        "category": "distribution",
        "question": "Has the long-form version been distributed (YouTube, Blog, Podcast)?",
        "source": "Gary Vee Step 1",
        "weight": 1,
    },
    {
        "id": "engagement_reviewed",
        "category": "distribution",
        "question": "Has engagement data been reviewed within 48 hours to inform micro cuts?",
        "source": "Gary Vee Step 2 — Listen",
        "weight": 1,
    },
    {
        "id": "micro_clips_cut",
        "category": "distribution",
        "question": "Have Round 1 micro clips (2-4 min) been cut and distributed?",
        "source": "Gary Vee Step 3",
        "weight": 1,
    },
    {
        "id": "micro_micro_queued",
        "category": "distribution",
        "question": "Have Round 2 micro-micro clips (60s/30s/<30s) + statics been queued?",
        "source": "Gary Vee Step 4",
        "weight": 1,
    },
    {
        "id": "subtitles_on",
        "category": "distribution",
        "question": "Do all video pieces have subtitles/captions? (70%+ watch with sound off)",
        "source": "Gary Vee + Lamar cross-reference",
        "weight": 1,
    },
    {
        "id": "headline_overlay",
        "category": "distribution",
        "question": "Do clips have a headline/title overlay for scrollers?",
        "source": "Gary Vee platform optimization",
        "weight": 1,
    },
]

# All criteria combined
ALL_CRITERIA = (
    LAMAR_RETENTION_CRITERIA
    + LAMAR_GROWTH_CRITERIA
    + LAMAR_MISTAKES_CRITERIA
    + GARYVEE_DISTRIBUTION_CRITERIA
)


# ============================================
# Score Card
# ============================================

@dataclass
class CriterionResult:
    """Result for a single evaluation criterion."""
    criterion_id: str
    passed: bool
    note: Optional[str] = None


@dataclass
class ContentScoreCard:
    """Complete evaluation of a content piece."""
    content_id: str
    influencer_id: str
    content_type: str               # pillar | micro | micro_micro | static
    funnel_stage: str               # tof | mof | bof
    platform: str                   # youtube | instagram | tiktok | linkedin | twitter
    results: list[CriterionResult] = field(default_factory=list)
    total_score: float = 0.0
    max_score: float = 0.0
    percentage: float = 0.0
    verdict: str = "pending"        # excellent | publishable | rework | reject
    scored_at: Optional[str] = None
    notes: str = ""

    def calculate(self):
        """Calculate total score and verdict from results."""
        criteria_map = {c["id"]: c for c in ALL_CRITERIA}
        self.total_score = 0.0
        self.max_score = 0.0
        for r in self.results:
            weight = criteria_map.get(r.criterion_id, {}).get("weight", 1)
            self.max_score += weight
            if r.passed:
                self.total_score += weight
        self.percentage = (self.total_score / self.max_score * 100) if self.max_score > 0 else 0
        if self.percentage >= 90:
            self.verdict = "excellent"
        elif self.percentage >= 75:
            self.verdict = "publishable"
        elif self.percentage >= 50:
            self.verdict = "rework"
        else:
            self.verdict = "reject"
        self.scored_at = datetime.utcnow().isoformat()

    def failing_criteria(self) -> list[dict]:
        """Return criteria that failed — these need fixing."""
        criteria_map = {c["id"]: c for c in ALL_CRITERIA}
        failures = []
        for r in self.results:
            if not r.passed and r.criterion_id in criteria_map:
                c = criteria_map[r.criterion_id]
                failures.append({
                    "id": c["id"],
                    "question": c["question"],
                    "source": c["source"],
                    "weight": c["weight"],
                    "note": r.note,
                })
        return sorted(failures, key=lambda x: x["weight"], reverse=True)

    def summary(self) -> str:
        """Human-readable summary of the score."""
        lines = [
            f"Score: {self.total_score}/{self.max_score} ({self.percentage:.0f}%) — {self.verdict.upper()}",
            f"Content: {self.content_id} | Type: {self.content_type} | Funnel: {self.funnel_stage} | Platform: {self.platform}",
        ]
        failures = self.failing_criteria()
        if failures:
            lines.append(f"\nFailing ({len(failures)}):")
            for f in failures:
                lines.append(f"  [{f['weight']}x] {f['question']}")
                if f["note"]:
                    lines.append(f"        Note: {f['note']}")
        return "\n".join(lines)


# ============================================
# Scoring Functions
# ============================================

def get_pre_publish_criteria(content_type: str = "micro") -> list[dict]:
    """Get criteria applicable before publishing.

    Pre-publish = Lamar Retention + Lamar Growth + Lamar Mistakes.
    Distribution criteria are post-publish (require analytics).
    """
    criteria = LAMAR_RETENTION_CRITERIA + LAMAR_GROWTH_CRITERIA + LAMAR_MISTAKES_CRITERIA
    # Filter conditional criteria for non-time-based content
    return [c for c in criteria if not c.get("conditional", False) or content_type in ("pillar", "micro")]


def get_post_publish_criteria() -> list[dict]:
    """Get criteria applicable after publishing (distribution + analytics)."""
    return GARYVEE_DISTRIBUTION_CRITERIA


def get_all_criteria() -> list[dict]:
    """Get all evaluation criteria."""
    return ALL_CRITERIA


def score_content(
    content_id: str,
    influencer_id: str,
    content_type: str,
    funnel_stage: str,
    platform: str,
    answers: dict[str, bool],
    notes: Optional[dict[str, str]] = None,
) -> ContentScoreCard:
    """Score a content piece against all applicable criteria.

    Args:
        content_id: Unique identifier for the content piece
        influencer_id: Which influencer this belongs to
        content_type: pillar | micro | micro_micro | static
        funnel_stage: tof | mof | bof
        platform: youtube | instagram | tiktok | linkedin | twitter
        answers: Dict of {criterion_id: True/False}
        notes: Optional dict of {criterion_id: "note about why"}

    Returns:
        ContentScoreCard with calculated scores and verdict
    """
    notes = notes or {}
    card = ContentScoreCard(
        content_id=content_id,
        influencer_id=influencer_id,
        content_type=content_type,
        funnel_stage=funnel_stage,
        platform=platform,
    )
    for criterion in ALL_CRITERIA:
        cid = criterion["id"]
        if cid in answers:
            card.results.append(CriterionResult(
                criterion_id=cid,
                passed=answers[cid],
                note=notes.get(cid),
            ))
    card.calculate()
    return card


def build_eval_prompt(content_type: str = "micro") -> str:
    """Build a prompt for LLM-based content evaluation.

    Used by the Marketing Operator to self-evaluate content
    before publishing. Returns a structured prompt with all
    binary criteria as yes/no questions.
    """
    criteria = get_pre_publish_criteria(content_type)
    lines = [
        "# Content Quality Evaluation",
        "Score each criterion as YES (passes) or NO (fails).",
        "Be honest — quality at scale requires honest self-assessment.",
        "",
        "## Criteria",
        "",
    ]
    for i, c in enumerate(criteria, 1):
        lines.append(f"{i}. [{c['id']}] {c['question']}")
        lines.append(f"   Source: {c['source']} | Weight: {c['weight']}x")
        lines.append("")
    lines.extend([
        "## Response Format",
        "Return JSON:",
        "```json",
        "{",
        '  "answers": {"criterion_id": true/false, ...},',
        '  "notes": {"criterion_id": "why it failed", ...},',
        '  "overall_impression": "one sentence"',
        "}",
        "```",
    ])
    return "\n".join(lines)

"""
Assessment / Scorecard System — Priestley Lead Gen Framework

"Sell the assessment, not the solution." (Daniel Priestley)

People need to be 90% sure to buy, but only 10-20% sure to fill in an assessment.
So assessments capture 5-10x more leads than direct sales CTAs. Then the
assessment itself:
  1. Segments buyers into a pyramid (top 10% vs base)
  2. Creates transparency ("X took this, top scored Y%")
  3. Diagnoses problems the buyer didn't know they had
  4. Builds Market Forces (supply/demand tension)
  5. Filters serious from curious
  6. Begins mental adoption of the solution

Each influencer has their own "Are you ready for X?" readiness assessment.

Flow:
  Stranger fills in assessment → answers 20-40 questions →
  Gets score + report + recommendations → Captured as lead with segmentation data →
  Welcome email with PDF report → Optional: booked to waitlist or upsold

This maps to Business Matrix entry 0010 (Priestley Lead Gen).

Required env vars (same as waitlist):
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
  RESEND_API_KEY
"""

import os
import logging
import uuid
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional
from enum import Enum

logger = logging.getLogger(__name__)


# ============================================
# Data Models
# ============================================

class QuestionType(str, Enum):
    YES_NO = "yes_no"              # 1 point if yes, 0 if no
    SCALE = "scale"                # 1-5 scale, weighted
    MULTIPLE_CHOICE = "multiple_choice"  # each option has weight
    OPEN_TEXT = "open_text"        # for segmentation data, not scored


@dataclass
class AssessmentQuestion:
    """A single assessment question."""
    id: str                        # "brand_identity_1"
    category: str                  # "brand_identity", "audience", "positioning"
    text: str                      # The question itself
    type: QuestionType
    weight: int = 1                # Multiplier for scoring (1-3x)
    options: list = field(default_factory=list)  # For multiple choice: [{label, value, score}]
    segmentation: bool = False     # If true, used for segmenting (not scoring)


@dataclass
class AssessmentDefinition:
    """A complete assessment/scorecard configuration."""
    id: str                        # "rebrand_readiness", "ai_readiness", etc.
    name: str                      # "Are You Ready for a Rebrand?"
    influencer_id: str             # Which influencer owns this assessment
    description: str
    intro_text: str                # Shown before the assessment starts
    questions: list[AssessmentQuestion] = field(default_factory=list)
    # Scoring tiers — matches Click to Client framework (TOFU/MOFU/BOFU)
    # cold = TOFU  | warm = MOFU  | hot = BOFU  | buyer = BOFU+
    tier_thresholds: dict = field(default_factory=lambda: {
        "buyer": 80,       # 80-100% — Ready to buy now. Route to Sales. Speed-to-lead <60s.
        "hot": 60,         # 60-80%  — Close the 1-2 gaps and they convert. BOFU.
        "warm": 30,        # 30-60%  — Build trust. Nurture sequence. MOFU.
        "cold": 0,         # 0-30%   — Educate first. Content drip. TOFU.
    })
    # Results content per tier
    tier_messages: dict = field(default_factory=dict)
    # Call to action per tier
    tier_ctas: dict = field(default_factory=dict)


@dataclass
class AssessmentResponse:
    """A user's responses to an assessment."""
    id: str
    assessment_id: str
    respondent_email: str
    respondent_name: Optional[str] = None
    # Source tracking
    source_platform: Optional[str] = None
    source_influencer: Optional[str] = None
    source_campaign: Optional[str] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_content: Optional[str] = None
    # Answers
    answers: dict = field(default_factory=dict)    # question_id → answer
    segmentation_data: dict = field(default_factory=dict)  # question_id → open text
    # Scoring
    raw_score: float = 0.0
    max_score: float = 0.0
    percentage: float = 0.0
    tier: str = "pending"
    # Metadata
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    completed: bool = False


# ============================================
# 4 Pre-Built Assessments (one per influencer)
# ============================================

def _anthony_assessment() -> AssessmentDefinition:
    """Anthony's AI Readiness Scorecard — Face 0 primary assessment."""
    return AssessmentDefinition(
        id="ai_readiness",
        name="Are You Ready to Run Your Business on AI?",
        influencer_id="anthony",
        description="Find out if your business is ready for an AI operator team",
        intro_text=(
            "20 questions. Takes 3 minutes. You'll get a personalized AI Readiness Score "
            "and a breakdown of what's working, what's broken, and where AI operators "
            "would move the needle fastest for YOUR business."
        ),
        questions=[
            # --- Business Foundation ---
            AssessmentQuestion("af_1", "foundation", "Do you have documented processes for your core operations?", QuestionType.YES_NO, weight=2),
            AssessmentQuestion("af_2", "foundation", "Is your team size 1-10 (where AI leverage hits hardest)?", QuestionType.YES_NO, weight=1),
            AssessmentQuestion("af_3", "foundation", "Monthly revenue: is it above $10K?", QuestionType.YES_NO, weight=3),
            AssessmentQuestion("af_4", "foundation", "Do you have a clear ideal customer profile?", QuestionType.YES_NO, weight=2),

            # --- Marketing & Sales ---
            AssessmentQuestion("ms_1", "marketing", "Do you have a consistent content posting schedule?", QuestionType.YES_NO, weight=1),
            AssessmentQuestion("ms_2", "marketing", "Are you posting across 3+ platforms currently?", QuestionType.YES_NO, weight=1),
            AssessmentQuestion("ms_3", "marketing", "Do you have a defined sales process (script/framework)?", QuestionType.YES_NO, weight=2),
            AssessmentQuestion("ms_4", "marketing", "Do you track content performance with analytics?", QuestionType.YES_NO, weight=1),

            # --- Bottlenecks ---
            AssessmentQuestion("bn_1", "bottleneck", "Are you the main bottleneck in your business?", QuestionType.YES_NO, weight=3),
            AssessmentQuestion("bn_2", "bottleneck", "Do you spend 10+ hours/week on tasks a team could handle?", QuestionType.YES_NO, weight=3),
            AssessmentQuestion("bn_3", "bottleneck", "Are leads falling through cracks because follow-up is slow?", QuestionType.YES_NO, weight=2),
            AssessmentQuestion("bn_4", "bottleneck", "Is your content output limited by your available time?", QuestionType.YES_NO, weight=2),

            # --- Tech Readiness ---
            AssessmentQuestion("tr_1", "tech", "Are you already using AI tools (ChatGPT, Claude, Copilot)?", QuestionType.YES_NO, weight=1),
            AssessmentQuestion("tr_2", "tech", "Comfortable connecting tools via OAuth (Google, social, etc.)?", QuestionType.YES_NO, weight=1),
            AssessmentQuestion("tr_3", "tech", "Have you automated any business processes already?", QuestionType.YES_NO, weight=1),

            # --- Urgency ---
            AssessmentQuestion("ur_1", "urgency", "Are competitors using AI in ways that concern you?", QuestionType.YES_NO, weight=2),
            AssessmentQuestion("ur_2", "urgency", "Do you believe AI changes the game in your industry?", QuestionType.YES_NO, weight=2),
            AssessmentQuestion("ur_3", "urgency", "Are you ready to invest in AI infrastructure this quarter?", QuestionType.YES_NO, weight=3),

            # --- Segmentation (not scored, used for personalization) ---
            AssessmentQuestion("sg_1", "segmentation", "What's the biggest bottleneck in your business right now?",
                             QuestionType.OPEN_TEXT, segmentation=True),
            AssessmentQuestion("sg_2", "segmentation", "What industry are you in?",
                             QuestionType.OPEN_TEXT, segmentation=True),
        ],
        tier_messages={
            "buyer": "You're ready. Your business is set up to get massive leverage from AI operators — the foundations are in place and the bottlenecks are clear.",
            "hot": "You're close. A few gaps to close, but you'll get strong ROI from AI operators within 90 days of implementation.",
            "warm": "Foundations first. You'll benefit from AI operators, but fixing 2-3 gaps will 10x the impact. We'll show you which ones.",
            "cold": "Too early right now. Focus on the basics first. Come back when you've built the fundamentals — AI operators amplify what works, not what's broken.",
        },
        tier_ctas={
            "buyer": "Book a 15-min strategy call — let's map your AI operator team",
            "hot": "Join the Marketing Machine waitlist — you'll be first in line",
            "warm": "Get the AI Readiness Roadmap PDF — the 5 gaps to close first",
            "cold": "Follow the build — we're documenting everything publicly",
        },
    )


def _tech_influencer_assessment() -> AssessmentDefinition:
    """Influencer 1 (Alex/The Builder) — Tech Stack Assessment."""
    return AssessmentDefinition(
        id="ai_stack_readiness",
        name="Is Your AI Tech Stack Built Right?",
        influencer_id="influencer_1",
        description="Audit your AI tool stack — find gaps, overlaps, and leverage opportunities",
        intro_text="15 questions. 2 minutes. Find out if your AI stack is set up for leverage or chaos.",
        questions=[
            AssessmentQuestion("s_1", "stack", "Are you using 3+ AI tools daily?", QuestionType.YES_NO, weight=1),
            AssessmentQuestion("s_2", "stack", "Do your tools share data automatically?", QuestionType.YES_NO, weight=2),
            AssessmentQuestion("s_3", "stack", "Is there a single source of truth for customer data?", QuestionType.YES_NO, weight=2),
            AssessmentQuestion("s_4", "stack", "Can you replace any single tool without breaking the stack?", QuestionType.YES_NO, weight=2),
            AssessmentQuestion("s_5", "stack", "Are you paying for features you don't use?", QuestionType.YES_NO, weight=1),
            AssessmentQuestion("w_1", "workflow", "Do you have automated workflows (not just prompts)?", QuestionType.YES_NO, weight=2),
            AssessmentQuestion("w_2", "workflow", "Is AI part of your daily workflow or ad-hoc?", QuestionType.YES_NO, weight=1),
            AssessmentQuestion("w_3", "workflow", "Have you built anything custom (API/scripts)?", QuestionType.YES_NO, weight=2),
            AssessmentQuestion("v_1", "vision", "Do you have a 12-month AI roadmap?", QuestionType.YES_NO, weight=1),
            AssessmentQuestion("v_2", "vision", "Are you building or buying AI capabilities?", QuestionType.YES_NO, weight=1),
            AssessmentQuestion("v_3", "vision", "Is your team AI-literate?", QuestionType.YES_NO, weight=2),
            AssessmentQuestion("sg_1", "segmentation", "What AI tools do you use most?", QuestionType.OPEN_TEXT, segmentation=True),
            AssessmentQuestion("sg_2", "segmentation", "What are you building right now?", QuestionType.OPEN_TEXT, segmentation=True),
        ],
        tier_messages={
            "buyer": "Your stack is solid. You're ready to build custom AI infrastructure.",
            "hot": "Strong foundation. A few integrations away from serious leverage.",
            "warm": "Time to consolidate. You've got tools — now connect them.",
            "cold": "Start with the basics. Pick 3 tools, learn them deep, then add.",
        },
        tier_ctas={
            "buyer": "DM 'BUILD' for the Advanced Stack Breakdown",
            "hot": "Get the AI Stack Blueprint — 15 tools + how they connect",
            "warm": "Join the waitlist for the Stack Audit Workshop",
            "cold": "Follow for beginner-friendly tool walkthroughs",
        },
    )


def _business_influencer_assessment() -> AssessmentDefinition:
    """Influencer 2 (Marcus/The Operator) — Business Diagnostic."""
    return AssessmentDefinition(
        id="scale_readiness",
        name="Is Your Business Ready to Scale?",
        influencer_id="influencer_2",
        description="Diagnose the 5 systems that determine if your business can scale",
        intro_text="25 questions. 4 minutes. Get your Scale Readiness Score across 5 systems.",
        questions=[
            AssessmentQuestion("o_1", "offer", "Do you have a clear, single-sentence value proposition?", QuestionType.YES_NO, weight=2),
            AssessmentQuestion("o_2", "offer", "Is your price higher than your top competitor?", QuestionType.YES_NO, weight=1),
            AssessmentQuestion("o_3", "offer", "Do you have a guarantee or risk-reversal?", QuestionType.YES_NO, weight=1),
            AssessmentQuestion("o_4", "offer", "Can you explain ROI to a customer in 30 seconds?", QuestionType.YES_NO, weight=2),
            AssessmentQuestion("l_1", "leads", "Do you generate 20+ qualified leads per week?", QuestionType.YES_NO, weight=2),
            AssessmentQuestion("l_2", "leads", "Do you have a documented lead capture process?", QuestionType.YES_NO, weight=1),
            AssessmentQuestion("l_3", "leads", "Is your cost per lead below your target?", QuestionType.YES_NO, weight=2),
            AssessmentQuestion("s_1", "sales", "Do you have a repeatable sales process (CLOSER/etc)?", QuestionType.YES_NO, weight=3),
            AssessmentQuestion("s_2", "sales", "Is your close rate tracked per stage?", QuestionType.YES_NO, weight=2),
            AssessmentQuestion("s_3", "sales", "Can someone else close sales for you?", QuestionType.YES_NO, weight=2),
            AssessmentQuestion("d_1", "delivery", "Do you have documented delivery SOPs?", QuestionType.YES_NO, weight=2),
            AssessmentQuestion("d_2", "delivery", "Is delivery handled without your direct involvement?", QuestionType.YES_NO, weight=2),
            AssessmentQuestion("d_3", "delivery", "Do you measure customer outcomes?", QuestionType.YES_NO, weight=1),
            AssessmentQuestion("r_1", "retention", "Do customers stay 12+ months?", QuestionType.YES_NO, weight=2),
            AssessmentQuestion("r_2", "retention", "Do you have a referral program?", QuestionType.YES_NO, weight=1),
            AssessmentQuestion("r_3", "retention", "Is your LTV > 3x CAC?", QuestionType.YES_NO, weight=3),
            AssessmentQuestion("sg_1", "segmentation", "What's your monthly revenue?", QuestionType.OPEN_TEXT, segmentation=True),
            AssessmentQuestion("sg_2", "segmentation", "What's the #1 thing blocking scale?", QuestionType.OPEN_TEXT, segmentation=True),
        ],
        tier_messages={
            "buyer": "Scale machine. All 5 systems are operational. Now it's about multipliers.",
            "hot": "Strong fundamentals. 1-2 systems to tighten and you're scale-ready.",
            "warm": "Good foundation, leaky bucket. Focus on retention + sales process.",
            "cold": "Pre-scale stage. Nail the offer first. Everything else compounds off that.",
        },
        tier_ctas={
            "buyer": "DM 'SCALE' for the Scale Operators blueprint",
            "hot": "Get the Business Diagnostic PDF with your gap analysis",
            "warm": "Join the waitlist — the Scale Readiness workshop is coming",
            "cold": "Follow for offer design frameworks",
        },
    )


def _creative_influencer_assessment() -> AssessmentDefinition:
    """Influencer 3 (Sage/The Director) — Brand Audit."""
    return AssessmentDefinition(
        id="brand_readiness",
        name="Does Your Brand Actually Convert?",
        influencer_id="influencer_3",
        description="Audit your brand across 20 conversion-critical dimensions",
        intro_text="20 questions. 3 minutes. See if your brand is built to attract or built to sell.",
        questions=[
            AssessmentQuestion("id_1", "identity", "Can you describe your brand in one sentence?", QuestionType.YES_NO, weight=2),
            AssessmentQuestion("id_2", "identity", "Is your visual identity consistent across all platforms?", QuestionType.YES_NO, weight=2),
            AssessmentQuestion("id_3", "identity", "Does your brand have a documented voice/tone?", QuestionType.YES_NO, weight=1),
            AssessmentQuestion("id_4", "identity", "Would your top 10 customers describe your brand the same way?", QuestionType.YES_NO, weight=2),
            AssessmentQuestion("po_1", "positioning", "Is your ideal customer clear about what you do?", QuestionType.YES_NO, weight=2),
            AssessmentQuestion("po_2", "positioning", "Can you name your top 3 competitors?", QuestionType.YES_NO, weight=1),
            AssessmentQuestion("po_3", "positioning", "Do you have a unique angle no competitor owns?", QuestionType.YES_NO, weight=3),
            AssessmentQuestion("po_4", "positioning", "Is your pricing positioned premium, mid, or low — intentionally?", QuestionType.YES_NO, weight=1),
            AssessmentQuestion("co_1", "content", "Does your content convert to leads?", QuestionType.YES_NO, weight=2),
            AssessmentQuestion("co_2", "content", "Do you have branded content templates?", QuestionType.YES_NO, weight=1),
            AssessmentQuestion("co_3", "content", "Is your content tied to your offer?", QuestionType.YES_NO, weight=2),
            AssessmentQuestion("ex_1", "experience", "Does your customer journey feel branded from start to finish?", QuestionType.YES_NO, weight=2),
            AssessmentQuestion("ex_2", "experience", "Do you have branded onboarding?", QuestionType.YES_NO, weight=1),
            AssessmentQuestion("ex_3", "experience", "Would clients recognize your brand if the logo was removed?", QuestionType.YES_NO, weight=2),
            AssessmentQuestion("sg_1", "segmentation", "What industry is your brand in?", QuestionType.OPEN_TEXT, segmentation=True),
            AssessmentQuestion("sg_2", "segmentation", "What's your brand's biggest challenge?", QuestionType.OPEN_TEXT, segmentation=True),
        ],
        tier_messages={
            "buyer": "Brand converts. You're in the top tier — now optimize for Market Force.",
            "hot": "Strong brand, conversion gaps. Tighten 2-3 dimensions for compound gains.",
            "warm": "Brand exists, positioning is soft. Start with the one-sentence test.",
            "cold": "Pre-brand stage. Nail who you serve first — identity follows positioning.",
        },
        tier_ctas={
            "buyer": "DM 'BRAND' for the Brand Conversion Playbook",
            "hot": "Get the Brand Audit Report — your gap analysis + fixes",
            "warm": "Join the waitlist for the Brand Workshop",
            "cold": "Follow for brand fundamentals and case studies",
        },
    )


# Registry of all assessments
ASSESSMENTS = {
    "ai_readiness": _anthony_assessment(),
    "ai_stack_readiness": _tech_influencer_assessment(),
    "scale_readiness": _business_influencer_assessment(),
    "brand_readiness": _creative_influencer_assessment(),
}


def get_assessment(assessment_id: str) -> Optional[AssessmentDefinition]:
    """Get an assessment by ID."""
    return ASSESSMENTS.get(assessment_id)


def list_assessments() -> list[dict]:
    """List all available assessments (for a landing page picker)."""
    return [
        {
            "id": a.id,
            "name": a.name,
            "influencer_id": a.influencer_id,
            "description": a.description,
            "question_count": len(a.questions),
        }
        for a in ASSESSMENTS.values()
    ]


# ============================================
# Scoring Engine
# ============================================

def score_assessment(
    definition: AssessmentDefinition,
    answers: dict,
) -> tuple[float, float, str]:
    """Score an assessment response.

    Returns: (raw_score, max_score, tier)
    """
    raw_score = 0.0
    max_score = 0.0

    for q in definition.questions:
        if q.segmentation or q.type == QuestionType.OPEN_TEXT:
            continue

        answer = answers.get(q.id)
        if answer is None:
            continue

        max_score += q.weight

        if q.type == QuestionType.YES_NO:
            if answer in (True, "yes", "Yes", "YES", 1, "1"):
                raw_score += q.weight
        elif q.type == QuestionType.SCALE:
            try:
                scale_val = float(answer)
                # Normalize 1-5 to 0-1, multiply by weight
                normalized = max(0, min(1, (scale_val - 1) / 4))
                raw_score += normalized * q.weight
            except (ValueError, TypeError):
                pass
        elif q.type == QuestionType.MULTIPLE_CHOICE:
            for option in q.options:
                if option.get("value") == answer:
                    raw_score += option.get("score", 0) * q.weight
                    break

    percentage = (raw_score / max_score * 100) if max_score > 0 else 0

    # Determine tier — check highest first, cold is fallback
    tier = "cold"
    for tier_name in ["buyer", "hot", "warm", "cold"]:
        if percentage >= definition.tier_thresholds.get(tier_name, 0):
            tier = tier_name
            break

    return raw_score, max_score, tier


# ============================================
# Supabase Storage
# ============================================

def _get_supabase():
    """Reuse waitlist's Supabase client."""
    from content_engine.capture.waitlist import _get_supabase as _get
    return _get()


async def store_response(response: AssessmentResponse) -> bool:
    """Store an assessment response in Supabase.

    Table: assessment_responses
      CREATE TABLE assessment_responses (
        id UUID PRIMARY KEY,
        assessment_id TEXT NOT NULL,
        respondent_email TEXT NOT NULL,
        respondent_name TEXT,
        source_platform TEXT,
        source_influencer TEXT,
        answers JSONB,
        segmentation_data JSONB,
        raw_score FLOAT,
        max_score FLOAT,
        percentage FLOAT,
        tier TEXT,
        utm_source TEXT,
        utm_medium TEXT,
        utm_content TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
      );
    """
    client = _get_supabase()
    if not client:
        logger.error("[ASSESSMENT] Supabase not available")
        return False

    try:
        data = {
            "id": response.id,
            "assessment_id": response.assessment_id,
            "respondent_email": response.respondent_email,
            "respondent_name": response.respondent_name,
            "source_platform": response.source_platform,
            "source_influencer": response.source_influencer,
            "source_campaign": response.source_campaign,
            "answers": response.answers,
            "segmentation_data": response.segmentation_data,
            "raw_score": response.raw_score,
            "max_score": response.max_score,
            "percentage": response.percentage,
            "tier": response.tier,
            "utm_source": response.utm_source,
            "utm_medium": response.utm_medium,
            "utm_content": response.utm_content,
            "created_at": response.created_at,
        }
        data = {k: v for k, v in data.items() if v is not None}

        client.table("assessment_responses").insert(data).execute()
        logger.info(
            f"[ASSESSMENT] {response.respondent_email} scored {response.percentage:.0f}% "
            f"on {response.assessment_id} → tier: {response.tier}"
        )
        return True
    except Exception as e:
        logger.error(f"[ASSESSMENT] Failed to store response: {e}")
        return False


async def get_assessment_stats(assessment_id: str) -> dict:
    """Get transparency stats for an assessment.

    Returns: {
        "total_completions": int,
        "by_tier": {"premium": int, "qualified": int, ...},
        "avg_score": float,
        "top_10_threshold": float,
    }

    Used to display "X people have taken this, top 10% scored above Y%".
    """
    client = _get_supabase()
    if not client:
        return {}

    try:
        result = client.table("assessment_responses").select(
            "percentage, tier"
        ).eq("assessment_id", assessment_id).execute()

        responses = result.data or []
        if not responses:
            return {
                "total_completions": 0,
                "by_tier": {},
                "avg_score": 0,
                "top_10_threshold": 0,
            }

        total = len(responses)
        by_tier = {}
        scores = []
        for r in responses:
            tier = r.get("tier", "unknown")
            by_tier[tier] = by_tier.get(tier, 0) + 1
            if r.get("percentage") is not None:
                scores.append(r["percentage"])

        scores.sort(reverse=True)
        top_10_count = max(1, total // 10)
        top_10_threshold = scores[top_10_count - 1] if scores else 0

        return {
            "total_completions": total,
            "by_tier": by_tier,
            "avg_score": round(sum(scores) / len(scores), 1) if scores else 0,
            "top_10_threshold": round(top_10_threshold, 1),
        }
    except Exception as e:
        logger.warning(f"[ASSESSMENT] Failed to get stats: {e}")
        return {}


# ============================================
# Main Submission Flow
# ============================================

async def submit_assessment(
    assessment_id: str,
    email: str,
    answers: dict,
    name: Optional[str] = None,
    source_platform: Optional[str] = None,
    source_influencer: Optional[str] = None,
    source_campaign: Optional[str] = None,
    utm_source: Optional[str] = None,
    utm_medium: Optional[str] = None,
    utm_content: Optional[str] = None,
) -> dict:
    """Submit a completed assessment.

    Flow:
      1. Score the answers
      2. Store the response in Supabase
      3. Also add to waitlist (dual capture — assessment + waitlist)
      4. Send results email via Resend
      5. Return results payload for immediate display on results page

    Returns a dict with: tier, percentage, message, cta, stats
    """
    definition = get_assessment(assessment_id)
    if not definition:
        return {"success": False, "error": f"Unknown assessment: {assessment_id}"}

    # Split answers into scored and segmentation
    scored_answers = {}
    segmentation = {}
    for q in definition.questions:
        if q.id in answers:
            if q.segmentation or q.type == QuestionType.OPEN_TEXT:
                segmentation[q.id] = answers[q.id]
            else:
                scored_answers[q.id] = answers[q.id]

    # Score it
    raw, max_s, tier = score_assessment(definition, scored_answers)
    percentage = (raw / max_s * 100) if max_s > 0 else 0

    response = AssessmentResponse(
        id=uuid.uuid4().hex,
        assessment_id=assessment_id,
        respondent_email=email,
        respondent_name=name,
        source_platform=source_platform,
        source_influencer=source_influencer or definition.influencer_id,
        source_campaign=source_campaign or f"assessment_{assessment_id}",
        utm_source=utm_source,
        utm_medium=utm_medium,
        utm_content=utm_content,
        answers=scored_answers,
        segmentation_data=segmentation,
        raw_score=raw,
        max_score=max_s,
        percentage=percentage,
        tier=tier,
        completed=True,
    )

    # Store response
    stored = await store_response(response)

    # Dual capture: also add to waitlist
    from content_engine.capture.waitlist import capture_waitlist_lead, WaitlistEntry
    waitlist_entry = WaitlistEntry(
        email=email,
        name=name,
        source_platform=source_platform,
        source_influencer=source_influencer or definition.influencer_id,
        source_campaign=source_campaign or f"assessment_{assessment_id}",
        utm_source=utm_source,
        utm_medium=utm_medium,
        utm_content=utm_content or tier,  # Track tier in UTM content
    )
    # Pass source_content_id so the graph tracks which content drove the lead
    waitlist_result = await capture_waitlist_lead(waitlist_entry, source_content_id=utm_content or "")

    # Write assessment-specific lead to graph (with tier — the V1 high-value path)
    try:
        from content_engine import graph_writer
        graph_writer.record_assessment_lead(
            lead_id=response.id,
            email=email,
            tier=tier,
            assessment_id=assessment_id,
            percentage=percentage,
            source_content_id=utm_content or "",
            source_influencer_id=source_influencer or definition.influencer_id,
            metadata={
                "name": name,
                "source_platform": source_platform,
                "segmentation": segmentation,
                "utm_campaign": source_campaign,
            },
        )
    except Exception as e:
        logger.warning(f"[ASSESSMENT] Graph write failed (non-fatal): {e}")

    # Send personalized results email
    await _send_results_email(response, definition)

    # Get transparency stats for Market Forces display
    stats = await get_assessment_stats(assessment_id)

    return {
        "success": stored,
        "tier": tier,
        "percentage": round(percentage, 1),
        "raw_score": raw,
        "max_score": max_s,
        "message": definition.tier_messages.get(tier, ""),
        "cta": definition.tier_ctas.get(tier, ""),
        "stats": stats,
        "response_id": response.id,
    }


async def _send_results_email(
    response: AssessmentResponse,
    definition: AssessmentDefinition,
) -> bool:
    """Send personalized results email with score + recommendations."""
    api_key = os.getenv("RESEND_API_KEY")
    if not api_key:
        return False

    try:
        import httpx

        from_name = os.getenv("RESEND_FROM_NAME", "Cocreatiq")
        from_email = os.getenv("RESEND_FROM_EMAIL", "hello@cocreatiq.com")

        name = response.respondent_name or "there"
        tier_name = response.tier.upper()
        message = definition.tier_messages.get(response.tier, "")
        cta = definition.tier_ctas.get(response.tier, "")

        html_body = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 40px 20px;">
            <h1 style="font-size: 28px; margin-bottom: 8px;">Your {definition.name} Score</h1>
            <p style="font-size: 18px; color: #666; margin-bottom: 24px;">Hey {name} — here's what we found.</p>

            <div style="background: #f5f5f5; padding: 24px; border-radius: 12px; margin-bottom: 24px;">
                <div style="font-size: 48px; font-weight: bold; margin-bottom: 8px;">{response.percentage:.0f}%</div>
                <div style="font-size: 20px; font-weight: bold; color: #0066cc;">Tier: {tier_name}</div>
            </div>

            <h2 style="font-size: 22px; margin-top: 32px; margin-bottom: 12px;">What This Means</h2>
            <p style="font-size: 16px; line-height: 1.6; color: #333;">{message}</p>

            <h2 style="font-size: 22px; margin-top: 32px; margin-bottom: 12px;">Your Next Step</h2>
            <p style="font-size: 16px; line-height: 1.6; color: #333;"><strong>{cta}</strong></p>

            <p style="font-size: 14px; line-height: 1.6; color: #888; margin-top: 40px; border-top: 1px solid #eee; padding-top: 16px;">
                This score was generated from your answers to {len(definition.questions)} questions.
                Want a deeper breakdown? Reply to this email and we'll send you a custom analysis.
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
                    "to": [response.respondent_email],
                    "subject": f"Your {definition.name} results — {tier_name} tier ({response.percentage:.0f}%)",
                    "html": html_body,
                },
            )

            if resp.status_code in (200, 201):
                logger.info(f"[ASSESSMENT] Results email sent to {response.respondent_email}")
                return True
            else:
                logger.error(f"[ASSESSMENT] Resend error {resp.status_code}: {resp.text[:200]}")
                return False

    except Exception as e:
        logger.error(f"[ASSESSMENT] Failed to send results email: {e}")
        return False


# ============================================
# Public Helpers (for landing page / API)
# ============================================

def get_assessment_questions(assessment_id: str) -> Optional[dict]:
    """Get the questions payload for a landing page to render."""
    definition = get_assessment(assessment_id)
    if not definition:
        return None

    return {
        "id": definition.id,
        "name": definition.name,
        "description": definition.description,
        "intro_text": definition.intro_text,
        "questions": [
            {
                "id": q.id,
                "category": q.category,
                "text": q.text,
                "type": q.type.value,
                "options": q.options,
            }
            for q in definition.questions
        ],
    }

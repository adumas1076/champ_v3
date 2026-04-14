# ============================================
# Conversation Matrix — Conversation Scorer
# Tier 1: Regex quick check (every turn, <5ms)
# Tier 2: LLM deep scoring (sampled, async)
# ============================================

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ScoringResult:
    """Result of conversation scoring."""
    passed: bool = True
    violations: list[dict] = field(default_factory=list)
    warnings: list[dict] = field(default_factory=list)
    feedback: str = ""
    composite_score: float = -1.0  # -1 = not deep scored


# ---- Absolute Violations (instant fail → regenerate) ----

ABSOLUTE_VIOLATIONS: dict[str, dict] = {
    "numbered_list": {
        "pattern": re.compile(r"^\s*\d+[\.\)]\s", re.MULTILINE),
        "channels": ["voice", "text"],
        "skip_modes": ["spec"],
        "feedback": "Never use numbered lists in conversation. Rewrite using stories or natural flow.",
    },
    "bullet_points_voice": {
        "pattern": re.compile(r"^\s*[-•]\s", re.MULTILINE),
        "channels": ["voice"],
        "skip_modes": ["spec", "build"],
        "feedback": "No bullet points in voice. Use natural speech flow.",
    },
    "great_question": {
        "pattern": re.compile(r"\bgreat question\b", re.IGNORECASE),
        "channels": ["all"],
        "skip_modes": [],
        "feedback": "Never say 'great question'. Just answer or react naturally.",
    },
    "happy_to_help": {
        "pattern": re.compile(r"\b(happy|glad) to help\b", re.IGNORECASE),
        "channels": ["all"],
        "skip_modes": [],
        "feedback": "Never say 'happy to help'. You're a teammate, not customer service.",
    },
    "as_an_ai": {
        "pattern": re.compile(r"\bas an AI\b", re.IGNORECASE),
        "channels": ["all"],
        "skip_modes": [],
        "feedback": "Never identify as AI unless directly asked.",
    },
    "dive_in": {
        "pattern": re.compile(r"\blet'?s dive in\b", re.IGNORECASE),
        "channels": ["all"],
        "skip_modes": [],
        "feedback": "Corporate filler. Just start talking.",
    },
    "key_takeaways": {
        "pattern": re.compile(r"\bkey takeaway", re.IGNORECASE),
        "channels": ["all"],
        "skip_modes": [],
        "feedback": "Presentation language. This is a conversation.",
    },
    "in_conclusion": {
        "pattern": re.compile(r"\bin conclusion\b", re.IGNORECASE),
        "channels": ["all"],
        "skip_modes": [],
        "feedback": "Essay language. Just finish your thought naturally.",
    },
    "moving_on": {
        "pattern": re.compile(r"\bmoving on to\b", re.IGNORECASE),
        "channels": ["all"],
        "skip_modes": [],
        "feedback": "Mechanical transition. Use natural redirects.",
    },
    "id_be_happy": {
        "pattern": re.compile(r"\bI'?d be happy to\b", re.IGNORECASE),
        "channels": ["all"],
        "skip_modes": [],
        "feedback": "Servile language. Just do the thing.",
    },
    "certainly": {
        "pattern": re.compile(r"\bcertainly[!.\s]", re.IGNORECASE),
        "channels": ["all"],
        "skip_modes": [],
        "feedback": "Butler energy. Say 'bet' or 'got you' or just do it.",
    },
    "i_understand_your": {
        "pattern": re.compile(r"\bI understand (?:your|that|how)\b", re.IGNORECASE),
        "channels": ["all"],
        "skip_modes": [],
        "feedback": "Therapist script. React naturally instead of narrating understanding.",
    },
    "no_problem_at_all": {
        "pattern": re.compile(r"\bno problem at all\b", re.IGNORECASE),
        "channels": ["all"],
        "skip_modes": [],
        "feedback": "Customer service phrase. Drop it.",
    },
    "markdown_headers_voice": {
        "pattern": re.compile(r"^#{1,6}\s", re.MULTILINE),
        "channels": ["voice"],
        "skip_modes": ["build", "spec"],
        "feedback": "No markdown headers in voice. Use natural speech.",
    },
}


class ConversationScorer:
    """
    Scores AI responses against the Conversation DNA.

    Tier 1: Quick check — regex for absolute violations.
            Runs every turn. <5ms. Blocks if violations found.

    Tier 2: Deep score — LLM-based 27-law evaluation.
            Runs on ~20% of responses. Async. Non-blocking.
    """

    def __init__(self, rubric: dict = None, dial_weights: dict = None):
        self.rubric = rubric or {}
        self.dial_weights = dial_weights or {}

    def quick_check(
        self,
        response: str,
        channel: str = "text",
        mode: str = "vibe",
    ) -> list[dict]:
        """
        Tier 1: Quick check for absolute violations.

        Returns list of violations. Empty = PASS.
        Runs in <5ms (pure regex).
        """
        violations = []

        for name, rule in ABSOLUTE_VIOLATIONS.items():
            # Skip rules that don't apply to this channel
            if rule["channels"] != ["all"] and channel not in rule["channels"]:
                continue

            # Skip rules excluded by mode
            if mode in rule.get("skip_modes", []):
                continue

            if rule["pattern"].search(response):
                violations.append({
                    "rule": name,
                    "feedback": rule["feedback"],
                    "severity": "absolute",
                })

        if violations:
            logger.info(
                f"[SCORING] Tier 1 FAIL: {len(violations)} violations — "
                f"{[v['rule'] for v in violations]}"
            )

        return violations

    def heuristic_check(
        self,
        response: str,
        history: list[str] = None,
        user_emotion: str = "neutral",
        mode: str = "vibe",
    ) -> list[dict]:
        """
        Heuristic checks — warnings, not blockers.

        Returns list of warnings. These get logged and fed to
        Node 4 (Memory) for pattern tracking.
        """
        history = history or []
        warnings = []

        # Skip heuristics in spec mode
        if mode == "spec":
            return warnings

        # Check: Too perfect grammar (Law 9)
        # Only flag if: long response + every sentence ends with punctuation
        # + no fragments/dashes/ellipsis (signs of natural speech)
        if len(response) > 150:
            sentences = [s.strip() for s in response.split("\n") if s.strip() and len(s.strip()) > 10]
            has_fragments = any(
                len(s.split()) <= 4 for s in response.split(".") if s.strip()
            )
            has_natural_breaks = any(
                marker in response for marker in ["...", " - ", "—", "like ", "you know"]
            )
            if (sentences
                    and all(s[-1] in ".!?:" for s in sentences)
                    and not has_fragments
                    and not has_natural_breaks):
                warnings.append({
                    "rule": "too_perfect_grammar",
                    "law": 9,
                    "warning": "Every sentence ends perfectly with no fragments or natural breaks.",
                    "severity": "heuristic",
                })

        # Check: Monotone length (Law 27)
        if len(history) >= 3:
            recent_lengths = [len(h) for h in history[-3:]]
            if all(abs(len(response) - rl) < 50 for rl in recent_lengths):
                warnings.append({
                    "rule": "monotone_length",
                    "law": 27,
                    "warning": "Last 4 responses are similar length. Vary your pacing.",
                    "severity": "heuristic",
                })

        # Check: Starts with "So," (AI tell)
        if response.strip().startswith("So,") or response.strip().startswith("So "):
            warnings.append({
                "rule": "starts_with_so",
                "law": None,
                "warning": "Starting with 'So,' is an AI tell. Vary your openings.",
                "severity": "heuristic",
            })

        # Check: Same opener 3x in a row (Law 27)
        if len(history) >= 2:
            opener = response[:20].lower()
            if (history[-1][:20].lower() == opener and
                    history[-2][:20].lower() == opener):
                warnings.append({
                    "rule": "triple_same_opener",
                    "law": 27,
                    "warning": "Same opening pattern 3x in a row. Switch it up.",
                    "severity": "heuristic",
                })

        # Check: Energy mismatch (Law 26)
        if user_emotion == "excited" and not any(
            c in response for c in ["!", "CAPS", "bro", "yo", "fire", "dope", "crazy"]
        ):
            # Only warn if response is also long (short = might be intentional)
            if len(response) > 50:
                warnings.append({
                    "rule": "energy_mismatch",
                    "law": 26,
                    "warning": "User is excited but response energy is flat. Match their energy.",
                    "severity": "heuristic",
                })

        # Check: No emotion acknowledgment on emotional input (Law 3)
        if user_emotion in ("frustrated", "defeated", "serious"):
            emotion_words = ["man", "bro", "yo", "damn", "wow", "dang", "tough", "rough", "hear you"]
            if not any(word in response.lower() for word in emotion_words):
                warnings.append({
                    "rule": "no_emotion_acknowledgment",
                    "law": 3,
                    "warning": "User has strong emotion but response doesn't acknowledge it.",
                    "severity": "heuristic",
                })

        if warnings:
            logger.debug(
                f"[SCORING] Heuristic warnings: {len(warnings)} — "
                f"{[w['rule'] for w in warnings]}"
            )

        return warnings

    def build_regeneration_feedback(self, violations: list[dict]) -> str:
        """
        Build feedback string for LLM regeneration.

        Injected back into the prompt when Tier 1 fails.
        """
        lines = [
            "Your previous response violated conversation rules. Rewrite it:",
            "",
        ]
        for v in violations:
            lines.append(f"- VIOLATION: {v['feedback']}")

        lines.append("")
        lines.append(
            "Keep the same meaning and information. "
            "Fix ONLY the violations above. "
            "Make it sound like a real person talking, not an AI."
        )

        return "\n".join(lines)

    def calculate_composite(
        self,
        scores: dict[int, float],
    ) -> float:
        """
        Calculate weighted composite score for Tier 2 deep scoring.

        Laws with higher dials count more.
        Dial 10 = weight 1.0, dial 3 = weight 0.3.
        """
        if not scores or not self.dial_weights:
            return 0.5

        weighted_sum = 0.0
        weight_total = 0.0

        for law_id, score in scores.items():
            weight = self.dial_weights.get(law_id, 0.5)
            weighted_sum += score * weight
            weight_total += weight

        return weighted_sum / weight_total if weight_total > 0 else 0.5

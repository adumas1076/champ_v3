# ============================================
# Cocreatiq V1 — Operator Pack Validation
# Validates operator YAML before compile
# Pattern: Claude Code Zod schemas + our OPT field list
# ============================================

import logging
from typing import Optional

logger = logging.getLogger(__name__)


# Required fields that MUST be present
REQUIRED_FIELDS = [
    "operator_name",
    "operator_role",
    "primary_mission",
    "tone_band",
    "relational_stance",
    "felt_presence",
    "forbidden_traits",
    "primary_audience",
    "primary_objective",
    "always_rules",
    "never_rules",
]

# Optional but recommended
RECOMMENDED_FIELDS = [
    "operator_relationship",
    "secondary_mission",
    "identity_summary",
    "confidence_band",
    "warmth_band",
    "humor_range",
    "energy_profile",
    "explanation_style",
    "communication_values",
    "audience_rules",
    "one_to_one_behavior",
    "secondary_objective",
    "success_definition",
    "decision_rules",
    "allowed_tools",
    "memory_scope",
    "initiative_level",
    "hard_boundaries",
    "escalation_boundaries",
    "default_warmth",
    "default_authority",
    "default_playfulness",
    "default_urgency",
    "default_softness",
    "default_depth",
    "default_challenge",
    "default_pacing",
    "response_length_rules",
    "acknowledgment_behavior_rules",
    "system_alignment_rule",
]

# Valid modulator range values
VALID_MODULATOR_RANGE = range(1, 11)


def validate_operator_pack(pack: dict) -> dict:
    """
    Validate an operator pack dictionary.
    Returns: {"valid": bool, "errors": [...], "warnings": [...]}
    """
    errors = []
    warnings = []

    # 1. Check required fields
    for field in REQUIRED_FIELDS:
        if field not in pack or not pack[field]:
            errors.append(f"Missing required field: {field}")

    # 2. Check recommended fields
    for field in RECOMMENDED_FIELDS:
        if field not in pack or not pack[field]:
            warnings.append(f"Missing recommended field: {field}")

    # 3. Validate operator_name
    name = pack.get("operator_name", "")
    if name and not name.replace("_", "").replace("-", "").isalnum():
        errors.append(f"operator_name must be alphanumeric (got: {name})")

    # 4. Validate modulator defaults (should be 1-10)
    for mod in ["warmth", "authority", "playfulness", "urgency", "softness", "depth", "challenge", "pacing"]:
        key = f"default_{mod}"
        val = pack.get(key, "")
        if val:
            # Extract number from string like "7 — warm but not soft"
            try:
                num = int(str(val).split()[0].split("—")[0].strip())
                if num < 1 or num > 10:
                    warnings.append(f"{key} should be 1-10 (got: {num})")
            except (ValueError, IndexError):
                pass  # Non-numeric format is OK (descriptive)

    # 5. Validate always/never rules are lists
    for field in ["always_rules", "never_rules"]:
        val = pack.get(field, "")
        if val and isinstance(val, str) and "-" not in val:
            warnings.append(f"{field} should contain bullet points (use - prefix)")

    # 6. Check forbidden_traits isn't empty
    forbidden = pack.get("forbidden_traits", "")
    if forbidden and len(str(forbidden)) < 20:
        warnings.append("forbidden_traits seems too short — be specific about what the operator should NEVER feel like")

    # 7. Check felt_presence
    presence = pack.get("felt_presence", "")
    if presence and len(str(presence)) < 20:
        warnings.append("felt_presence seems too short — describe how the operator should FEEL to the user")

    is_valid = len(errors) == 0

    if errors:
        logger.error(f"Operator pack validation FAILED: {len(errors)} errors")
        for e in errors:
            logger.error(f"  ERROR: {e}")
    if warnings:
        logger.warning(f"Operator pack validation: {len(warnings)} warnings")
        for w in warnings:
            logger.warning(f"  WARNING: {w}")
    if is_valid and not warnings:
        logger.info("Operator pack validation PASSED — all fields clean")

    return {
        "valid": is_valid,
        "errors": errors,
        "warnings": warnings,
    }


def validate_yaml_file(yaml_path: str) -> dict:
    """Validate an operator pack YAML file."""
    try:
        import yaml
        with open(yaml_path, "r", encoding="utf-8") as f:
            pack = yaml.safe_load(f)
        if not isinstance(pack, dict):
            return {"valid": False, "errors": ["YAML file is not a dictionary"], "warnings": []}
        return validate_operator_pack(pack)
    except Exception as e:
        return {"valid": False, "errors": [f"Failed to load YAML: {e}"], "warnings": []}
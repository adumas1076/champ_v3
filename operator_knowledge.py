# ============================================
# Cocreatiq V1 — Operator Knowledge Blocks
# Business Matrix frameworks load per operator type
# Pattern: Dr. Frankenstein — content exists, just stitch it in
# ============================================

import logging
import os

logger = logging.getLogger(__name__)

# Base directory for knowledge block files
KNOWLEDGE_DIR = os.path.join(os.path.dirname(__file__), "development")

# Mapping: operator name → list of knowledge block files
# Each operator gets the frameworks relevant to their role
OPERATOR_KNOWLEDGE = {
    "sales": [
        "0008_os_business_matrix_hormozi_sales.md",
        "0011_os_business_matrix_gian_ad_optimization.md",
    ],
    "lead_gen": [
        "0010_os_business_matrix_priestley_lead_gen.md",
        "0011_os_business_matrix_gian_ad_optimization.md",
    ],
    "marketing": [
        "0017_os_business_matrix_garyvee_content_model.md",
        "0015_os_business_matrix_lamar_brand_growth.md",
        "0016_os_business_matrix_lamar_brand_mistakes.md",
    ],
    "onboarding": [
        "0012_os_business_matrix_platten_onboarding.md",
    ],
    "retention": [
        "0013_os_business_matrix_hormozi_retention.md",
        "0014_os_business_matrix_lamar_retention.md",
    ],
    "operations": [
        "0009_os_business_matrix_hormozi_scaling.md",
        "0012_os_business_matrix_gian_scaling_masterclass.md",
    ],
    "research": [
        # Research operator gets no pre-loaded blocks — it researches live
    ],
    "champ": [
        # Champ gets ALL frameworks — he's the boss
        "0008_os_business_matrix_hormozi_sales.md",
        "0009_os_business_matrix_hormozi_scaling.md",
        "0010_os_business_matrix_priestley_lead_gen.md",
        "0011_os_business_matrix_gian_ad_optimization.md",
        "0012_os_business_matrix_gian_scaling_masterclass.md",
        "0012_os_business_matrix_platten_onboarding.md",
        "0013_os_business_matrix_hormozi_retention.md",
        "0014_os_business_matrix_lamar_retention.md",
        "0015_os_business_matrix_lamar_brand_growth.md",
        "0016_os_business_matrix_lamar_brand_mistakes.md",
        "0017_os_business_matrix_garyvee_content_model.md",
    ],
}


def extract_frameworks(content: str, max_chars: int = 3000) -> str:
    """
    Extract key frameworks from a knowledge block.
    Keeps headers (##, ###) and bullet points, drops metadata and timestamps.
    """
    lines = content.split("\n")
    extracted = []
    current_size = 0

    for line in lines:
        stripped = line.strip()

        # Skip metadata lines
        if stripped.startswith("**Date:") or stripped.startswith("**Source:"):
            continue
        if stripped.startswith("**URL:") or stripped.startswith("**Duration:"):
            continue
        if stripped.startswith("**Extracted via:") or stripped.startswith("**Coverage:"):
            continue
        if stripped == "---":
            continue

        # Keep headers — these ARE the frameworks
        if stripped.startswith("#"):
            extracted.append(stripped)
            current_size += len(stripped)
            continue

        # Keep bullet points and quotes — these are the rules
        if stripped.startswith("- ") or stripped.startswith("> ") or stripped.startswith("* "):
            # Strip timestamp references like [0:12] or [3:12-7:00]
            clean = stripped
            while "[" in clean and "]" in clean:
                start = clean.find("[")
                end = clean.find("]", start)
                if end != -1:
                    bracket_content = clean[start+1:end]
                    # Only strip timestamp-like brackets (contain : or digits)
                    if ":" in bracket_content or bracket_content.replace("-", "").isdigit():
                        clean = clean[:start] + clean[end+1:]
                    else:
                        break
                else:
                    break
            clean = clean.strip()
            if clean and len(clean) > 5:
                extracted.append(clean)
                current_size += len(clean)

        # Keep bold framework names
        if stripped.startswith("**") and stripped.endswith("**"):
            extracted.append(stripped)
            current_size += len(stripped)

        # Stop if we're getting too long
        if current_size > max_chars:
            extracted.append("... [truncated for context window]")
            break

    return "\n".join(extracted)


def load_knowledge_blocks(operator_name: str, max_total_chars: int = 8000) -> str:
    """
    Load and extract knowledge blocks for an operator.
    Returns a formatted string ready to inject into operator context.
    """
    name = operator_name.lower()
    files = OPERATOR_KNOWLEDGE.get(name, [])

    if not files:
        logger.info(f"[KNOWLEDGE] No knowledge blocks for '{name}'")
        return ""

    blocks = []
    total_chars = 0
    per_block_limit = max_total_chars // max(len(files), 1)

    for filename in files:
        filepath = os.path.join(KNOWLEDGE_DIR, filename)
        if not os.path.exists(filepath):
            logger.warning(f"[KNOWLEDGE] File not found: {filename}")
            continue

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            extracted = extract_frameworks(content, max_chars=per_block_limit)
            if extracted:
                blocks.append(extracted)
                total_chars += len(extracted)
                logger.debug(f"[KNOWLEDGE] Loaded {filename}: {len(extracted)} chars")
        except Exception as e:
            logger.warning(f"[KNOWLEDGE] Failed to load {filename}: {e}")

    if not blocks:
        return ""

    result = "## BUSINESS FRAMEWORKS (use these in your work)\n\n" + "\n\n".join(blocks)

    logger.info(f"[KNOWLEDGE] Loaded {len(blocks)}/{len(files)} blocks for '{name}': {total_chars} chars")
    return result

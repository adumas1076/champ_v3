# ============================================
# Content Matrix — Pass 1: Deterministic Parser
# Extracts structure from content. NO LLM. FREE.
# Pattern: Graphify extract.py adapted for business content
# ============================================

import re
import hashlib
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def make_id(*parts: str) -> str:
    """Build a stable node ID from name parts."""
    combined = "_".join(p.strip("_.") for p in parts if p)
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", combined)
    return cleaned.strip("_").lower()[:100]


def content_hash(content: str) -> str:
    """SHA-256 hash of content for caching."""
    return hashlib.sha256(content.encode()).hexdigest()


# ---- Knowledge Block Parser (.md files from Business Matrix) ----

def parse_knowledge_block(filepath: str) -> dict:
    """
    Extract nodes + edges from a Business Matrix .md file.
    FREE — no LLM call. Pure regex + structure.

    Extracts:
    - Framework name (from # header)
    - Elements (from ## headers)
    - Rules/points (from bullet points under each element)
    - Source metadata (author, URL, date)
    """
    path = Path(filepath)
    if not path.exists():
        return {"nodes": [], "edges": [], "source_file": str(filepath)}

    content = path.read_text(encoding="utf-8")
    nodes = []
    edges = []
    source_file = str(path.name)

    # Extract metadata from header
    author = ""
    source_url = ""
    for line in content.split("\n")[:15]:
        if line.startswith("**Source:**"):
            author = line.replace("**Source:**", "").strip()
        if line.startswith("**URL:**"):
            source_url = line.replace("**URL:**", "").strip()

    # Extract framework name from first # header
    framework_name = ""
    framework_id = ""
    for line in content.split("\n"):
        if line.startswith("# ") and not line.startswith("##"):
            framework_name = line.replace("# ", "").strip()
            framework_id = make_id(source_file, framework_name)
            nodes.append({
                "id": framework_id,
                "label": framework_name,
                "source_type": "framework",
                "source_file": source_file,
                "source_location": "# header",
                "operator_scope": _infer_operator_scope(source_file),
                "content_hash": content_hash(framework_name),
                "metadata": {"author": author, "url": source_url},
            })
            break

    if not framework_id:
        framework_id = make_id(source_file)
        framework_name = source_file
        nodes.append({
            "id": framework_id,
            "label": framework_name,
            "source_type": "framework",
            "source_file": source_file,
            "source_location": "filename",
            "operator_scope": _infer_operator_scope(source_file),
            "content_hash": content_hash(source_file),
            "metadata": {},
        })

    # Extract elements from ## and ### headers
    current_element_id = framework_id
    for line in content.split("\n"):
        stripped = line.strip()

        # ## or ### headers = elements
        if stripped.startswith("## ") or stripped.startswith("### "):
            header_text = re.sub(r"^#+\s*", "", stripped).strip()
            # Skip metadata headers
            if any(skip in header_text.lower() for skip in ["what this video", "who is", "context"]):
                continue

            element_id = make_id(framework_id, header_text)
            current_element_id = element_id

            nodes.append({
                "id": element_id,
                "label": header_text,
                "source_type": "element",
                "source_file": source_file,
                "source_location": stripped[:5],
                "operator_scope": _infer_operator_scope(source_file),
                "content_hash": content_hash(header_text),
                "metadata": {"parent_framework": framework_name},
            })
            edges.append({
                "source": element_id,
                "target": framework_id,
                "relation": "part_of",
                "confidence": "EXTRACTED",
                "weight": 1.0,
            })

        # Bullet points under current element = rules/facts
        elif stripped.startswith("- ") and len(stripped) > 20:
            bullet_text = stripped[2:].strip()
            # Strip timestamp references
            bullet_text = re.sub(r"\[[\d:,\s\-]+\]", "", bullet_text).strip()
            # Strip source references
            bullet_text = re.sub(r"\*Source:.*?\*", "", bullet_text).strip()

            if len(bullet_text) > 15:
                rule_id = make_id(current_element_id, bullet_text[:50])
                nodes.append({
                    "id": rule_id,
                    "label": bullet_text[:200],
                    "source_type": "rule",
                    "source_file": source_file,
                    "source_location": current_element_id,
                    "operator_scope": _infer_operator_scope(source_file),
                    "content_hash": content_hash(bullet_text),
                    "metadata": {},
                })
                edges.append({
                    "source": rule_id,
                    "target": current_element_id,
                    "relation": "part_of",
                    "confidence": "EXTRACTED",
                    "weight": 0.8,
                })

    logger.info(f"[PARSER] {source_file}: {len(nodes)} nodes, {len(edges)} edges")
    return {"nodes": nodes, "edges": edges, "source_file": source_file}


# ---- Conversation Transcript Parser ----

def parse_transcript(transcript_text: str, session_id: str = "") -> dict:
    """
    Extract nodes + edges from a conversation transcript.
    FREE — regex on [timestamp] SPEAKER: text pattern.

    Extracts:
    - Session node
    - Entities mentioned (proper nouns, project names)
    - Decisions made ("let's do X", "we'll go with Y")
    - Questions asked
    """
    nodes = []
    edges = []

    # Session node
    sid = session_id or make_id("session", content_hash(transcript_text[:100]))
    nodes.append({
        "id": sid,
        "label": f"Session {sid[:8]}",
        "source_type": "session",
        "source_file": "transcript",
        "source_location": "",
        "operator_scope": ["champ"],
        "content_hash": content_hash(transcript_text[:500]),
        "metadata": {},
    })

    # Extract entities (capitalized words that appear 2+ times)
    words = re.findall(r"\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)*\b", transcript_text)
    word_counts = {}
    for w in words:
        if len(w) > 3 and w not in ("The", "This", "That", "What", "When", "Where", "How", "Yeah", "Copy"):
            word_counts[w] = word_counts.get(w, 0) + 1

    for entity, count in word_counts.items():
        if count >= 2:
            entity_id = make_id("entity", entity)
            nodes.append({
                "id": entity_id,
                "label": entity,
                "source_type": "entity",
                "source_file": "transcript",
                "source_location": sid,
                "operator_scope": ["champ"],
                "content_hash": content_hash(entity),
                "metadata": {"mention_count": count},
            })
            edges.append({
                "source": entity_id,
                "target": sid,
                "relation": "discussed_in",
                "confidence": "EXTRACTED",
                "weight": min(count / 10, 1.0),
            })

    # Extract decisions (patterns like "let's", "we'll", "going to", "lock it in")
    decision_patterns = [
        r"(?:let's|we'll|we're going to|gonna|lock it in|decided to)\s+(.{10,80})",
        r"(?:the plan is|the move is|we should)\s+(.{10,80})",
    ]
    for pattern in decision_patterns:
        for match in re.finditer(pattern, transcript_text, re.IGNORECASE):
            decision_text = match.group(1).strip().rstrip(".")
            decision_id = make_id("decision", decision_text[:50])
            nodes.append({
                "id": decision_id,
                "label": f"Decision: {decision_text[:100]}",
                "source_type": "decision",
                "source_file": "transcript",
                "source_location": sid,
                "operator_scope": ["champ"],
                "content_hash": content_hash(decision_text),
                "metadata": {},
            })
            edges.append({
                "source": decision_id,
                "target": sid,
                "relation": "decided_in",
                "confidence": "EXTRACTED",
                "weight": 0.9,
            })

    logger.info(f"[PARSER] transcript {sid[:8]}: {len(nodes)} nodes, {len(edges)} edges")
    return {"nodes": nodes, "edges": edges, "source_file": "transcript"}


# ---- Supabase Memory Parser ----

def parse_memory_tables(entities: list, lessons: list, profile: list) -> dict:
    """
    Extract nodes + edges from existing Supabase memory tables.
    FREE — direct data transformation.
    """
    nodes = []
    edges = []

    # Entities → nodes
    for e in entities:
        eid = make_id("entity", e.get("name", ""))
        nodes.append({
            "id": eid,
            "label": f"{e.get('name', '')} [{e.get('entity_type', '')}]",
            "source_type": "entity",
            "source_file": "mem_entities",
            "source_location": "",
            "operator_scope": [e.get("operator_name", "champ")],
            "content_hash": content_hash(e.get("name", "")),
            "metadata": {"description": e.get("description", "")[:200]},
        })

    # Lessons → nodes
    for l in lessons:
        lid = make_id("lesson", l.get("lesson", "")[:50])
        nodes.append({
            "id": lid,
            "label": l.get("lesson", ""),
            "source_type": "lesson",
            "source_file": "mem_lessons",
            "source_location": "",
            "operator_scope": [l.get("operator_name", "champ")],
            "content_hash": content_hash(l.get("lesson", "")),
            "metadata": {
                "category": l.get("tags", ["general"])[0] if l.get("tags") else "general",
                "times_seen": l.get("times_seen", 1),
                "status": l.get("status", "draft"),
            },
        })

    # Profile facts → nodes
    for p in profile:
        pid = make_id("fact", p.get("key", ""))
        nodes.append({
            "id": pid,
            "label": f"{p.get('key', '')}: {p.get('value', '')[:100]}",
            "source_type": "fact",
            "source_file": "mem_profile",
            "source_location": "",
            "operator_scope": ["champ"],
            "content_hash": content_hash(p.get("key", "") + p.get("value", "")),
            "metadata": {"category": p.get("category", "")},
        })

    logger.info(f"[PARSER] memory tables: {len(nodes)} nodes, {len(edges)} edges")
    return {"nodes": nodes, "edges": edges, "source_file": "memory"}


# ---- Helpers ----

def _infer_operator_scope(filename: str) -> list:
    """Infer which operators should have access to this content."""
    f = filename.lower()
    if "hormozi_sales" in f or "closer" in f:
        return ["sales", "champ"]
    if "hormozi_scaling" in f or "gian_scaling" in f:
        return ["operations", "champ"]
    if "hormozi_retention" in f or "lamar_retention" in f:
        return ["retention", "champ"]
    if "priestley" in f or "gian_ad" in f:
        return ["lead_gen", "champ"]
    if "garyvee" in f or "lamar_brand" in f:
        return ["marketing", "champ"]
    if "platten" in f:
        return ["onboarding", "champ"]
    return ["champ"]


def parse_all_knowledge_blocks(knowledge_dir: str) -> list[dict]:
    """Parse all .md files in the knowledge block directory."""
    results = []
    kb_dir = Path(knowledge_dir)
    if not kb_dir.exists():
        return results

    for md_file in sorted(kb_dir.glob("0*_os_business_matrix_*.md")):
        result = parse_knowledge_block(str(md_file))
        if result["nodes"]:
            results.append(result)

    logger.info(f"[PARSER] Parsed {len(results)} knowledge block files")
    return results
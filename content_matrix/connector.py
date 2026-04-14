# ============================================
# Content Matrix — Pass 2: Semantic Connector
# LLM finds cross-content relationships. Runs ONCE per content, cached.
# Pattern: Graphify semantic pass + confidence tagging
# ============================================

import json
import logging
import os
import requests
from typing import Optional

logger = logging.getLogger(__name__)


def connect_semantic(
    nodes: list[dict],
    existing_edges: list[dict] = None,
    model: str = "gpt-4o-mini",
    max_relationships: int = 30,
) -> list[dict]:
    """
    LLM finds relationships between content nodes that the parser can't.
    Cross-framework connections, contradictions, application patterns.

    Runs ONCE per content batch. Results get cached by graph_store.

    Args:
        nodes: List of node dicts from parser
        existing_edges: Edges already found by parser (to avoid duplicates)
        model: LLM to use (cheap model — gpt-4o-mini or gemini-flash)
        max_relationships: Max edges to return

    Returns:
        List of edge dicts with confidence tags
    """
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key or len(nodes) < 3:
        return []

    # Build compact node summaries (minimize tokens)
    node_summaries = []
    for n in nodes[:100]:  # Cap at 100 nodes
        label = n.get("label", "")[:100]
        ntype = n.get("source_type", "")
        nid = n.get("id", "")
        node_summaries.append(f"[{nid}] ({ntype}) {label}")

    # Build existing edge set for dedup
    existing = set()
    if existing_edges:
        for e in existing_edges:
            existing.add((e.get("source", ""), e.get("target", "")))

    prompt = f"""You are a knowledge graph builder. Given these content nodes from a business knowledge base, find meaningful relationships between them.

NODES:
{chr(10).join(node_summaries)}

RULES:
- Only return relationships you're confident about
- Each relationship needs: source_id, target_id, relation, confidence, reason
- relation must be one of: supports, contradicts, applied_in, evolved_from, prerequisite, related_to, teaches
- confidence must be: INFERRED (reasonable deduction) or AMBIGUOUS (uncertain)
- reason: one sentence explaining WHY this relationship exists
- Max {max_relationships} relationships
- Focus on CROSS-SOURCE connections (different files, different frameworks)
- Skip obvious part_of relationships (parser already found those)

Return ONLY a JSON array. No markdown, no explanation. Example:
[{{"source": "node_id_1", "target": "node_id_2", "relation": "supports", "confidence": "INFERRED", "reason": "Both address customer retention through engagement"}}]"""

    try:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "You are a knowledge graph builder. Return only valid JSON arrays."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.3,
                "max_tokens": 2000,
            },
            timeout=30,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"].strip()

        # Strip markdown code blocks if present
        if content.startswith("```"):
            content = content.split("\n", 1)[1] if "\n" in content else content
            content = content.rsplit("```", 1)[0] if "```" in content else content

        edges = json.loads(content.strip())
        if not isinstance(edges, list):
            return []

        # Validate and clean edges
        valid_edges = []
        valid_relations = {"supports", "contradicts", "applied_in", "evolved_from", "prerequisite", "related_to", "teaches"}
        valid_confidence = {"INFERRED", "AMBIGUOUS"}
        node_ids = {n["id"] for n in nodes}

        for edge in edges:
            src = edge.get("source", "")
            tgt = edge.get("target", "")
            rel = edge.get("relation", "related_to")
            conf = edge.get("confidence", "INFERRED")

            # Validate
            if src not in node_ids or tgt not in node_ids:
                continue
            if (src, tgt) in existing:
                continue
            if rel not in valid_relations:
                rel = "related_to"
            if conf not in valid_confidence:
                conf = "INFERRED"

            valid_edges.append({
                "source": src,
                "target": tgt,
                "relation": rel,
                "confidence": conf,
                "weight": 0.6 if conf == "INFERRED" else 0.3,
                "reason": edge.get("reason", ""),
            })

        logger.info(f"[CONNECTOR] Found {len(valid_edges)} semantic relationships from {len(nodes)} nodes")
        return valid_edges

    except Exception as e:
        logger.warning(f"[CONNECTOR] Semantic connection failed (non-fatal): {e}")
        return []


def promote_edge(edge: dict, seen_count: int) -> dict:
    """
    Promote edge confidence based on repeated observation.
    AMBIGUOUS → INFERRED → EXTRACTED → PROVEN

    Called when the same relationship is observed again.
    """
    confidence = edge.get("confidence", "AMBIGUOUS")

    if seen_count >= 5 and confidence != "PROVEN":
        edge["confidence"] = "PROVEN"
        edge["weight"] = 0.95
    elif seen_count >= 3 and confidence in ("AMBIGUOUS", "INFERRED"):
        edge["confidence"] = "EXTRACTED"
        edge["weight"] = 0.85
    elif seen_count >= 2 and confidence == "AMBIGUOUS":
        edge["confidence"] = "INFERRED"
        edge["weight"] = 0.6

    edge["seen_count"] = seen_count
    return edge
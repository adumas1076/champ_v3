# ============================================
# Content Matrix — Graph Store
# Build, cache, persist, query the knowledge graph
# Pattern: Graphify build.py + cache.py + NetworkX
# ============================================

import json
import logging
import os
import re
import hashlib
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import networkx as nx
except ImportError:
    nx = None
    logger.warning("[GRAPH] NetworkX not installed. Content Matrix disabled. pip install networkx")


# ---- Cache ----

CACHE_DIR = Path.home() / ".champ" / "content_matrix" / "cache"
GRAPH_PATH = Path.home() / ".champ" / "content_matrix" / "graph.json"


def _ensure_dirs():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    GRAPH_PATH.parent.mkdir(parents=True, exist_ok=True)


def is_cached(content_hash: str) -> bool:
    """Check if this content has already been processed."""
    return (CACHE_DIR / f"{content_hash}.json").exists()


def load_cache(content_hash: str) -> Optional[dict]:
    """Load cached extraction for this content."""
    path = CACHE_DIR / f"{content_hash}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def save_cache(content_hash: str, extraction: dict):
    """Save extraction to cache. Atomic write."""
    _ensure_dirs()
    path = CACHE_DIR / f"{content_hash}.json"
    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(extraction, default=str), encoding="utf-8")
        os.replace(tmp, path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


# ---- Build Graph ----

def build_graph(extractions: list[dict], directed: bool = False):
    """
    Merge multiple extraction results into one NetworkX graph.
    Same pattern as Graphify build.py.

    Nodes with same ID get merged (last write wins).
    Edges accumulate.
    """
    if nx is None:
        return None

    G = nx.DiGraph() if directed else nx.Graph()

    for extraction in extractions:
        # Add nodes
        for node in extraction.get("nodes", []):
            nid = node.get("id", "")
            if not nid:
                continue
            attrs = {k: v for k, v in node.items() if k != "id"}
            G.add_node(nid, **attrs)

        # Add edges
        node_set = set(G.nodes())
        for edge in extraction.get("edges", []):
            src = edge.get("source", "")
            tgt = edge.get("target", "")
            if src not in node_set or tgt not in node_set:
                continue
            attrs = {k: v for k, v in edge.items() if k not in ("source", "target")}
            G.add_edge(src, tgt, **attrs)

    logger.info(f"[GRAPH] Built: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    return G


# ---- Persist / Load ----

def save_graph(G, path: Optional[str] = None):
    """Save graph to JSON. Atomic write."""
    if G is None or nx is None:
        return

    _ensure_dirs()
    filepath = Path(path) if path else GRAPH_PATH

    data = {
        "nodes": [
            {"id": nid, **attrs}
            for nid, attrs in G.nodes(data=True)
        ],
        "edges": [
            {"source": src, "target": tgt, **attrs}
            for src, tgt, attrs in G.edges(data=True)
        ],
        "meta": {
            "node_count": G.number_of_nodes(),
            "edge_count": G.number_of_edges(),
        }
    }

    tmp = filepath.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(data, default=str, indent=2), encoding="utf-8")
        os.replace(tmp, filepath)
        logger.info(f"[GRAPH] Saved: {filepath} ({G.number_of_nodes()} nodes, {G.number_of_edges()} edges)")
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def load_graph(path: Optional[str] = None):
    """Load graph from JSON."""
    if nx is None:
        return None

    filepath = Path(path) if path else GRAPH_PATH
    if not filepath.exists():
        return None

    try:
        data = json.loads(filepath.read_text(encoding="utf-8"))
        return build_graph([data])
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"[GRAPH] Failed to load: {e}")
        return None


# ---- Cluster ----

def cluster_graph(G):
    """
    Auto-group related nodes using Louvain community detection.
    Pattern: Graphify cluster.py
    """
    if G is None or nx is None:
        return {}

    try:
        # NetworkX built-in Louvain
        communities = nx.community.louvain_communities(G, seed=42)
        cluster_map = {}
        for idx, community in enumerate(communities):
            for node_id in community:
                G.nodes[node_id]["cluster"] = idx
                cluster_map[node_id] = idx

        logger.info(f"[GRAPH] Clustered into {len(communities)} communities")
        return {i: list(c) for i, c in enumerate(communities)}
    except Exception as e:
        logger.warning(f"[GRAPH] Clustering failed (non-fatal): {e}")
        return {}


# ---- Analyze ----

def god_nodes(G, top_n: int = 10) -> list[dict]:
    """
    Find the most-connected nodes = core concepts.
    Pattern: Graphify analyze.py
    """
    if G is None or nx is None:
        return []

    degree = dict(G.degree())
    sorted_nodes = sorted(degree.items(), key=lambda x: x[1], reverse=True)

    results = []
    for node_id, deg in sorted_nodes[:top_n]:
        attrs = G.nodes[node_id]
        results.append({
            "id": node_id,
            "label": attrs.get("label", node_id),
            "edges": deg,
            "source_type": attrs.get("source_type", ""),
            "cluster": attrs.get("cluster", -1),
        })
    return results


def surprising_connections(G, top_n: int = 5) -> list[dict]:
    """
    Find cross-cluster connections = non-obvious relationships.
    Pattern: Graphify analyze.py
    """
    if G is None or nx is None:
        return []

    results = []
    for src, tgt, attrs in G.edges(data=True):
        src_cluster = G.nodes[src].get("cluster", -1)
        tgt_cluster = G.nodes[tgt].get("cluster", -1)

        if src_cluster != tgt_cluster and src_cluster >= 0 and tgt_cluster >= 0:
            results.append({
                "source": G.nodes[src].get("label", src),
                "target": G.nodes[tgt].get("label", tgt),
                "relation": attrs.get("relation", "related_to"),
                "confidence": attrs.get("confidence", "INFERRED"),
                "reason": attrs.get("reason", ""),
            })

    # Sort by confidence (AMBIGUOUS first — most surprising)
    confidence_order = {"AMBIGUOUS": 0, "INFERRED": 1, "EXTRACTED": 2, "PROVEN": 3}
    results.sort(key=lambda x: confidence_order.get(x["confidence"], 99))
    return results[:top_n]


# ---- Query ----

def query_graph(
    G,
    user_message: str,
    operator_name: str = "champ",
    top_n: int = 10,
) -> str:
    """
    Query the content graph for context relevant to this user message.
    Returns a formatted string ready to inject into the LLM prompt.

    FREE — no LLM call. In-memory keyword matching on NetworkX.

    This is where the token savings happen:
    - Old: inject ALL 15K+ tokens of knowledge every turn
    - New: inject only the ~500-800 tokens that are RELEVANT to this turn
    """
    if G is None or nx is None or G.number_of_nodes() == 0:
        return ""

    # 1. Extract keywords from user message
    keywords = _extract_keywords(user_message)
    if not keywords:
        return ""

    # 2. Score each node by keyword overlap + operator scope match
    scored = []
    for node_id, attrs in G.nodes(data=True):
        label = attrs.get("label", "").lower()
        source_type = attrs.get("source_type", "")
        scope = attrs.get("operator_scope", ["champ"])

        # Operator scope filter
        if operator_name not in scope and "champ" not in scope:
            continue

        # Keyword score
        score = sum(1 for kw in keywords if kw in label)

        # Boost frameworks and elements (they're more important than rules)
        if source_type in ("framework", "element"):
            score *= 1.5
        elif source_type == "lesson" and attrs.get("metadata", {}).get("status") == "proven":
            score *= 1.3

        if score > 0:
            scored.append((node_id, score))

    if not scored:
        return ""

    # 3. Get top N matches + their 1-hop neighbors
    top_nodes = sorted(scored, key=lambda x: x[1], reverse=True)[:top_n]
    context_nodes = set()
    for node_id, _ in top_nodes:
        context_nodes.add(node_id)
        for neighbor in G.neighbors(node_id):
            context_nodes.add(neighbor)

    # Cap total context nodes
    if len(context_nodes) > top_n * 3:
        # Keep only the directly matched + their highest-degree neighbors
        context_nodes = {nid for nid, _ in top_nodes}
        for node_id, _ in top_nodes:
            neighbors = sorted(
                G.neighbors(node_id),
                key=lambda n: G.degree(n),
                reverse=True,
            )[:2]
            context_nodes.update(neighbors)

    # 4. Build injection string
    lines = ["## RELEVANT KNOWLEDGE (from Content Graph)"]
    for node_id in context_nodes:
        if node_id not in G.nodes:
            continue
        attrs = G.nodes[node_id]
        label = attrs.get("label", node_id)
        ntype = attrs.get("source_type", "")
        lines.append(f"- [{ntype}] {label}")

        # Add relationship context for direct matches only
        if node_id in {nid for nid, _ in top_nodes}:
            for neighbor in G.neighbors(node_id):
                if neighbor in context_nodes and neighbor in G.nodes:
                    edge_data = G.edges.get((node_id, neighbor), {})
                    rel = edge_data.get("relation", "related_to")
                    conf = edge_data.get("confidence", "")
                    neighbor_label = G.nodes[neighbor].get("label", neighbor)
                    lines.append(f"  → {rel} [{conf}]: {neighbor_label[:80]}")

    result = "\n".join(lines)
    logger.info(f"[GRAPH] Query '{user_message[:40]}' → {len(context_nodes)} nodes, {len(result)} chars")
    return result


def _extract_keywords(text: str) -> list[str]:
    """Extract meaningful keywords from user message. FREE."""
    # Lowercase, split, remove common words
    stop_words = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "shall", "can", "need", "dare", "ought",
        "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
        "as", "into", "through", "during", "before", "after", "above", "below",
        "between", "out", "off", "over", "under", "again", "further", "then",
        "once", "here", "there", "when", "where", "why", "how", "all", "both",
        "each", "few", "more", "most", "other", "some", "such", "no", "nor",
        "not", "only", "own", "same", "so", "than", "too", "very", "just",
        "don", "now", "and", "but", "or", "if", "it", "its", "i", "me", "my",
        "we", "our", "you", "your", "he", "she", "they", "them", "what", "which",
        "who", "this", "that", "these", "those", "am", "up", "about", "get",
        "got", "like", "yeah", "okay", "right", "well", "know", "think",
        "want", "tell", "say", "said", "champ", "bro", "man", "hey", "yo",
    }
    words = re.findall(r"\b[a-z]+\b", text.lower())
    keywords = [w for w in words if w not in stop_words and len(w) > 2]
    return keywords


# ---- Full Pipeline ----

def build_full_graph(
    knowledge_dir: str,
    memory_data: Optional[dict] = None,
    run_semantic: bool = True,
) -> Optional[object]:
    """
    Full pipeline: parse all content → connect → build → cluster → save.

    Args:
        knowledge_dir: Path to Business Matrix .md files
        memory_data: Dict with 'entities', 'lessons', 'profile' from Supabase
        run_semantic: Whether to run Pass 2 (LLM connector). Set False for fast/free rebuild.

    Returns:
        NetworkX graph or None
    """
    if nx is None:
        return None

    from content_matrix.parser import parse_all_knowledge_blocks, parse_memory_tables

    _ensure_dirs()
    all_extractions = []

    # Pass 1: Parse knowledge blocks (FREE)
    kb_extractions = parse_all_knowledge_blocks(knowledge_dir)
    for ext in kb_extractions:
        # Check cache
        source = ext.get("source_file", "")
        h = hashlib.sha256(json.dumps(ext["nodes"], default=str).encode()).hexdigest()
        cached = load_cache(h)
        if cached:
            all_extractions.append(cached)
            logger.debug(f"[GRAPH] Cache hit: {source}")
        else:
            all_extractions.append(ext)
            save_cache(h, ext)

    # Pass 1: Parse memory tables (FREE)
    if memory_data:
        mem_ext = parse_memory_tables(
            entities=memory_data.get("entities", []),
            lessons=memory_data.get("lessons", []),
            profile=memory_data.get("profile", []),
        )
        if mem_ext["nodes"]:
            all_extractions.append(mem_ext)

    # Build initial graph from Pass 1
    G = build_graph(all_extractions)
    if G is None:
        return None

    # Pass 2: Semantic connections (COSTS TOKENS, cached)
    if run_semantic and G.number_of_nodes() >= 3:
        semantic_cache_key = hashlib.sha256(
            json.dumps(sorted(G.nodes()), default=str).encode()
        ).hexdigest()

        cached_semantic = load_cache(f"semantic_{semantic_cache_key}")
        if cached_semantic:
            semantic_edges = cached_semantic.get("edges", [])
            logger.info(f"[GRAPH] Semantic cache hit: {len(semantic_edges)} edges")
        else:
            from content_matrix.connector import connect_semantic
            all_nodes = [{"id": nid, **attrs} for nid, attrs in G.nodes(data=True)]
            all_edges = [{"source": s, "target": t, **a} for s, t, a in G.edges(data=True)]
            semantic_edges = connect_semantic(all_nodes, all_edges)
            save_cache(f"semantic_{semantic_cache_key}", {"edges": semantic_edges})

        # Add semantic edges to graph
        for edge in semantic_edges:
            src, tgt = edge.get("source", ""), edge.get("target", "")
            if src in G.nodes and tgt in G.nodes:
                attrs = {k: v for k, v in edge.items() if k not in ("source", "target")}
                G.add_edge(src, tgt, **attrs)

    # Cluster
    cluster_graph(G)

    # Save
    save_graph(G)

    # Report
    gods = god_nodes(G)
    surprises = surprising_connections(G)
    logger.info(
        f"[GRAPH] Full build complete: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges, "
        f"{len(gods)} god nodes, {len(surprises)} surprising connections"
    )

    return G

# ============================================
# Content Matrix — Injector
# Wires the content graph into the operator's context
# Replaces flat memory injection with graph query
# ============================================

import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Module-level graph instance (loaded once at session start)
_graph = None


def load_content_graph(
    knowledge_dir: Optional[str] = None,
    memory_data: Optional[dict] = None,
    run_semantic: bool = True,
) -> bool:
    """
    Load or build the content graph at session start.
    Call once in the entrypoint. The graph persists in memory for the session.

    Returns True if graph is ready, False if not.
    """
    global _graph

    from content_matrix.graph_store import load_graph, build_full_graph

    # Try loading existing graph first (instant)
    _graph = load_graph()
    if _graph is not None:
        try:
            node_count = _graph.number_of_nodes()
            edge_count = _graph.number_of_edges()
            logger.info(f"[CONTENT] Loaded existing graph: {node_count} nodes, {edge_count} edges")
            return True
        except Exception:
            _graph = None

    # Build fresh if no existing graph
    if knowledge_dir is None:
        knowledge_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "development")

    _graph = build_full_graph(
        knowledge_dir=knowledge_dir,
        memory_data=memory_data,
        run_semantic=run_semantic,
    )

    if _graph is not None:
        logger.info(f"[CONTENT] Built new graph: {_graph.number_of_nodes()} nodes, {_graph.number_of_edges()} edges")
        return True
    else:
        logger.warning("[CONTENT] Graph build failed — falling back to flat memory")
        return False


def query_for_context(user_message: str, operator_name: str = "champ", top_n: int = 10) -> str:
    """
    Query the content graph for context relevant to this user message.
    Call on every user message (via hook or directly).

    Returns a formatted string to inject into the LLM context.
    Returns empty string if graph not loaded.

    This is FREE — no LLM call. In-memory keyword matching.
    """
    if _graph is None:
        return ""

    from content_matrix.graph_store import query_graph
    return query_graph(_graph, user_message, operator_name, top_n)


def get_graph_stats() -> dict:
    """Get current graph statistics."""
    if _graph is None:
        return {"loaded": False, "nodes": 0, "edges": 0}

    try:
        from content_matrix.graph_store import god_nodes, surprising_connections
        gods = god_nodes(_graph, top_n=5)
        surprises = surprising_connections(_graph, top_n=3)

        return {
            "loaded": True,
            "nodes": _graph.number_of_nodes(),
            "edges": _graph.number_of_edges(),
            "god_nodes": [g["label"] for g in gods],
            "surprising_connections": [
                f"{s['source']} → {s['relation']} → {s['target']}"
                for s in surprises
            ],
        }
    except Exception:
        return {"loaded": True, "nodes": 0, "edges": 0}


def get_graph():
    """Get the raw NetworkX graph for advanced queries."""
    return _graph
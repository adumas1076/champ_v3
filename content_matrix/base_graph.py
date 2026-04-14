# ============================================
# Cocreatiq OS — BaseGraph
# Universal graph class. Every domain graph inherits this.
# Built by extracting proven patterns from ContentGraph V1
# + Claude Code + Hermes + Graphify harvests.
#
# Usage:
#   class ContentGraph(BaseGraph):
#       name = "content"
#       node_types = ["framework", "element", "rule"]
#       relation_types = ["part_of", "supports", "contradicts"]
#
#   class ClientGraph(BaseGraph):
#       name = "client"
#       node_types = ["lead", "prospect", "client", "deal"]
#       relation_types = ["converted_to", "referred_by"]
# ============================================

import hashlib
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Any

logger = logging.getLogger(__name__)

try:
    import networkx as nx
except ImportError:
    nx = None
    logger.warning("[GRAPH] NetworkX not installed. pip install networkx")


# ---- Threat Scanning (Hermes pattern) ----

_THREAT_PATTERNS = [
    (r"ignore\s+(previous|all|above|prior)\s+instructions", "prompt_injection"),
    (r"you\s+are\s+now\s+", "role_hijack"),
    (r"do\s+not\s+tell\s+the\s+user", "deception"),
    (r"system\s+prompt\s+override", "sys_override"),
    (r"disregard\s+(your|all|any)\s+(instructions|rules)", "disregard"),
    (r"curl\s+[^\n]*\$\{?\w*(KEY|TOKEN|SECRET|PASSWORD|API)", "exfil_curl"),
    (r"wget\s+[^\n]*\$\{?\w*(KEY|TOKEN|SECRET|PASSWORD|API)", "exfil_wget"),
    (r"cat\s+[^\n]*(\.env|credentials|\.netrc|\.pgpass)", "read_secrets"),
    (r"authorized_keys", "ssh_backdoor"),
    (r"rm\s+-rf\s+/", "destructive"),
    (r"eval\s*\(", "code_injection"),
    (r"exec\s*\(", "code_injection"),
    (r"__import__", "code_injection"),
]

_INVISIBLE_CHARS = {
    "\u200b", "\u200c", "\u200d", "\u2060", "\ufeff",
    "\u202a", "\u202b", "\u202c", "\u202d", "\u202e",
}

# ---- Confidence Levels ----

CONFIDENCE_LEVELS = ["AMBIGUOUS", "INFERRED", "EXTRACTED", "PROVEN"]
CONFIDENCE_ORDER = {c: i for i, c in enumerate(CONFIDENCE_LEVELS)}

# ---- Decay Config ----

DECAY_DAYS_THRESHOLD = 90
DECAY_FACTOR = 0.9
IMMUNE_CONFIDENCES = {"PROVEN"}

# ---- Stop Words for Query ----

_STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "to", "of", "in",
    "for", "on", "with", "at", "by", "from", "as", "into", "through",
    "during", "before", "after", "between", "out", "off", "over", "under",
    "again", "then", "once", "here", "there", "when", "where", "why", "how",
    "all", "both", "each", "few", "more", "most", "other", "some", "such",
    "no", "nor", "not", "only", "own", "same", "so", "than", "too", "very",
    "just", "don", "now", "and", "but", "or", "if", "it", "its", "i", "me",
    "my", "we", "our", "you", "your", "he", "she", "they", "them", "what",
    "which", "who", "this", "that", "these", "those", "am", "up", "about",
    "get", "got", "like", "yeah", "okay", "right", "well", "know", "think",
    "want", "tell", "say", "said", "champ", "bro", "man", "hey", "yo",
}


class BaseGraph:
    """
    Universal graph class for Cocreatiq OS.
    Every domain graph (content, conversation, client, operations) inherits this.
    All operations — query, cache, cluster, analytics, security, visualization — built in.
    """

    # ---- Override in subclass ----
    name: str = "base"
    node_types: list[str] = []
    relation_types: list[str] = []

    def __init__(self, storage_dir: Optional[str] = None):
        if nx is None:
            raise ImportError("NetworkX required. pip install networkx")

        self.G = nx.Graph()
        self._snapshot = None  # Frozen copy for session (Hermes pattern)
        self._storage_dir = Path(storage_dir) if storage_dir else Path.home() / ".champ" / "graphs" / self.name
        self._cache_dir = self._storage_dir / "cache"
        self._graph_path = self._storage_dir / "graph.json"
        self._ensure_dirs()

        logger.info(f"[{self.name.upper()}] Graph initialized | storage: {self._storage_dir}")

    def _ensure_dirs(self):
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    # ============================================
    # NODES
    # ============================================

    def add_node(
        self,
        node_id: str,
        label: str,
        node_type: str,
        source: str = "",
        source_type: str = "",
        scope: Optional[list[str]] = None,
        metadata: Optional[dict] = None,
    ) -> bool:
        """
        Add a node with universal schema.
        Validates, scans for threats, sets defaults.
        Returns True if added, False if blocked.
        """
        # Threat scan on label
        threat = self._scan(label)
        if threat:
            logger.warning(f"[{self.name.upper()}] Node blocked — {threat}: {label[:50]}")
            return False

        now = datetime.now(timezone.utc).isoformat()
        self.G.add_node(node_id, **{
            "label": label[:500],
            "type": node_type,
            "source": source,
            "source_type": source_type,
            "scope": scope or [self.name],
            "hash": self._hash(label),
            "created_at": now,
            "updated_at": now,
            "metadata": metadata or {},
            # Analytics
            "query_count": 0,
            "last_queried": None,
            "success_score": 0.0,
            "operator_usage": {},
            # Freshness
            "freshness": 1.0,
        })
        return True

    def add_nodes_bulk(self, nodes: list[dict]) -> int:
        """Add multiple nodes. Returns count added."""
        added = 0
        for n in nodes:
            ok = self.add_node(
                node_id=n.get("id", ""),
                label=n.get("label", ""),
                node_type=n.get("type", n.get("source_type", "")),
                source=n.get("source_file", n.get("source", "")),
                source_type=n.get("source_type", ""),
                scope=n.get("scope", n.get("operator_scope")),
                metadata=n.get("metadata"),
            )
            if ok:
                added += 1
        return added

    # ============================================
    # EDGES
    # ============================================

    def add_edge(
        self,
        source: str,
        target: str,
        relation: str,
        confidence: str = "INFERRED",
        weight: float = 0.5,
        reason: str = "",
    ) -> bool:
        """
        Add an edge with confidence scoring.
        Both nodes must exist. Confidence must be valid.
        """
        if source not in self.G.nodes or target not in self.G.nodes:
            return False

        if confidence not in CONFIDENCE_LEVELS:
            confidence = "INFERRED"

        now = datetime.now(timezone.utc).isoformat()

        # Check if edge exists — if so, promote
        if self.G.has_edge(source, target):
            existing = self.G.edges[source, target]
            seen = existing.get("seen_count", 1) + 1
            self.G.edges[source, target]["seen_count"] = seen
            self.G.edges[source, target]["last_seen"] = now
            self._promote_edge(source, target, seen)
            return True

        self.G.add_edge(source, target, **{
            "relation": relation,
            "confidence": confidence,
            "weight": weight,
            "reason": reason[:200],
            "seen_count": 1,
            "created_at": now,
            "last_seen": now,
        })
        return True

    def add_edges_bulk(self, edges: list[dict]) -> int:
        """Add multiple edges. Returns count added."""
        added = 0
        for e in edges:
            ok = self.add_edge(
                source=e.get("source", ""),
                target=e.get("target", ""),
                relation=e.get("relation", "related_to"),
                confidence=e.get("confidence", "INFERRED"),
                weight=e.get("weight", 0.5),
                reason=e.get("reason", ""),
            )
            if ok:
                added += 1
        return added

    def _promote_edge(self, source: str, target: str, seen_count: int):
        """Promote edge confidence based on evidence. AMBIGUOUS → INFERRED → EXTRACTED → PROVEN."""
        edge = self.G.edges[source, target]
        conf = edge.get("confidence", "AMBIGUOUS")
        score = edge.get("weight", 0.5)

        if seen_count >= 5 and score > 0.7 and conf != "PROVEN":
            edge["confidence"] = "PROVEN"
            edge["weight"] = 0.95
        elif seen_count >= 3 and conf in ("AMBIGUOUS", "INFERRED"):
            edge["confidence"] = "EXTRACTED"
            edge["weight"] = max(score, 0.85)
        elif seen_count >= 2 and conf == "AMBIGUOUS":
            edge["confidence"] = "INFERRED"
            edge["weight"] = max(score, 0.6)

    # ============================================
    # PARSE — Override in subclass
    # ============================================

    def parse(self, source: Any) -> dict:
        """
        Pass 1: Deterministic extraction. FREE. No LLM.
        Override in subclass for domain-specific parsing.

        Returns: {"nodes": [...], "edges": [...]}
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement parse()")

    # ============================================
    # CONNECT — LLM semantic relationships (cached)
    # ============================================

    def connect(self, model: str = "gpt-4o-mini", max_relationships: int = 30) -> list[dict]:
        """
        Pass 2: LLM finds cross-content relationships. CACHED.
        Runs once per content batch. Generic — works for any graph.
        """
        import requests

        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key or self.G.number_of_nodes() < 3:
            return []

        # Check cache
        cache_key = f"semantic_{self._hash(json.dumps(sorted(self.G.nodes()), default=str))}"
        cached = self._load_cache(cache_key)
        if cached:
            edges = cached.get("edges", [])
            logger.info(f"[{self.name.upper()}] Semantic cache hit: {len(edges)} edges")
            return edges

        # Build compact node summaries
        summaries = []
        for nid, attrs in list(self.G.nodes(data=True))[:100]:
            label = attrs.get("label", "")[:100]
            ntype = attrs.get("type", "")
            summaries.append(f"[{nid}] ({ntype}) {label}")

        existing_edges = {(s, t) for s, t, _ in self.G.edges(data=True)}

        prompt = f"""You are a knowledge graph builder. Given these nodes from a {self.name} graph, find meaningful relationships.

NODES:
{chr(10).join(summaries)}

Return ONLY a JSON array. Each item: {{"source": "id", "target": "id", "relation": "type", "confidence": "INFERRED|AMBIGUOUS", "reason": "one sentence"}}
Focus on CROSS-SOURCE connections. Skip obvious part_of. Max {max_relationships}."""

        try:
            resp = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "Return only valid JSON arrays."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 2000,
                },
                timeout=30,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"].strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1] if "\n" in content else content
                content = content.rsplit("```", 1)[0] if "```" in content else content

            edges = json.loads(content.strip())
            if not isinstance(edges, list):
                edges = []

            # Validate
            node_ids = set(self.G.nodes())
            valid = []
            for e in edges:
                s, t = e.get("source", ""), e.get("target", "")
                if s in node_ids and t in node_ids and (s, t) not in existing_edges:
                    e["confidence"] = e.get("confidence", "INFERRED")
                    if e["confidence"] not in CONFIDENCE_LEVELS:
                        e["confidence"] = "INFERRED"
                    valid.append(e)

            self._save_cache(cache_key, {"edges": valid})
            logger.info(f"[{self.name.upper()}] Semantic: {len(valid)} relationships found")
            return valid

        except Exception as e:
            logger.warning(f"[{self.name.upper()}] Semantic connect failed: {e}")
            return []

    # ============================================
    # BUILD — Merge extractions into graph
    # ============================================

    def build(self, extractions: list[dict]) -> int:
        """Merge multiple parse results into the graph. Returns total nodes added."""
        total = 0
        for ext in extractions:
            total += self.add_nodes_bulk(ext.get("nodes", []))
            self.add_edges_bulk(ext.get("edges", []))
        logger.info(f"[{self.name.upper()}] Built: {self.G.number_of_nodes()} nodes, {self.G.number_of_edges()} edges")
        return total

    # ============================================
    # CLUSTER — Auto-group related nodes
    # ============================================

    def cluster(self) -> dict:
        """Louvain community detection. Returns {cluster_id: [node_ids]}."""
        if self.G.number_of_nodes() < 2:
            return {}
        try:
            communities = nx.community.louvain_communities(self.G, seed=42)
            result = {}
            for idx, community in enumerate(communities):
                for nid in community:
                    self.G.nodes[nid]["cluster"] = idx
                result[idx] = list(community)
            logger.info(f"[{self.name.upper()}] Clustered: {len(result)} communities")
            return result
        except Exception as e:
            logger.warning(f"[{self.name.upper()}] Clustering failed: {e}")
            return {}

    # ============================================
    # QUERY — Find relevant nodes. FREE.
    # ============================================

    def query(
        self,
        text: str,
        scope: str = "",
        top_n: int = 10,
    ) -> str:
        """
        Query graph for nodes relevant to text. FREE — no LLM.
        Returns formatted context string for prompt injection.
        """
        if self.G.number_of_nodes() == 0:
            return ""

        keywords = self._extract_keywords(text)
        if not keywords:
            return ""

        scored = []
        for nid, attrs in self.G.nodes(data=True):
            label = attrs.get("label", "").lower()
            node_scope = attrs.get("scope", [])

            # Scope filter
            if scope and scope not in node_scope and self.name not in node_scope:
                continue

            # Keyword score
            score = sum(1 for kw in keywords if kw in label)

            # Boost by type
            ntype = attrs.get("type", "")
            if ntype in ("framework", "entity"):
                score *= 1.5
            # Boost by freshness
            score *= attrs.get("freshness", 1.0)

            if score > 0:
                scored.append((nid, score))

        if not scored:
            return ""

        # Top N + 1-hop neighbors
        top = sorted(scored, key=lambda x: x[1], reverse=True)[:top_n]
        context_nodes = set()
        for nid, _ in top:
            context_nodes.add(nid)
            for neighbor in self.G.neighbors(nid):
                context_nodes.add(neighbor)

        # Cap
        if len(context_nodes) > top_n * 3:
            context_nodes = {nid for nid, _ in top}
            for nid, _ in top:
                neighbors = sorted(self.G.neighbors(nid), key=lambda n: self.G.degree(n), reverse=True)[:2]
                context_nodes.update(neighbors)

        # Build injection
        lines = [f"## RELEVANT KNOWLEDGE ({self.name})"]
        for nid in context_nodes:
            if nid not in self.G.nodes:
                continue
            attrs = self.G.nodes[nid]
            label = attrs.get("label", nid)
            ntype = attrs.get("type", "")
            lines.append(f"- [{ntype}] {label}")

            # Track analytics
            attrs["query_count"] = attrs.get("query_count", 0) + 1
            attrs["last_queried"] = datetime.now(timezone.utc).isoformat()
            if scope:
                usage = attrs.get("operator_usage", {})
                usage[scope] = usage.get(scope, 0) + 1
                attrs["operator_usage"] = usage
            # Reset freshness on query (evidence overrides time)
            attrs["freshness"] = 1.0

            # Relationship context for direct matches
            if nid in {n for n, _ in top}:
                for neighbor in self.G.neighbors(nid):
                    if neighbor in context_nodes and neighbor in self.G.nodes:
                        edge = self.G.edges.get((nid, neighbor), {})
                        rel = edge.get("relation", "related_to")
                        conf = edge.get("confidence", "")
                        nlabel = self.G.nodes[neighbor].get("label", neighbor)[:80]
                        lines.append(f"  -> {rel} [{conf}]: {nlabel}")

        result = "\n".join(lines)
        logger.info(f"[{self.name.upper()}] Query '{text[:40]}' -> {len(context_nodes)} nodes, {len(result)} chars")
        return result

    # ============================================
    # RECALL — LLM semantic relevance (Claude Code pattern)
    # ============================================

    def recall(self, text: str, scope: str = "", top_n: int = 5) -> str:
        """
        Semantic recall via LLM side-query. COSTS TOKENS.
        Use for ambiguous queries where keyword matching isn't enough.
        Falls back to query() if LLM fails.
        """
        import requests

        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            return self.query(text, scope, top_n)

        # Build node manifest (Claude Code pattern — names + descriptions)
        manifest = []
        for nid, attrs in self.G.nodes(data=True):
            node_scope = attrs.get("scope", [])
            if scope and scope not in node_scope:
                continue
            label = attrs.get("label", "")[:100]
            ntype = attrs.get("type", "")
            manifest.append(f"[{nid}] ({ntype}) {label}")

        if not manifest:
            return ""

        try:
            resp = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": f"Select up to {top_n} nodes most relevant to the query. Return ONLY a JSON array of node IDs. Be selective."},
                        {"role": "user", "content": f"Query: {text}\n\nNodes:\n{chr(10).join(manifest[:80])}"},
                    ],
                    "temperature": 0.1,
                    "max_tokens": 200,
                },
                timeout=15,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"].strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0]
            selected = json.loads(content)
            if not isinstance(selected, list):
                return self.query(text, scope, top_n)

            # Build context from selected nodes
            lines = [f"## RELEVANT KNOWLEDGE ({self.name})"]
            for nid in selected:
                if nid in self.G.nodes:
                    attrs = self.G.nodes[nid]
                    lines.append(f"- [{attrs.get('type', '')}] {attrs.get('label', nid)}")
                    attrs["query_count"] = attrs.get("query_count", 0) + 1
                    attrs["freshness"] = 1.0

            return "\n".join(lines)

        except Exception:
            return self.query(text, scope, top_n)

    # ============================================
    # TRACK — Log query outcomes
    # ============================================

    def track(self, node_id: str, success: bool):
        """Track whether a queried node actually helped the user."""
        if node_id not in self.G.nodes:
            return
        attrs = self.G.nodes[node_id]
        current = attrs.get("success_score", 0.0)
        count = attrs.get("query_count", 1)
        # Running average
        attrs["success_score"] = ((current * (count - 1)) + (1.0 if success else 0.0)) / count

    # ============================================
    # DECAY — Time-based freshness
    # ============================================

    def decay(self):
        """
        Reduce freshness on stale nodes.
        Decay unless: PROVEN, recently queried, recently connected, or healing.
        Evidence overrides time.
        """
        now = time.time()
        threshold = DECAY_DAYS_THRESHOLD * 86400

        for nid, attrs in self.G.nodes(data=True):
            # Immune: PROVEN nodes never decay
            edges = list(self.G.edges(nid, data=True))
            has_proven = any(e[2].get("confidence") in IMMUNE_CONFIDENCES for e in edges)
            if has_proven:
                continue

            # Immune: recently queried (freshness already reset by query)
            last_q = attrs.get("last_queried")
            if last_q:
                continue  # Was queried this session, skip

            # Immune: healing nodes
            if attrs.get("type") == "healing" or attrs.get("source") == "mem_healing":
                continue

            # Decay
            created = attrs.get("created_at", "")
            if created:
                try:
                    created_ts = datetime.fromisoformat(created.replace("Z", "+00:00")).timestamp()
                    age = now - created_ts
                    if age > threshold:
                        current = attrs.get("freshness", 1.0)
                        attrs["freshness"] = max(0.1, current * DECAY_FACTOR)
                except (ValueError, TypeError):
                    pass

    # ============================================
    # CROSS-GRAPH REFERENCES
    # ============================================

    def cross_ref(self, local_node_id: str, remote_graph: str, remote_node_id: str, relation: str = "cross_ref"):
        """Create a cross-graph reference. Stored as metadata on the local node."""
        if local_node_id not in self.G.nodes:
            return False

        refs = self.G.nodes[local_node_id].get("metadata", {}).get("cross_refs", [])
        ref = {"graph": remote_graph, "node_id": remote_node_id, "relation": relation}
        if ref not in refs:
            refs.append(ref)
            if "metadata" not in self.G.nodes[local_node_id]:
                self.G.nodes[local_node_id]["metadata"] = {}
            self.G.nodes[local_node_id]["metadata"]["cross_refs"] = refs
        return True

    # ============================================
    # HEALTH METRICS
    # ============================================

    def health(self) -> dict:
        """Report graph health. System monitors itself."""
        if self.G.number_of_nodes() == 0:
            return {"name": self.name, "healthy": False, "reason": "empty"}

        total_nodes = self.G.number_of_nodes()
        total_edges = self.G.number_of_edges()

        # Orphans
        orphans = [n for n in self.G.nodes() if self.G.degree(n) == 0]

        # Confidence distribution
        conf_dist = {"AMBIGUOUS": 0, "INFERRED": 0, "EXTRACTED": 0, "PROVEN": 0}
        for _, _, attrs in self.G.edges(data=True):
            c = attrs.get("confidence", "INFERRED")
            if c in conf_dist:
                conf_dist[c] += 1

        # Never queried
        never_queried = sum(1 for _, a in self.G.nodes(data=True) if a.get("query_count", 0) == 0)

        # Average freshness
        freshness_vals = [a.get("freshness", 1.0) for _, a in self.G.nodes(data=True)]
        avg_freshness = sum(freshness_vals) / len(freshness_vals) if freshness_vals else 0

        return {
            "name": self.name,
            "healthy": True,
            "nodes": total_nodes,
            "edges": total_edges,
            "orphans": len(orphans),
            "orphan_pct": round(len(orphans) / total_nodes * 100, 1),
            "confidence": conf_dist,
            "never_queried": never_queried,
            "never_queried_pct": round(never_queried / total_nodes * 100, 1),
            "avg_freshness": round(avg_freshness, 3),
        }

    # ============================================
    # SNAPSHOT — Frozen load (Hermes pattern)
    # ============================================

    def snapshot(self) -> "BaseGraph":
        """Freeze graph state for session. Prefix cache optimization."""
        import copy
        self._snapshot = copy.deepcopy(self.G)
        logger.info(f"[{self.name.upper()}] Snapshot frozen: {self._snapshot.number_of_nodes()} nodes")
        return self

    def get_snapshot_context(self, scope: str = "", max_chars: int = 2000) -> str:
        """Get a compact context string from the frozen snapshot for system prompt injection."""
        G = self._snapshot or self.G
        lines = [f"## {self.name.upper()} KNOWLEDGE"]

        # God nodes first
        gods = self.god_nodes(top_n=5)
        if gods:
            for g in gods:
                lines.append(f"- [CORE] {g['label'][:80]} ({g['edges']} connections)")

        current_chars = sum(len(l) for l in lines)
        if current_chars >= max_chars:
            return "\n".join(lines)

        # Then cluster summaries
        clusters = {}
        for nid, attrs in G.nodes(data=True):
            c = attrs.get("cluster", -1)
            if c >= 0:
                if c not in clusters:
                    clusters[c] = []
                clusters[c].append(attrs.get("label", nid)[:50])

        for cid, labels in sorted(clusters.items()):
            summary = f"- Cluster {cid}: {', '.join(labels[:3])}"
            if current_chars + len(summary) > max_chars:
                break
            lines.append(summary)
            current_chars += len(summary)

        return "\n".join(lines)

    # ============================================
    # PERSIST / LOAD
    # ============================================

    def persist(self):
        """Save graph to JSON. Atomic write (Graphify pattern)."""
        data = {
            "name": self.name,
            "nodes": [{"id": nid, **{k: v for k, v in attrs.items()}} for nid, attrs in self.G.nodes(data=True)],
            "edges": [{"source": s, "target": t, **{k: v for k, v in a.items()}} for s, t, a in self.G.edges(data=True)],
            "meta": {
                "node_count": self.G.number_of_nodes(),
                "edge_count": self.G.number_of_edges(),
                "saved_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        tmp = self._graph_path.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(data, default=str, indent=2), encoding="utf-8")
            os.replace(tmp, self._graph_path)
            logger.info(f"[{self.name.upper()}] Persisted: {self._graph_path}")
        except Exception:
            tmp.unlink(missing_ok=True)
            raise

    def load(self) -> bool:
        """Load graph from JSON. Returns True if loaded."""
        if not self._graph_path.exists():
            return False
        try:
            data = json.loads(self._graph_path.read_text(encoding="utf-8"))
            self.G = nx.Graph()
            for n in data.get("nodes", []):
                nid = n.pop("id", "")
                if nid:
                    self.G.add_node(nid, **n)
            node_set = set(self.G.nodes())
            for e in data.get("edges", []):
                s, t = e.pop("source", ""), e.pop("target", "")
                if s in node_set and t in node_set:
                    self.G.add_edge(s, t, **e)
            logger.info(f"[{self.name.upper()}] Loaded: {self.G.number_of_nodes()} nodes, {self.G.number_of_edges()} edges")
            return True
        except Exception as e:
            logger.warning(f"[{self.name.upper()}] Load failed: {e}")
            return False

    # ============================================
    # ANALYSIS
    # ============================================

    def god_nodes(self, top_n: int = 10) -> list[dict]:
        """Most connected nodes = core concepts."""
        G = self._snapshot or self.G
        degree = dict(G.degree())
        sorted_nodes = sorted(degree.items(), key=lambda x: x[1], reverse=True)
        results = []
        for nid, deg in sorted_nodes[:top_n]:
            attrs = G.nodes[nid]
            results.append({
                "id": nid,
                "label": attrs.get("label", nid),
                "edges": deg,
                "type": attrs.get("type", ""),
                "cluster": attrs.get("cluster", -1),
            })
        return results

    def surprising(self, top_n: int = 5) -> list[dict]:
        """Cross-cluster connections = non-obvious insights."""
        G = self._snapshot or self.G
        results = []
        for src, tgt, attrs in G.edges(data=True):
            sc = G.nodes[src].get("cluster", -1)
            tc = G.nodes[tgt].get("cluster", -1)
            if sc != tc and sc >= 0 and tc >= 0:
                results.append({
                    "source": G.nodes[src].get("label", src),
                    "target": G.nodes[tgt].get("label", tgt),
                    "relation": attrs.get("relation", ""),
                    "confidence": attrs.get("confidence", ""),
                    "reason": attrs.get("reason", ""),
                })
        conf_order = {"AMBIGUOUS": 0, "INFERRED": 1, "EXTRACTED": 2, "PROVEN": 3}
        results.sort(key=lambda x: conf_order.get(x["confidence"], 99))
        return results[:top_n]

    # ============================================
    # SECURITY — Threat scanning (Hermes pattern)
    # ============================================

    def _scan(self, content: str) -> Optional[str]:
        """Scan content for injection/exfiltration patterns."""
        for char in _INVISIBLE_CHARS:
            if char in content:
                return f"invisible_unicode_U+{ord(char):04X}"
        for pattern, threat_type in _THREAT_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                return threat_type
        return None

    # ============================================
    # CACHE — SHA-256 (Graphify pattern)
    # ============================================

    def _hash(self, content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()

    def _load_cache(self, key: str) -> Optional[dict]:
        path = self._cache_dir / f"{key}.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def _save_cache(self, key: str, data: dict):
        path = self._cache_dir / f"{key}.json"
        tmp = path.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(data, default=str), encoding="utf-8")
            os.replace(tmp, path)
        except Exception:
            tmp.unlink(missing_ok=True)

    # ============================================
    # HELPERS
    # ============================================

    def _extract_keywords(self, text: str) -> list[str]:
        words = re.findall(r"\b[a-z]+\b", text.lower())
        return [w for w in words if w not in _STOP_WORDS and len(w) > 2]

    def __repr__(self):
        return f"<{self.__class__.__name__} '{self.name}': {self.G.number_of_nodes()} nodes, {self.G.number_of_edges()} edges>"
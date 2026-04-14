# ============================================
# Cocreatiq OS — MarketingGraph
# First graph that inherits from BaseGraph.
# Tracks content creation, publishing, scoring, and lead capture.
#
# Schema locked 2026-04-14 with Marketing Machine session:
#   - 11 node types
#   - 11 relationship types
#   - 3 content_piece properties (funnel_stage, kpi_stage, content_tier)
#   - Universal waitlist_lead node with source_type (4 capture channels)
#   - hook as first-class node (cross-face performance aggregation)
#   - eval_score + performance_score as separate nodes (time-series preservation)
#
# Writes from: publishers/*, scoring.py, eval.py, orchestrator.py,
#              capture/waitlist.py, capture/assessment.py, autoresearch.py
#
# The V1 Killer Query:
#   "Which face + platform + kpi_stage + hook generated the most HOT/BUYER
#    tier assessment leads?"
# ============================================

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, Any

from content_matrix.base_graph import BaseGraph

logger = logging.getLogger(__name__)


# ============================================
# Schema Constants
# ============================================

NODE_TYPES = [
    "content_piece",      # The post itself (tweet, reel, video)
    "influencer",         # Anthony / AI Face 1 / AI Face 2 / AI Face 3
    "platform",           # twitter / instagram / linkedin / tiktok / youtube / facebook
    "hook",               # Opening line pattern (cross-face shareable)
    "script",             # Full content body
    "eval_score",         # Pre-publish score (QA Operator, Lamar + Gary Vee)
    "publish_result",     # API response from publisher (success/fail)
    "performance_score",  # Post-publish score (48hr / 7-day / 30-day snapshots)
    "pattern",            # Autoresearch-proven pattern
    "trend",              # Trend Scout discoveries
    "waitlist_lead",      # Universal capture node (4 source types)
]

RELATION_TYPES = [
    "published_on",       # content_piece -> platform
    "created_by",         # content_piece -> influencer
    "used_hook",          # content_piece -> hook
    "pre_scored_as",      # content_piece -> eval_score (pre-publish)
    "post_scored_as",     # content_piece -> performance_score (post-publish)
    "posted_result",      # content_piece -> publish_result
    "converted_to_lead",  # content_piece -> waitlist_lead (THE V1 METRIC)
    "uses_framework",     # content_piece -> knowledge_node (cross-graph)
    "proved_pattern",     # performance_score -> pattern
    "derived_from",       # trend -> content_piece
    "outperformed",       # content_piece -> content_piece
]

# content_piece properties (not nodes — only 4 values each)
FUNNEL_STAGES = ["cold", "warm", "hot", "buyer"]
KPI_STAGES = ["know", "like", "trust", "convert"]
CONTENT_TIERS = ["text", "voice", "video", "static"]

# waitlist_lead source types
CAPTURE_SOURCES = ["waitlist", "assessment", "dm_keyword", "profile_link"]

# performance_score time windows
SCORE_WINDOWS = ["48hr", "7day", "30day"]


class MarketingGraph(BaseGraph):
    """
    Marketing graph — tracks content pipeline from creation to conversion.
    Every role in the Marketing Department writes to this graph.

    Inherits from BaseGraph:
      - Nodes, edges, confidence promotion, caching, clustering
      - Query (free), recall (LLM), analytics tracking, threat scanning
      - Decay, cross-graph refs, health metrics, snapshot, persist/load
      - God nodes, surprising connections

    Domain-specific:
      - parse() methods for each data source
      - killer_query() — the V1 win condition query
      - content_piece convenience methods
    """

    name = "marketing"
    node_types = NODE_TYPES
    relation_types = RELATION_TYPES

    # ============================================
    # WRITE APIS — Each role in the department calls these
    # ============================================

    def write_influencer(self, influencer_id: str, name: str, niche: str = "", brand_voice: dict = None) -> bool:
        """Called by orchestrator on startup — one influencer node per face."""
        return self.add_node(
            node_id=f"influencer_{influencer_id}",
            label=name,
            node_type="influencer",
            source="influencers/*.yaml",
            source_type="config",
            scope=["marketing", "champ"],
            metadata={"niche": niche, "brand_voice": brand_voice or {}},
        )

    def write_platform(self, platform: str) -> bool:
        """Called when first post goes to a platform."""
        return self.add_node(
            node_id=f"platform_{platform}",
            label=platform.capitalize(),
            node_type="platform",
            source="publishers",
            source_type="config",
            scope=["marketing", "champ"],
        )

    def write_content_piece(
        self,
        piece_id: str,
        topic: str,
        influencer_id: str,
        platform: str,
        funnel_stage: str = "cold",
        kpi_stage: str = "know",
        content_tier: str = "text",
        cta_keyword: str = "",
    ) -> bool:
        """STRATEGIST output — called by orchestrator after planning."""
        # Validate properties
        if funnel_stage not in FUNNEL_STAGES:
            funnel_stage = "cold"
        if kpi_stage not in KPI_STAGES:
            kpi_stage = "know"
        if content_tier not in CONTENT_TIERS:
            content_tier = "text"

        ok = self.add_node(
            node_id=f"content_{piece_id}",
            label=topic[:200],
            node_type="content_piece",
            source="orchestrator",
            source_type="planned",
            scope=["marketing", "champ"],
            metadata={
                "funnel_stage": funnel_stage,
                "kpi_stage": kpi_stage,
                "content_tier": content_tier,
                "cta_keyword": cta_keyword,
                "status": "planned",
            },
        )
        if not ok:
            return False

        # Connect to influencer
        self.add_edge(
            source=f"content_{piece_id}",
            target=f"influencer_{influencer_id}",
            relation="created_by",
            confidence="EXTRACTED",
            weight=1.0,
        )

        # Connect to platform (auto-create if missing)
        if f"platform_{platform}" not in self.G.nodes:
            self.write_platform(platform)
        self.add_edge(
            source=f"content_{piece_id}",
            target=f"platform_{platform}",
            relation="published_on",
            confidence="EXTRACTED",
            weight=1.0,
        )

        return True

    def write_hook(self, hook_text: str, hook_pattern: str = "") -> str:
        """
        CREATOR output — write a hook node.
        Hooks are cross-face shareable — same structural hook used by multiple influencers
        aggregates performance across the graph.

        Returns the hook_id so it can be linked to content pieces.
        """
        # Normalize hook by pattern (not exact text) so "Did you know X?" and "Did you know Y?"
        # map to the same hook pattern node
        hook_id = f"hook_{self._hash(hook_pattern or hook_text)[:16]}"

        if hook_id not in self.G.nodes:
            self.add_node(
                node_id=hook_id,
                label=hook_text[:200],
                node_type="hook",
                source="creator",
                source_type="generated",
                scope=["marketing", "champ"],
                metadata={"pattern": hook_pattern or hook_text[:50]},
            )
        return hook_id

    def link_hook_to_content(self, piece_id: str, hook_id: str) -> bool:
        """Link a content piece to its hook."""
        return self.add_edge(
            source=f"content_{piece_id}",
            target=hook_id,
            relation="used_hook",
            confidence="EXTRACTED",
            weight=1.0,
        )

    def write_script(self, piece_id: str, script_text: str) -> bool:
        """CREATOR output — link script to content piece via metadata (not a separate node for V1)."""
        if f"content_{piece_id}" not in self.G.nodes:
            return False
        self.G.nodes[f"content_{piece_id}"]["metadata"]["script_preview"] = script_text[:500]
        self.G.nodes[f"content_{piece_id}"]["metadata"]["script_length"] = len(script_text)
        self.G.nodes[f"content_{piece_id}"]["metadata"]["status"] = "scripted"
        return True

    def write_eval_score(
        self,
        piece_id: str,
        score: float,
        verdict: str,
        passed: bool,
        notes: str = "",
    ) -> bool:
        """QA OPERATOR output — pre-publish score (Lamar + Gary Vee eval)."""
        eval_id = f"eval_{piece_id}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        ok = self.add_node(
            node_id=eval_id,
            label=f"Eval: {score:.1f} ({verdict})",
            node_type="eval_score",
            source="qa_operator",
            source_type="pre_publish",
            scope=["marketing", "champ"],
            metadata={
                "score": score,
                "verdict": verdict,
                "passed": passed,
                "notes": notes[:500],
            },
        )
        if not ok:
            return False

        self.add_edge(
            source=f"content_{piece_id}",
            target=eval_id,
            relation="pre_scored_as",
            confidence="EXTRACTED",
            weight=1.0,
        )

        # Update content piece status
        if f"content_{piece_id}" in self.G.nodes:
            status = "qa_pass" if passed else "qa_fail"
            self.G.nodes[f"content_{piece_id}"]["metadata"]["status"] = status

        return True

    def write_publish_result(
        self,
        piece_id: str,
        platform: str,
        success: bool,
        post_id: str = "",
        post_url: str = "",
        error: str = "",
    ) -> bool:
        """PUBLISHER output — API response from platform."""
        result_id = f"publish_{piece_id}_{platform}"
        ok = self.add_node(
            node_id=result_id,
            label=f"Published to {platform}" if success else f"Failed: {platform}",
            node_type="publish_result",
            source=f"publishers/{platform}",
            source_type="api_result",
            scope=["marketing", "champ"],
            metadata={
                "success": success,
                "platform": platform,
                "post_id": post_id,
                "post_url": post_url,
                "error": error[:500],
                "published_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        if not ok:
            return False

        self.add_edge(
            source=f"content_{piece_id}",
            target=result_id,
            relation="posted_result",
            confidence="EXTRACTED",
            weight=1.0,
        )

        # Update content piece status
        if f"content_{piece_id}" in self.G.nodes:
            self.G.nodes[f"content_{piece_id}"]["metadata"]["status"] = "posted" if success else "failed"
            self.G.nodes[f"content_{piece_id}"]["metadata"]["post_url"] = post_url

        return True

    def write_performance_score(
        self,
        piece_id: str,
        window: str,
        overall: float,
        verdict: str,
        signals: dict = None,
    ) -> bool:
        """
        ANALYST output — post-publish score (5-signal scoring).
        Creates a NEW node per window (48hr, 7day, 30day) — preserves time series.
        """
        if window not in SCORE_WINDOWS:
            window = "48hr"

        perf_id = f"perf_{piece_id}_{window}"
        ok = self.add_node(
            node_id=perf_id,
            label=f"{window}: {overall:.1f} ({verdict})",
            node_type="performance_score",
            source="analyst",
            source_type=f"post_publish_{window}",
            scope=["marketing", "champ"],
            metadata={
                "window": window,
                "overall": overall,
                "verdict": verdict,
                "signals": signals or {},
                "scored_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        if not ok:
            return False

        self.add_edge(
            source=f"content_{piece_id}",
            target=perf_id,
            relation="post_scored_as",
            confidence="EXTRACTED",
            weight=1.0,
        )
        return True

    def write_waitlist_lead(
        self,
        lead_id: str,
        email: str,
        source_type: str,
        tier: Optional[str] = None,
        source_content_id: str = "",
        source_influencer_id: str = "",
        metadata: dict = None,
    ) -> bool:
        """
        Universal capture — writes from all 4 capture channels.

        source_type: waitlist | assessment | dm_keyword | profile_link
        tier (assessment only): cold | warm | hot | buyer

        This is THE V1 conversion node. Every lead flows here.
        """
        if source_type not in CAPTURE_SOURCES:
            source_type = "waitlist"

        lead_node_id = f"lead_{lead_id}"
        ok = self.add_node(
            node_id=lead_node_id,
            label=f"{email} [{source_type}{':' + tier if tier else ''}]",
            node_type="waitlist_lead",
            source=f"capture/{source_type}",
            source_type=source_type,
            scope=["marketing", "lead_gen", "champ"],
            metadata={
                "email": email,
                "source_type": source_type,
                "tier": tier,
                "captured_at": datetime.now(timezone.utc).isoformat(),
                **(metadata or {}),
            },
        )
        if not ok:
            return False

        # THE V1 METRIC EDGE — content -> lead
        if source_content_id and f"content_{source_content_id}" in self.G.nodes:
            self.add_edge(
                source=f"content_{source_content_id}",
                target=lead_node_id,
                relation="converted_to_lead",
                confidence="EXTRACTED",
                weight=1.0 if tier == "buyer" else (0.8 if tier == "hot" else 0.5),
            )

        return True

    def write_trend(self, trend_text: str, source: str = "trend_scout", metadata: dict = None) -> str:
        """TREND SCOUT output — discovered trend."""
        trend_id = f"trend_{self._hash(trend_text)[:16]}"
        self.add_node(
            node_id=trend_id,
            label=trend_text[:200],
            node_type="trend",
            source=source,
            source_type="discovered",
            scope=["marketing", "research", "champ"],
            metadata=metadata or {},
        )
        return trend_id

    def write_pattern(self, pattern_text: str, confidence: str = "INFERRED", evidence_count: int = 1) -> str:
        """AUTORESEARCH output — proven pattern."""
        pattern_id = f"pattern_{self._hash(pattern_text)[:16]}"
        self.add_node(
            node_id=pattern_id,
            label=pattern_text[:300],
            node_type="pattern",
            source="autoresearch",
            source_type="learned",
            scope=["marketing", "champ"],
            metadata={"evidence_count": evidence_count, "initial_confidence": confidence},
        )
        return pattern_id

    def link_pattern_to_performance(self, pattern_id: str, perf_id: str) -> bool:
        """Link a pattern to the performance score that proved it."""
        return self.add_edge(
            source=perf_id,
            target=pattern_id,
            relation="proved_pattern",
            confidence="INFERRED",
            weight=0.7,
        )

    def link_content_to_framework(self, piece_id: str, framework_node_id: str) -> bool:
        """Cross-graph reference to ContentGraph knowledge nodes."""
        return self.cross_ref(
            local_node_id=f"content_{piece_id}",
            remote_graph="content",
            remote_node_id=framework_node_id,
            relation="uses_framework",
        )

    def link_outperformed(self, winner_piece_id: str, loser_piece_id: str, margin: float = 0.5) -> bool:
        """Record that one piece outperformed another."""
        return self.add_edge(
            source=f"content_{winner_piece_id}",
            target=f"content_{loser_piece_id}",
            relation="outperformed",
            confidence="EXTRACTED",
            weight=min(margin, 1.0),
        )

    def link_trend_to_content(self, trend_id: str, piece_id: str) -> bool:
        """Trend inspired this content piece."""
        return self.add_edge(
            source=trend_id,
            target=f"content_{piece_id}",
            relation="derived_from",
            confidence="EXTRACTED",
            weight=1.0,
        )

    # ============================================
    # PARSE — Override BaseGraph parse for bulk import
    # ============================================

    def parse(self, source: Any) -> dict:
        """
        Bulk parse for initial load or import.
        Expects a dict with keys: influencers, content_pieces, eval_scores,
        publish_results, performance_scores, leads, trends, patterns

        Each role (Strategist/Creator/QA/Publisher/Analyst) calls write_* methods directly
        for real-time writes. This parse() is for bulk/batch import only.
        """
        if not isinstance(source, dict):
            return {"nodes": [], "edges": []}

        nodes_before = self.G.number_of_nodes()
        edges_before = self.G.number_of_edges()

        # Influencers first (referenced by content)
        for inf in source.get("influencers", []):
            self.write_influencer(
                influencer_id=inf.get("id", ""),
                name=inf.get("name", ""),
                niche=inf.get("niche", ""),
                brand_voice=inf.get("brand_voice", {}),
            )

        # Content pieces
        for cp in source.get("content_pieces", []):
            self.write_content_piece(
                piece_id=cp.get("id", ""),
                topic=cp.get("topic", ""),
                influencer_id=cp.get("influencer_id", ""),
                platform=cp.get("platform", ""),
                funnel_stage=cp.get("funnel_stage", "cold"),
                kpi_stage=cp.get("kpi_stage", "know"),
                content_tier=cp.get("content_tier", "text"),
                cta_keyword=cp.get("cta_keyword", ""),
            )
            # Hook
            if cp.get("hook"):
                hid = self.write_hook(cp["hook"], cp.get("hook_pattern", ""))
                self.link_hook_to_content(cp["id"], hid)

        # Eval scores
        for ev in source.get("eval_scores", []):
            self.write_eval_score(
                piece_id=ev.get("piece_id", ""),
                score=ev.get("score", 0),
                verdict=ev.get("verdict", ""),
                passed=ev.get("passed", False),
                notes=ev.get("notes", ""),
            )

        # Publish results
        for pr in source.get("publish_results", []):
            self.write_publish_result(
                piece_id=pr.get("piece_id", ""),
                platform=pr.get("platform", ""),
                success=pr.get("success", False),
                post_id=pr.get("post_id", ""),
                post_url=pr.get("post_url", ""),
                error=pr.get("error", ""),
            )

        # Performance scores
        for ps in source.get("performance_scores", []):
            self.write_performance_score(
                piece_id=ps.get("piece_id", ""),
                window=ps.get("window", "48hr"),
                overall=ps.get("overall", 0),
                verdict=ps.get("verdict", ""),
                signals=ps.get("signals", {}),
            )

        # Leads
        for lead in source.get("leads", []):
            self.write_waitlist_lead(
                lead_id=lead.get("id", ""),
                email=lead.get("email", ""),
                source_type=lead.get("source_type", "waitlist"),
                tier=lead.get("tier"),
                source_content_id=lead.get("source_content_id", ""),
                source_influencer_id=lead.get("source_influencer_id", ""),
                metadata=lead.get("metadata"),
            )

        nodes_added = self.G.number_of_nodes() - nodes_before
        edges_added = self.G.number_of_edges() - edges_before
        logger.info(f"[MARKETING] Parsed: +{nodes_added} nodes, +{edges_added} edges")

        return {
            "nodes": [{"id": n, **a} for n, a in self.G.nodes(data=True)],
            "edges": [{"source": s, "target": t, **a} for s, t, a in self.G.edges(data=True)],
        }

    # ============================================
    # THE V1 KILLER QUERY
    # ============================================

    def killer_query(
        self,
        tiers: Optional[list[str]] = None,
        source_types: Optional[list[str]] = None,
        top_n: int = 20,
    ) -> list[dict]:
        """
        THE V1 WIN CONDITION QUERY:

        Which face + platform + kpi_stage + hook generated the most
        HOT/BUYER tier assessment leads?

        Returns ranked list showing what to double down on.
        Default: tier in (hot, buyer), source in (assessment), top 20.
        """
        tiers = tiers or ["hot", "buyer"]
        source_types = source_types or ["assessment"]

        results = {}

        # Iterate converted_to_lead edges
        for src, tgt, attrs in self.G.edges(data=True):
            if attrs.get("relation") != "converted_to_lead":
                continue
            if src not in self.G.nodes or tgt not in self.G.nodes:
                continue

            lead_attrs = self.G.nodes[tgt]
            lead_meta = lead_attrs.get("metadata", {})

            # Filter by tier and source_type
            if tiers and lead_meta.get("tier") not in tiers:
                continue
            if source_types and lead_meta.get("source_type") not in source_types:
                continue

            # Get content piece details
            content_attrs = self.G.nodes[src]
            content_meta = content_attrs.get("metadata", {})

            # Find influencer
            influencer_label = ""
            for neighbor in self.G.neighbors(src):
                ndata = self.G.nodes.get(neighbor, {})
                if ndata.get("type") == "influencer":
                    edge_data = self.G.edges.get((src, neighbor), {})
                    if edge_data.get("relation") == "created_by":
                        influencer_label = ndata.get("label", "")
                        break

            # Find platform
            platform_label = ""
            for neighbor in self.G.neighbors(src):
                ndata = self.G.nodes.get(neighbor, {})
                if ndata.get("type") == "platform":
                    platform_label = ndata.get("label", "")
                    break

            # Find hook
            hook_label = ""
            for neighbor in self.G.neighbors(src):
                ndata = self.G.nodes.get(neighbor, {})
                if ndata.get("type") == "hook":
                    edge_data = self.G.edges.get((src, neighbor), {})
                    if edge_data.get("relation") == "used_hook":
                        hook_label = ndata.get("label", "")[:80]
                        break

            key = (influencer_label, platform_label, content_meta.get("kpi_stage", ""), hook_label)
            if key not in results:
                results[key] = {
                    "influencer": influencer_label,
                    "platform": platform_label,
                    "kpi_stage": content_meta.get("kpi_stage", ""),
                    "hook": hook_label,
                    "lead_count": 0,
                    "tiers_captured": set(),
                }
            results[key]["lead_count"] += 1
            if lead_meta.get("tier"):
                results[key]["tiers_captured"].add(lead_meta["tier"])

        # Convert sets to lists for JSON serialization, sort
        ranked = []
        for r in results.values():
            r["tiers_captured"] = sorted(list(r["tiers_captured"]))
            ranked.append(r)
        ranked.sort(key=lambda x: x["lead_count"], reverse=True)

        logger.info(f"[MARKETING] Killer query: {len(ranked)} winning combinations found")
        return ranked[:top_n]

    # ============================================
    # DECORATION DETECTOR
    # ============================================

    def find_decoration(self, days_threshold: int = 7) -> list[dict]:
        """
        Anthony's rule: "Anything that doesn't move someone further down
        KLT->Convert is decoration."

        Find content_piece nodes tagged 'know' that captured ZERO leads
        over N days. Flag them. Kill them in next iteration.
        """
        decoration = []
        now = datetime.now(timezone.utc)

        for nid, attrs in self.G.nodes(data=True):
            if attrs.get("type") != "content_piece":
                continue
            meta = attrs.get("metadata", {})
            if meta.get("kpi_stage") != "know":
                continue

            # Check age
            try:
                created = datetime.fromisoformat(attrs.get("created_at", "").replace("Z", "+00:00"))
                age_days = (now - created).days
                if age_days < days_threshold:
                    continue
            except (ValueError, TypeError):
                continue

            # Check if it captured any leads
            captured_leads = 0
            for neighbor in self.G.neighbors(nid):
                edge_data = self.G.edges.get((nid, neighbor), {})
                if edge_data.get("relation") == "converted_to_lead":
                    captured_leads += 1

            if captured_leads == 0:
                decoration.append({
                    "piece_id": nid,
                    "topic": attrs.get("label", ""),
                    "age_days": age_days,
                    "platform": meta.get("platform", ""),
                    "recommendation": "KILL — 0 leads after 7 days, pure decoration",
                })

        logger.info(f"[MARKETING] Decoration found: {len(decoration)} pieces to kill")
        return decoration

    # ============================================
    # ROLE-SPECIFIC DASHBOARDS
    # ============================================

    def strategist_view(self) -> dict:
        """What the Strategist needs to plan tomorrow."""
        return {
            "killer_combos": self.killer_query(top_n=10),
            "decoration_count": len(self.find_decoration()),
            "top_hooks": self.god_nodes(top_n=5),
            "health": self.health(),
        }

    def analyst_view(self) -> dict:
        """What the Analyst needs for weekly intelligence."""
        return {
            "health": self.health(),
            "god_nodes": self.god_nodes(top_n=10),
            "surprising": self.surprising(top_n=5),
            "total_content": sum(1 for _, a in self.G.nodes(data=True) if a.get("type") == "content_piece"),
            "total_leads": sum(1 for _, a in self.G.nodes(data=True) if a.get("type") == "waitlist_lead"),
        }
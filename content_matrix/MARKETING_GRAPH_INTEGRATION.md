# MarketingGraph Integration Guide

For the Marketing Machine session — how to wire your code into the graph.

**Built:** 2026-04-14 by Operator Session
**Graph file:** `content_matrix/marketing_graph.py`
**Inherits from:** `content_matrix/base_graph.py`

---

## Zero Refactor Required

Every piece of code already built in the Marketing Machine writes cleanly to this schema. Just import `MarketingGraph` and call the write methods at the existing lifecycle points.

---

## Quick Start

```python
from content_matrix.marketing_graph import MarketingGraph

# Singleton — one graph per Cocreatiq instance
graph = MarketingGraph()
graph.load()  # Resume from persisted state
```

Put this in your orchestrator startup. Pass the `graph` instance down to each role.

---

## Integration Points By File

### `content_engine/orchestrator.py`

**On startup:**
```python
# Register influencers from influencers/*.yaml
for inf in influencers:
    graph.write_influencer(
        influencer_id=inf["id"],
        name=inf["name"],
        niche=inf.get("niche", ""),
        brand_voice=inf.get("brand_voice", {}),
    )
```

**After Strategist plans content:**
```python
# For each ContentItem in manifest
graph.write_content_piece(
    piece_id=item.id,
    topic=item.topic,
    influencer_id=item.influencer_id,
    platform=item.platform,
    funnel_stage=item.funnel_stage,   # cold/warm/hot/buyer
    kpi_stage=item.kpi_stage,          # know/like/trust/convert — ADD THIS TO ContentItem
    content_tier=item.content_tier,
    cta_keyword=item.cta_keyword,
)
```

**After Creator writes script:**
```python
# Write the hook first (cross-face shareable)
hook_id = graph.write_hook(
    hook_text=item.hook,
    hook_pattern=item.hook_pattern or "",  # e.g., "Did you know X?"
)
graph.link_hook_to_content(item.id, hook_id)

# Write the script
graph.write_script(item.id, item.script)
```

### `operators/qa_operator` (after eval.py runs)

```python
graph.write_eval_score(
    piece_id=item.id,
    score=eval_result.score,
    verdict=eval_result.verdict,
    passed=eval_result.passed,
    notes=eval_result.notes or "",
)
```

### `content_engine/publishers/*` (after BasePublisher.post())

```python
# In the orchestrator after publisher returns
result: PublishResult = await publisher.post(payload)
graph.write_publish_result(
    piece_id=item.id,
    platform=publisher.platform,
    success=result.success,
    post_id=result.post_id or "",
    post_url=result.post_url or "",
    error=result.error or "",
)
```

### `content_engine/scoring.py` (48hr/7day/30day scoring)

```python
# After multi-signal scoring
graph.write_performance_score(
    piece_id=piece_id,
    window="48hr",  # or "7day", "30day"
    overall=score.overall,
    verdict=score.verdict.value,  # viral/hit/solid/weak/miss
    signals={
        "hook": score.hook,
        "retention": score.retention,
        "engagement": score.engagement,
        "conversion": score.conversion,
        "outlier": score.outlier,
    },
)
```

### `capture/waitlist.py` (landing page email capture)

```python
graph.write_waitlist_lead(
    lead_id=lead.id,
    email=lead.email,
    source_type="waitlist",
    source_content_id=lead.utm_content,  # Which post drove them here
    source_influencer_id=lead.utm_source,
    metadata={"utm_campaign": lead.utm_campaign},
)
```

### `capture/assessment.py` (scorecard captures — THE HIGH-VALUE PATH)

```python
graph.write_waitlist_lead(
    lead_id=lead.id,
    email=lead.email,
    source_type="assessment",
    tier=assessment.tier,  # "cold" | "warm" | "hot" | "buyer" — KEY FIELD
    source_content_id=lead.utm_content,
    source_influencer_id=lead.utm_source,
    metadata={
        "assessment_type": assessment.type,  # ai_readiness, scale_readiness, etc.
        "score": assessment.score,
    },
)
```

### `capture/dm_monitor.py` (keyword detection)

```python
graph.write_waitlist_lead(
    lead_id=lead.id,
    email=lead.email or f"dm_{lead.platform_user_id}@unknown.com",  # email may be unknown
    source_type="dm_keyword",
    source_content_id=triggering_post_id,
    metadata={
        "keyword": detected_keyword,  # BUILD / SCALE / BRAND / OPERATOR
        "platform": platform,
    },
)
```

### `content_engine/autoresearch.py` (pattern discovery)

```python
# When autoresearch promotes a pattern
pattern_id = graph.write_pattern(
    pattern_text=pattern.description,
    confidence="INFERRED",  # will promote to EXTRACTED/PROVEN through repeat evidence
    evidence_count=pattern.evidence_count,
)

# Link pattern to the performance scores that proved it
for perf_id in pattern.supporting_scores:
    graph.link_pattern_to_performance(pattern_id, perf_id)
```

### `content_engine/analytics/*.py` (trend detection)

```python
# When trend scout finds something
trend_id = graph.write_trend(
    trend_text=trend.description,
    metadata={"source": trend.source, "growth_rate": trend.growth_rate},
)

# When a content piece is created FROM that trend
graph.link_trend_to_content(trend_id, piece_id)
```

---

## Cross-Graph Linking (Content Graph)

When a piece uses a Business Matrix framework (Hormozi, Gary Vee, etc.):

```python
# In the Creator, when generating based on a framework
graph.link_content_to_framework(
    piece_id=item.id,
    framework_node_id="hormozi_closer",  # node ID in ContentGraph
)
```

This enables the query: "Does Gary Vee's Reverse Pyramid actually perform better on Twitter than LinkedIn?"

---

## The V1 Killer Query

After running for a week, this one query answers everything:

```python
# THE V1 WIN CONDITION
winners = graph.killer_query(
    tiers=["hot", "buyer"],
    source_types=["assessment"],
    top_n=20,
)

for w in winners:
    print(f"{w['influencer']} on {w['platform']} [{w['kpi_stage']}]: {w['lead_count']} leads")
    print(f"  Hook: {w['hook']}")
    print(f"  Tiers: {w['tiers_captured']}")
```

**Translation:** "Which face + platform + kpi_stage + hook generated the most HOT/BUYER tier assessment leads?"

That's what to double down on. Everything else is decoration.

---

## Decoration Detector

```python
decoration = graph.find_decoration(days_threshold=7)
for d in decoration:
    print(f"KILL: {d['topic']} (age {d['age_days']}d, 0 leads)")
```

**Anthony's rule:** "Anything that doesn't move someone further down KLT→Convert is decoration."

Run this weekly. Kill dead content. Make room for what works.

---

## Role Dashboards

```python
# For the Strategist (daily)
sv = graph.strategist_view()
# Returns: killer_combos, decoration_count, top_hooks, health

# For the Analyst (weekly)
av = graph.analyst_view()
# Returns: health, god_nodes, surprising, total_content, total_leads
```

---

## Persistence

The graph auto-saves at `~/.champ/graphs/marketing/graph.json` after calling `persist()`.

**Recommended pattern:**
```python
# At session end or every N writes
graph.persist()

# At session start
graph.load()
```

---

## Schema Reference

**11 Node Types:**
content_piece · influencer · platform · hook · script · eval_score · publish_result · performance_score · pattern · trend · waitlist_lead

**11 Relationships:**
published_on · created_by · used_hook · pre_scored_as · post_scored_as · posted_result · converted_to_lead · uses_framework · proved_pattern · derived_from · outperformed

**content_piece Properties (not nodes):**
- `funnel_stage`: cold | warm | hot | buyer
- `kpi_stage`: know | like | trust | convert
- `content_tier`: text | voice | video | static

**waitlist_lead Source Types:**
- `waitlist` (landing page)
- `assessment` (scorecard — has tier)
- `dm_keyword` (monitor detection)
- `profile_link` (bio link click)

---

## What You Get For Free (from BaseGraph)

Every graph operation is inherited:

- **Threat scanning** on every write (13 patterns)
- **SHA-256 caching** for cheap LLM calls
- **Confidence promotion** (AMBIGUOUS → INFERRED → EXTRACTED → PROVEN)
- **Community clustering** (Louvain)
- **Free keyword query** (`query()`)
- **LLM semantic recall** (`recall()`)
- **Time decay** (with evidence override)
- **Cross-graph references**
- **Health metrics**
- **God nodes + surprising connections**
- **Frozen snapshots** (prefix cache optimization)
- **Atomic persist/load** (no partial writes)

Zero code for any of this. Just inherit BaseGraph.

---

## Smoke Test Passed

28 nodes, 29 edges simulated end-to-end through full department workflow. Killer query returned correct winner. Persist/load confirmed. Ready for production writes.

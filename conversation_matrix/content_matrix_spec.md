# Content Matrix — Operator Knowledge Graph

**Status:** Spec  
**Pattern source:** Graphify (13K stars) adapted for business content  
**Purpose:** Replace flat memory injection with a queryable knowledge graph  
**Result:** 50-70x fewer tokens per operator context load  

---

## Pipeline

```
ingest → parse → connect → cluster → query → inject
```

| Stage | What It Does | LLM? | Cost |
|-------|-------------|------|------|
| **Ingest** | Accept content (transcript, PDF, web, doc, conversation) | No | Free |
| **Parse** | Extract structure — headers, entities, facts, timestamps | No | Free |
| **Connect** | Find relationships between nodes, assign confidence | Yes | Tokens |
| **Cluster** | Auto-group related content (Leiden/Louvain) | No | Free |
| **Query** | Find relevant nodes for THIS conversation turn | No | Free |
| **Inject** | Build minimal context string from query results | No | Free |

4 of 6 stages are FREE. Only "Connect" costs tokens, and it runs ONCE per content piece (cached after).

---

## Node Schema

Every piece of content becomes nodes in the graph:

```json
{
  "id": "hormozi_closer_element3",
  "label": "CLOSER Element 3: Objection Handling",
  "source_type": "knowledge_block",
  "source_file": "0008_os_business_matrix_hormozi_sales.md",
  "source_location": "## Element 3",
  "operator_scope": ["sales", "champ"],
  "content_hash": "sha256:abc123...",
  "extracted_at": "2026-04-13T...",
  "metadata": {
    "framework": "CLOSER",
    "author": "Alex Hormozi",
    "category": "sales"
  }
}
```

### Node Types

| Type | Source | Example |
|------|--------|---------|
| `framework` | Knowledge block .md files | "CLOSER Framework", "Gary Vee Reverse Pyramid" |
| `entity` | mem_entities table | "Anthony", "Cocreatiq", "Supabase" |
| `fact` | mem_profile, conversations | "Anthony prefers direct communication" |
| `lesson` | mem_lessons table | "Check billing before debugging code" |
| `skill` | operator_skills table | "Handle price objection with value stack" |
| `decision` | conversation transcripts | "Chose Grok over GPT for voice" |
| `callback` | conversation transcripts | "Doorman analogy for API abstraction" |
| `session` | sessions table | "Session 47: discussed pricing strategy" |

---

## Edge Schema

Relationships between nodes:

```json
{
  "source": "hormozi_closer_element3",
  "target": "anthony_objection_pattern",
  "relation": "applied_in",
  "confidence": "PROVEN",
  "weight": 0.92,
  "seen_count": 5,
  "last_seen": "2026-04-12T..."
}
```

### Confidence Levels

| Level | Meaning | How It Gets There |
|-------|---------|-------------------|
| `EXTRACTED` | Explicitly stated in source content | Pass 1 parser found it directly |
| `INFERRED` | Reasonable deduction from co-occurrence | Pass 2 LLM connected it |
| `AMBIGUOUS` | Uncertain — needs more evidence | Pass 2 flagged, low confidence |
| `PROVEN` | Confirmed through repeated use | Seen 3+ times, scored above 0.7 |

Edges promote: AMBIGUOUS → INFERRED → EXTRACTED → PROVEN (through use).

### Relation Types

| Relation | Example |
|----------|---------|
| `part_of` | Element 3 → CLOSER Framework |
| `applied_in` | CLOSER → Session 47 |
| `contradicts` | Hormozi retention vs Lamar retention approach |
| `supports` | Gian ad optimization → Priestley lead gen |
| `evolved_from` | "Direct objection handling" → "Value stack objection handling" |
| `related_to` | Generic semantic similarity |
| `prerequisite` | Lead gen → Sales (you need leads before you close) |
| `taught_by` | CLOSER Framework → Hormozi |

---

## Pass 1: Deterministic Parser (FREE)

No LLM. Regex + structure parsing. Runs on every content piece.

### What It Extracts Per Content Type

| Content Type | Parser | Nodes Extracted | Edges Extracted |
|-------------|--------|----------------|----------------|
| **Knowledge block .md** | Markdown headers + bullet points | Framework names, elements, rules | `part_of` (element → framework) |
| **Conversation transcript** | Timestamp + speaker regex | Decisions, entities mentioned, callbacks | `discussed_in` (entity → session) |
| **mem_entities** | Direct table read | People, projects, operators | `related_to` (entity → entity) |
| **mem_lessons** | Direct table read | Lesson text as nodes | `learned_from` (lesson → operator) |
| **operator_skills** | Direct table read | Skill steps as nodes | `created_by` (skill → operator) |
| **PDF content** | Header + paragraph extraction | Concepts, definitions | `defined_in` (concept → document) |
| **Web content** | HTML structure | Topics, claims, data points | `sourced_from` (claim → URL) |

### Implementation

```python
def parse_knowledge_block(filepath: str) -> dict:
    """Extract nodes + edges from a Business Matrix .md file."""
    nodes, edges = [], []
    content = open(filepath).read()
    
    # Extract framework name from # header
    framework_id = make_id(filepath)
    nodes.append({"id": framework_id, "label": first_header, "source_type": "framework"})
    
    # Extract elements from ## headers
    for header in h2_headers:
        element_id = make_id(framework_id, header)
        nodes.append({"id": element_id, "label": header, "source_type": "element"})
        edges.append({"source": element_id, "target": framework_id, 
                      "relation": "part_of", "confidence": "EXTRACTED"})
    
    # Extract rules from bullet points
    for bullet in bullets:
        rule_id = make_id(element_id, bullet[:50])
        nodes.append({"id": rule_id, "label": bullet, "source_type": "rule"})
        edges.append({"source": rule_id, "target": element_id,
                      "relation": "part_of", "confidence": "EXTRACTED"})
    
    return {"nodes": nodes, "edges": edges}
```

---

## Pass 2: Semantic Extractor (COSTS TOKENS)

LLM finds relationships that the parser can't. Runs ONCE per content piece, cached forever.

### What It Finds

| Relationship | Example | Why Parser Can't Find It |
|-------------|---------|-------------------------|
| Cross-framework connections | "Hormozi retention connects to Platten onboarding" | Different files, no explicit link |
| Contradiction detection | "Hormozi says X, Lamar says opposite" | Requires understanding meaning |
| Application patterns | "Anthony used CLOSER Element 3 in Session 47" | Requires matching framework to transcript |
| Evolution tracking | "Objection handling approach changed from direct to value-stack" | Requires temporal reasoning |

### Implementation

```python
def connect_semantic(nodes: list, existing_graph: nx.Graph) -> list:
    """LLM finds cross-content relationships. Runs once, cached."""
    
    # Build context from existing nodes (summarized, not full content)
    node_summaries = [f"{n['id']}: {n['label']}" for n in nodes[:50]]
    
    prompt = f"""Given these knowledge nodes:
    {node_summaries}
    
    Find relationships between them. For each relationship return:
    - source node id
    - target node id  
    - relation type (supports, contradicts, applied_in, evolved_from, prerequisite)
    - confidence (INFERRED or AMBIGUOUS)
    - reasoning (one sentence)
    
    Only return relationships you're confident about. Max 20."""
    
    # Use cheap model (gpt-4o-mini or gemini-flash)
    edges = call_llm(prompt)
    return edges
```

---

## SHA-256 Caching

Same pattern as Graphify. Hash content → skip if unchanged.

```python
def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()

def is_cached(content: str, cache_dir: Path) -> bool:
    h = content_hash(content)
    return (cache_dir / f"{h}.json").exists()

def save_cache(content: str, extraction: dict, cache_dir: Path):
    h = content_hash(content)
    tmp = cache_dir / f"{h}.tmp"
    target = cache_dir / f"{h}.json"
    tmp.write_text(json.dumps(extraction))
    os.replace(tmp, target)  # atomic
```

Re-runs only process NEW content. Graph persists across sessions.

---

## Clustering

Auto-group related nodes using Louvain community detection (built into NetworkX, no extra dependency).

Clusters emerge naturally:
- **Sales cluster:** CLOSER, objections, pricing, conversion
- **Content cluster:** Gary Vee model, Lamar brand, repurposing
- **Operations cluster:** Hormozi scaling, business diagnostics
- **Retention cluster:** Churn, engagement, onboarding

Operators query their relevant clusters. Sales operator loads the sales cluster. Marketing loads the content cluster. Champ loads all clusters.

---

## Query → Inject (the token savings)

### Old Way (current — flat injection)
```
Load ALL memory (entities, profile, lessons, knowledge blocks)
→ 15,000+ tokens in system prompt
→ Same context every turn regardless of relevance
```

### New Way (Content Matrix)
```
User says: "How should I handle this price objection?"
→ Query graph for: "price objection" + "handling" + "sales"
→ Returns: 5 most relevant nodes with relationships
→ Inject: ~800 tokens of focused, connected context
→ 18x fewer tokens, MORE relevant
```

### Query Implementation

```python
def query_graph(graph: nx.Graph, user_message: str, operator_name: str, top_n: int = 10) -> str:
    """Query the content graph for relevant context."""
    
    # 1. Keyword extraction from user message (free, regex)
    keywords = extract_keywords(user_message)
    
    # 2. Find matching nodes (label search + source_type filter)
    matches = []
    for node_id, attrs in graph.nodes(data=True):
        score = keyword_overlap(keywords, attrs.get("label", ""))
        if operator_name in attrs.get("operator_scope", ["champ"]):
            matches.append((node_id, score))
    
    # 3. Get top N matches + their immediate neighbors (1-hop)
    top_nodes = sorted(matches, key=lambda x: x[1], reverse=True)[:top_n]
    context_nodes = set()
    for node_id, _ in top_nodes:
        context_nodes.add(node_id)
        for neighbor in graph.neighbors(node_id):
            context_nodes.add(neighbor)
    
    # 4. Build injection string
    lines = []
    for node_id in context_nodes:
        attrs = graph.nodes[node_id]
        label = attrs.get("label", node_id)
        lines.append(f"- {label}")
        # Add relationship context
        for neighbor in graph.neighbors(node_id):
            if neighbor in context_nodes:
                edge = graph.edges[node_id, neighbor]
                rel = edge.get("relation", "related_to")
                conf = edge.get("confidence", "INFERRED")
                lines.append(f"  → {rel} [{conf}]: {graph.nodes[neighbor].get('label', neighbor)}")
    
    return "\n".join(lines)
```

---

## File Structure

```
champ_v3/content_matrix/
├── content_matrix_spec.md     ← this file
├── parser.py                  ← Pass 1: deterministic extraction
├── connector.py               ← Pass 2: LLM semantic relationships  
├── graph_store.py             ← Build, cache, persist, query
├── injector.py                ← Query results → operator context string
└── tests/
    └── test_content_matrix.py
```

---

## Integration Point

In `test_agent_voice.py`, replace:

```python
# OLD: flat injection
knowledge_context = load_knowledge_blocks(OPERATOR_NAME)
ChampAgent._memory_context += knowledge_context
```

With:

```python
# NEW: graph query (on each user message, via hook)
from content_matrix.graph_store import query_graph
relevant_context = query_graph(graph, user_message, OPERATOR_NAME)
# Inject into next LLM call
```

The graph builds at startup (one-time cost). Queries are free (in-memory NetworkX). Context is focused and minimal.

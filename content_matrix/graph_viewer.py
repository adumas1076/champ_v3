# ============================================
# Content Matrix — Graph Viewer Generator
# Generates interactive HTML using the same design
# language as the Conversation Matrix graph_viewer.html
# ============================================

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Color scheme per source_type — matches conversation matrix palette
NODE_COLORS = {
    "framework": {"bg": "#7c3aed", "border": "#a78bfa", "hi_bg": "#8b5cf6", "hi_border": "#c4b5fd"},
    "element":   {"bg": "#ec4899", "border": "#f472b6", "hi_bg": "#f472b6", "hi_border": "#fbcfe8"},
    "rule":      {"bg": "#06b6d4", "border": "#22d3ee", "hi_bg": "#22d3ee", "hi_border": "#67e8f9"},
    "entity":    {"bg": "#ef4444", "border": "#f87171", "hi_bg": "#f87171", "hi_border": "#fca5a5"},
    "fact":      {"bg": "#f59e0b", "border": "#fbbf24", "hi_bg": "#fbbf24", "hi_border": "#fde68a"},
    "lesson":    {"bg": "#10b981", "border": "#34d399", "hi_bg": "#34d399", "hi_border": "#6ee7b7"},
    "skill":     {"bg": "#06b6d4", "border": "#22d3ee", "hi_bg": "#22d3ee", "hi_border": "#67e8f9"},
    "decision":  {"bg": "#8b5cf6", "border": "#a78bfa", "hi_bg": "#a78bfa", "hi_border": "#c4b5fd"},
    "callback":  {"bg": "#ec4899", "border": "#f472b6", "hi_bg": "#f472b6", "hi_border": "#fbcfe8"},
    "session":   {"bg": "#475569", "border": "#64748b", "hi_bg": "#64748b", "hi_border": "#94a3b8"},
}

EDGE_COLORS = {
    "PROVEN":    "rgba(16,185,129,0.6)",
    "EXTRACTED": "rgba(59,130,246,0.5)",
    "INFERRED":  "rgba(245,158,11,0.4)",
    "AMBIGUOUS": "rgba(239,68,68,0.3)",
}

EDGE_HIGHLIGHT = {
    "PROVEN":    "#10b981",
    "EXTRACTED": "#3b82f6",
    "INFERRED":  "#f59e0b",
    "AMBIGUOUS": "#ef4444",
}


def generate_viewer(graph_path: Optional[str] = None, output_path: Optional[str] = None) -> str:
    """Generate an interactive HTML viewer for the content matrix graph."""

    gpath = Path(graph_path) if graph_path else Path.home() / ".champ" / "content_matrix" / "graph.json"
    if not gpath.exists():
        raise FileNotFoundError(f"Graph not found: {gpath}")

    data = json.loads(gpath.read_text(encoding="utf-8"))
    raw_nodes = data.get("nodes", [])
    raw_edges = data.get("edges", [])

    # Count clusters
    clusters = set(n.get("cluster", 0) for n in raw_nodes)

    # Build vis.js nodes
    vis_nodes = []
    for n in raw_nodes:
        nid = n.get("id", "")
        label = n.get("label", nid)
        if len(label) > 50:
            label = label[:47] + "..."
        ntype = n.get("source_type", "")
        cluster = n.get("cluster", 0)
        colors = NODE_COLORS.get(ntype, NODE_COLORS["rule"])

        is_major = ntype in ("framework", "entity")
        size = 40 if is_major else (25 if ntype == "element" else 12)

        scope = n.get("operator_scope", [])
        source = n.get("source_file", "")
        desc = n.get("metadata", {}).get("description", "")[:150] if n.get("metadata") else ""

        vis_nodes.append({
            "id": nid,
            "label": label.replace(" — ", "\n").replace(": ", "\n") if is_major else label,
            "color": {
                "background": colors["bg"],
                "border": colors["border"],
                "highlight": {"background": colors["hi_bg"], "border": colors["hi_border"]},
            },
            "font": {"color": "#fff", "size": 14 if is_major else 10, "face": "Segoe UI"},
            "size": size,
            "shape": "dot",
            "shadow": {"enabled": is_major, "color": f"{colors['bg']}66", "size": 15},
            "group": cluster,
            "_type": ntype,
            "_source": source,
            "_scope": ", ".join(scope) if scope else "all",
            "_desc": desc,
        })

    # Build vis.js edges
    vis_edges = []
    for e in raw_edges:
        src = e.get("source", "")
        tgt = e.get("target", "")
        rel = e.get("relation", "related_to")
        conf = e.get("confidence", "INFERRED")
        reason = e.get("reason", "")

        vis_edges.append({
            "from": src,
            "to": tgt,
            "label": rel,
            "color": {"color": EDGE_COLORS.get(conf, "rgba(100,100,100,0.3)"), "highlight": EDGE_HIGHLIGHT.get(conf, "#888")},
            "font": {"size": 9, "color": "#555", "strokeWidth": 0, "face": "Segoe UI"},
            "arrows": {"to": {"scaleFactor": 0.5}},
            "width": 2.5 if conf == "PROVEN" else (1.5 if conf == "EXTRACTED" else 1),
            "dashes": conf == "AMBIGUOUS",
            "_conf": conf,
            "_reason": reason,
        })

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Content Matrix Graph — Cocreatiq OS</title>
    <script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            background: #0a0a0f;
            color: #e0e0e0;
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            overflow: hidden;
        }}
        #graph-container {{ width: 100vw; height: 100vh; position: relative; }}
        #network {{ width: 100%; height: 100%; }}

        #info-panel {{
            position: fixed; top: 20px; right: 20px; width: 380px;
            max-height: calc(100vh - 40px); overflow-y: auto;
            background: rgba(15, 15, 25, 0.95);
            border: 1px solid rgba(120, 80, 255, 0.3);
            border-radius: 12px; padding: 24px;
            backdrop-filter: blur(20px); display: none; z-index: 10;
        }}
        #info-panel.visible {{ display: block; }}
        #info-panel h2 {{ font-size: 18px; color: #a78bfa; margin-bottom: 4px; }}
        #info-panel .subtitle {{ font-size: 12px; color: #666; margin-bottom: 16px; }}
        #info-panel .section {{ margin-bottom: 16px; }}
        #info-panel .section h3 {{
            font-size: 13px; color: #7c3aed; text-transform: uppercase;
            letter-spacing: 1px; margin-bottom: 8px;
        }}
        #info-panel .section p {{ font-size: 13px; line-height: 1.5; color: #bbb; }}
        #info-panel .edge-list {{ list-style: none; padding: 0; }}
        #info-panel .edge-list li {{
            font-size: 12px; padding: 4px 0; color: #999;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }}
        #info-panel .edge-list li .rel {{ color: #f59e0b; font-weight: 600; }}
        #info-panel .edge-list li .conf {{ color: #666; font-size: 10px; }}
        #info-panel .close-btn {{
            position: absolute; top: 12px; right: 16px;
            background: none; border: none; color: #666; font-size: 20px; cursor: pointer;
        }}
        #info-panel .close-btn:hover {{ color: #fff; }}
        .tag {{ display: inline-block; font-size: 10px; padding: 2px 8px; border-radius: 4px; margin: 2px; }}
        .tag-framework {{ background: rgba(124,58,237,0.2); color: #a78bfa; }}
        .tag-element {{ background: rgba(236,72,153,0.2); color: #f472b6; }}
        .tag-rule {{ background: rgba(6,182,212,0.2); color: #22d3ee; }}
        .tag-entity {{ background: rgba(239,68,68,0.2); color: #f87171; }}
        .tag-lesson {{ background: rgba(16,185,129,0.2); color: #34d399; }}
        .tag-fact {{ background: rgba(245,158,11,0.2); color: #fbbf24; }}

        #header {{
            position: fixed; top: 20px; left: 20px; z-index: 10;
        }}
        #header h1 {{
            font-size: 22px; font-weight: 700;
            background: linear-gradient(135deg, #a78bfa, #ec4899);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        }}
        #header .tag-line {{ font-size: 11px; color: #666; margin-top: 4px; }}

        #stats {{
            position: fixed; bottom: 20px; left: 20px;
            display: flex; gap: 24px; z-index: 10;
        }}
        .stat {{ text-align: center; }}
        .stat .value {{
            font-size: 28px; font-weight: 700;
            background: linear-gradient(135deg, #a78bfa, #ec4899);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        }}
        .stat .label {{
            font-size: 10px; color: #666; text-transform: uppercase; letter-spacing: 1px;
        }}

        #search {{
            position: fixed; top: 76px; left: 20px; z-index: 10;
        }}
        #search input {{
            background: rgba(15, 15, 25, 0.9); border: 1px solid rgba(120, 80, 255, 0.3);
            color: #e0e0e0; padding: 8px 14px; border-radius: 8px; width: 260px;
            font-size: 13px; outline: none; backdrop-filter: blur(10px);
        }}
        #search input:focus {{ border-color: #a78bfa; }}

        #legend {{
            position: fixed; bottom: 20px; right: 20px;
            background: rgba(15, 15, 25, 0.95); border: 1px solid rgba(120, 80, 255, 0.2);
            border-radius: 12px; padding: 14px 18px; z-index: 10; font-size: 11px;
        }}
        #legend .item {{ display: flex; align-items: center; margin: 3px 0; }}
        #legend .dot {{ width: 10px; height: 10px; border-radius: 50%; margin-right: 8px; }}
        #legend hr {{ border-color: rgba(255,255,255,0.1); margin: 6px 0; }}
    </style>
</head>
<body>
    <div id="header">
        <h1>Content Matrix Graph</h1>
        <div class="tag-line">Cocreatiq OS — Operator Knowledge Graph</div>
    </div>

    <div id="search">
        <input type="text" id="searchInput" placeholder="Search nodes..." oninput="searchNodes(this.value)">
    </div>

    <div id="graph-container"><div id="network"></div></div>

    <div id="info-panel">
        <button class="close-btn" onclick="closePanel()">&times;</button>
        <h2 id="panel-title"></h2>
        <div class="subtitle" id="panel-subtitle"></div>
        <div id="panel-content"></div>
    </div>

    <div id="stats">
        <div class="stat"><div class="value">{len(raw_nodes)}</div><div class="label">Nodes</div></div>
        <div class="stat"><div class="value">{len(raw_edges)}</div><div class="label">Edges</div></div>
        <div class="stat"><div class="value">{len(clusters)}</div><div class="label">Clusters</div></div>
        <div class="stat"><div class="value">22x</div><div class="label">Token Savings</div></div>
        <div class="stat"><div class="value">15</div><div class="label">Sources</div></div>
    </div>

    <div id="legend">
        <div class="item"><div class="dot" style="background:#7c3aed"></div>Framework</div>
        <div class="item"><div class="dot" style="background:#ec4899"></div>Element</div>
        <div class="item"><div class="dot" style="background:#06b6d4"></div>Rule / Skill</div>
        <div class="item"><div class="dot" style="background:#ef4444"></div>Entity</div>
        <div class="item"><div class="dot" style="background:#f59e0b"></div>Fact</div>
        <div class="item"><div class="dot" style="background:#10b981"></div>Lesson</div>
        <div class="item"><div class="dot" style="background:#8b5cf6"></div>Decision</div>
        <hr>
        <div class="item"><div class="dot" style="background:#10b981"></div>Proven</div>
        <div class="item"><div class="dot" style="background:#3b82f6"></div>Extracted</div>
        <div class="item"><div class="dot" style="background:#f59e0b"></div>Inferred</div>
        <div class="item"><div class="dot" style="background:#ef4444"></div>Ambiguous</div>
    </div>

    <script>
    const nodesData = {json.dumps(vis_nodes, indent=2)};
    const edgesData = {json.dumps(vis_edges, indent=2)};

    const nodes = new vis.DataSet(nodesData);
    const edges = new vis.DataSet(edgesData);

    const container = document.getElementById("network");
    const data = {{ nodes, edges }};
    const options = {{
        physics: {{
            forceAtlas2Based: {{
                gravitationalConstant: -60,
                centralGravity: 0.006,
                springLength: 180,
                springConstant: 0.04,
                damping: 0.4,
            }},
            solver: "forceAtlas2Based",
            stabilization: {{ iterations: 200 }},
        }},
        edges: {{
            smooth: {{ type: "curvedCW", roundness: 0.12 }},
            font: {{ size: 9, color: "#555", strokeWidth: 0, face: "Segoe UI" }},
            arrows: {{ to: {{ scaleFactor: 0.5 }} }},
        }},
        interaction: {{
            hover: true,
            tooltipDelay: 200,
            zoomView: true,
            dragView: true,
        }},
    }};

    const network = new vis.Network(container, data, options);

    network.on("click", function(params) {{
        if (params.nodes.length > 0) {{
            const nodeId = params.nodes[0];
            const node = nodesData.find(n => n.id === nodeId);
            if (node) showPanel(node);
        }} else {{
            closePanel();
        }}
    }});

    function showPanel(node) {{
        const panel = document.getElementById("info-panel");
        document.getElementById("panel-title").textContent = node.label.replace(/\\n/g, " ");
        document.getElementById("panel-subtitle").textContent = node._type + " — " + node._source;

        let html = "";

        // Type + scope tags
        html += '<div class="section">';
        html += '<span class="tag tag-' + node._type + '">' + node._type + '</span> ';
        html += '<span class="tag" style="background:rgba(255,255,255,0.05);color:#888;">scope: ' + node._scope + '</span>';
        if (node._desc) html += '<p style="margin-top:8px;">' + node._desc + '</p>';
        html += '</div>';

        // Connections
        const connEdges = edgesData.filter(e => e.from === node.id || e.to === node.id);
        if (connEdges.length > 0) {{
            html += '<div class="section"><h3>Connections (' + connEdges.length + ')</h3><ul class="edge-list">';
            connEdges.forEach(e => {{
                const otherId = e.from === node.id ? e.to : e.from;
                const otherNode = nodesData.find(n => n.id === otherId);
                const otherLabel = otherNode ? otherNode.label.replace(/\\n/g, " ") : otherId;
                const direction = e.from === node.id ? "\\u2192" : "\\u2190";
                html += '<li><span class="rel">' + e.label + '</span> ' + direction + ' ' + otherLabel;
                html += ' <span class="conf">[' + (e._conf || '') + ']</span>';
                if (e._reason) html += '<br><span style="color:#555;font-size:11px;">' + e._reason + '</span>';
                html += '</li>';
            }});
            html += '</ul></div>';
        }}

        document.getElementById("panel-content").innerHTML = html;
        panel.classList.add("visible");
    }}

    function closePanel() {{
        document.getElementById("info-panel").classList.remove("visible");
    }}

    function searchNodes(query) {{
        if (!query) {{
            nodesData.forEach(n => nodes.update({{ id: n.id, hidden: false }}));
            return;
        }}
        const q = query.toLowerCase();
        nodesData.forEach(n => {{
            const match = (n.label || "").toLowerCase().includes(q) || (n.id || "").toLowerCase().includes(q) || (n._type || "").includes(q);
            nodes.update({{ id: n.id, hidden: !match }});
        }});
    }}
    </script>
</body>
</html>"""

    out = Path(output_path) if output_path else Path(__file__).parent / "content_graph.html"
    out.write_text(html, encoding="utf-8")
    logger.info(f"[GRAPH] Content viewer saved: {out}")
    return str(out)


if __name__ == "__main__":
    path = generate_viewer()
    print(f"Content Matrix viewer: {path}")
    print("Open in browser to explore.")
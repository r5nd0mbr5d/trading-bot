# Interactive Execution Flow Viewer (HTML)

**Purpose**: Generate an interactive HTML dashboard showing execution flows, with collapsible sections and clickable navigation to code files.

---

## Option 1: GitHub Markdown Rendering (Easiest)

**No setup required.** GitHub automatically renders Mermaid diagrams in `.md` files.

```bash
# View in web browser
open https://github.com/yourusername/trading-bot/blob/main/EXECUTION_FLOW.md
```

**Includes**:
- ✅ Mermaid sequence diagram (drag to pan, click nodes)
- ✅ Module dependency graph
- ✅ Text-based flow descriptions
- ✅ Code links (clickable)

**Limitation**: Read-only, no code folding beyond markdown headers.

---

## Option 2: Local Mermaid HTML (5 minutes)

Generate a self-contained HTML file with interactive Mermaid diagrams.

### Setup

```bash
npm install -g mermaid-cli
# or
pip install mermaid-cli
```

### Generate HTML

```bash
# Create HTML with embedded Mermaid
mmdc -i EXECUTION_FLOW.md -o execution_flow.html -c mermaid.config.json

# Or use a simpler approach: copy the Mermaid text into an HTML template
```

### HTML Template

Create `execution_flow_viewer.html`:

```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Trading Bot Execution Flow</title>
    <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }
        .nav {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }
        .nav button {
            padding: 8px 16px;
            background: #0066cc;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
        }
        .nav button:hover {
            background: #0052a3;
        }
        .section {
            display: none;
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        .section.active {
            display: block;
        }
        .mermaid {
            display: flex;
            justify-content: center;
            margin: 20px 0;
            background: #fafafa;
            padding: 20px;
            border-radius: 4px;
        }
        h2 {
            color: #0066cc;
            border-bottom: 2px solid #0066cc;
            padding-bottom: 10px;
        }
        code {
            background: #f0f0f0;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
        }
    </style>
</head>
<body>
    <h1>Trading Bot Execution Flow</h1>
    
    <div class="nav">
        <button onclick="showSection('paper')">📊 Paper Trading</button>
        <button onclick="showSection('backtest')">🔄 Backtest</button>
        <button onclick="showSection('research')">🧪 Research</button>
        <button onclick="showSection('graph')">📈 Dependency Graph</button>
        <button onclick="showSection('decision')">🎯 Decision Tree</button>
    </div>

    <!-- Paper Trading -->
    <div id="paper" class="section active">
        <h2>Paper Trading Flow</h2>
        <p>Real-time bar processing with risk gating and order submission.</p>
        <div class="mermaid">
{{ PAPER_SEQUENCE_DIAGRAM }}
        </div>
    </div>

    <!-- Backtest -->
    <div id="backtest" class="section">
        <h2>Backtest Flow</h2>
        <p>Synchronous historical replay with deterministic fills.</p>
        <pre><code>
Start → cmd_backtest()
  ↓
BacktestEngine.run()
  ├─ Load historical bars (yfinance, Polygon)
  ├─ For each bar (chronologically):
  │  ├─ generate_signal() → approve_signal() → submit_order()
  │  ├─ PaperBroker fills at close price
  │  └─ Portfolio.update_position()
  ├─ Aggregate results (Sharpe, DD, win rate)
  └─ Export report (JSON, CSV, charts)
        </code></pre>
    </div>

    <!-- Research -->
    <div id="research" class="section">
        <h2>Research Flow</h2>
        <p>Feature engineering, model training, and promotion gates.</p>
        <pre><code>
Start → research_train_xgboost()
  ↓
XGBoostPipeline.run()
  ├─ Load bars → [MarketDataStore] SQLite cache
  ├─ compute_features() → MA, RSI, Bollinger, MACD
  ├─ compute_labels() → forward returns (binary/ternary)
  ├─ WalkForwardSplits → train/val/test
  ├─ XGBoostModel.train() → hyperparameter tuning
  ├─ Evaluate → R2, Sharpe, max_dd
  ├─ R2 gate (R2 ≥ 0.15?) → promotion_check.json
  └─ research_register_candidate() → store artifacts
        </code></pre>
    </div>

    <!-- Dependency Graph -->
    <div id="graph" class="section">
        <h2>Module Dependency Graph</h2>
        <p>Color-coded by layer: blue=entry, green=data, yellow=strategy, red=risk, purple=execution.</p>
        <div class="mermaid">
{{ DEPENDENCY_GRAPH }}
        </div>
    </div>

    <!-- Decision Tree -->
    <div id="decision" class="section">
        <h2>Per-Bar Decision Tree</h2>
        <p>All checks performed for each incoming bar.</p>
        <pre><code>
Bar received
 ├─ Kill-switch active? → SKIP
 ├─ Data stale (>1h)? → BLOCK
 ├─ Min bars available? → SKIP
 ├─ Signal generated? → SKIP
 ├─ VaR gate pass? → BLOCK if no
 ├─ Daily limit ok? → BLOCK if no
 ├─ Symbol cooldown? → BLOCK if yes
 ├─ Session window (8-16 UTC)? → BLOCK if no
 └─ Submit order → Retry 3x → Monitor fill
        </code></pre>
    </div>

    <script>
        function showSection(id) {
            // Hide all
            document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
            // Show selected
            document.getElementById(id).classList.add('active');
            // Scroll to top
            window.scrollTo(0, 0);
        }
        // Initialize Mermaid
        mermaid.initialize({ startOnLoad: true, theme: 'default' });
        mermaid.contentLoaded();
    </script>
</body>
</html>
```

### Usage

```bash
# Open in browser
open execution_flow_viewer.html
# or
python -m http.server 8000
# Visit http://localhost:8000/execution_flow_viewer.html
```

---

## Option 3: Dynamic Visualization with D3.js (Advanced)

For fully interactive node graphs with zoom, panning, and code navigation.

### Setup

```bash
npm init
npm install d3@7 webpack webpack-cli --save-dev
```

### d3_flow_viewer.html

```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Flow Viewer - D3.js</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        #graph { border: 1px solid #ddd; background: #fafafa; }
        .node { cursor: pointer; }
        .node circle { fill: #4a90e2; stroke: #0052a3; stroke-width: 2px; }
        .node text { font-size: 12px; dominant-baseline: middle; text-anchor: middle; }
        .link { stroke: #999; stroke-opacity: 0.6; }
        .tooltip { position: absolute; background: rgba(0,0,0,0.8); color: white; 
                   padding: 8px; border-radius: 4px; font-size: 12px; pointer-events: none; }
    </style>
</head>
<body>
    <h1>Module Flow Diagram (D3.js)</h1>
    <svg id="graph" width="1200" height="800"></svg>
    <div id="tooltip" class="tooltip" style="display:none;"></div>

    <script>
        // Flowchart with zoom, drag, and code links
        const nodes = [
            { id: "main", label: "main.py", file: "main.py", color: "#4a90e2" },
            { id: "feeds", label: "MarketDataFeed", file: "src/data/feeds.py", color: "#50c878" },
            { id: "strategy", label: "Strategy", file: "src/strategies/", color: "#ffd700" },
            { id: "risk", label: "RiskManager", file: "src/risk/manager.py", color: "#ff6b6b" },
            { id: "broker", label: "IBKRBroker", file: "src/execution/broker.py", color: "#9b59b6" },
            { id: "db", label: "trading_paper.db", file: "", color: "#ff9999" },
        ];

        const links = [
            { source: "main", target: "feeds" },
            { source: "main", target: "strategy" },
            { source: "main", target: "risk" },
            { source: "main", target: "broker" },
            { source: "feeds", target: "db" },
            { source: "strategy", target: "risk" },
            { source: "risk", target: "broker" },
            { source: "broker", target: "db" },
        ];

        const svg = d3.select("#svg");
        const width = 1200, height = 800;

        const simulation = d3.forceSimulation(nodes)
            .force("link", d3.forceLink(links).id(d => d.id).distance(100))
            .force("charge", d3.forceManyBody().strength(-300))
            .force("center", d3.forceCenter(width / 2, height / 2));

        const g = svg.append("g");

        // Draw links
        const link = g.selectAll("line").data(links).enter()
            .append("line").attr("class", "link");

        // Draw nodes
        const node = g.selectAll("circle").data(nodes).enter()
            .append("g").attr("class", "node")
            .on("click", d => window.open(d.file, "_blank"));

        node.append("circle").attr("r", 30).attr("fill", d => d.color);
        node.append("text").text(d => d.label).attr("fill", "white").attr("font-weight", "bold");

        simulation.on("tick", () => {
            link.attr("x1", d => d.source.x).attr("y1", d => d.source.y)
               .attr("x2", d => d.target.x).attr("y2", d => d.target.y);
            node.attr("transform", d => `translate(${d.x},${d.y})`);
        });

        // Zoom
        svg.call(d3.zoom().on("zoom", e => {
            g.attr("transform", e.transform);
        }));
    </script>
</body>
</html>
```

---

## Option 4: Python Generation Script (Programmatic)

Auto-generate execution flow docs from code analysis.

```python
#!/usr/bin/env python3
"""Generate execution flow docs from AST analysis."""

import ast
import json
from pathlib import Path

def extract_functions(file_path):
    """Extract functions, classes, and their calls."""
    with open(file_path) as f:
        tree = ast.parse(f.read())
    
    functions = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            calls = [n.func.attr for n in ast.walk(node) if isinstance(n, ast.Call)]
            functions[node.name] = {
                "line": node.lineno,
                "calls": calls,
                "args": [arg.arg for arg in node.args.args]
            }
    return functions

def build_call_graph(root_dir):
    """Map all functions and their calls."""
    graph = {}
    for py_file in Path(root_dir).rglob("*.py"):
        funcs = extract_functions(py_file)
        graph[str(py_file)] = funcs
    return graph

def export_as_mermaid(graph, entry_point):
    """Convert call graph to Mermaid diagram."""
    lines = ["flowchart TD"]
    visited = set()
    
    def visit(func_name, depth=0):
        if depth > 5 or func_name in visited:
            return
        visited.add(func_name)
        # ... mermaid syntax generation
    
    return "\n".join(lines)

if __name__ == "__main__":
    graph = build_call_graph("src/")
    mermaid = export_as_mermaid(graph, "cmd_paper")
    print(mermaid)
```

Run:
```bash
python generate_flow.py > execution_flow_generated.md
```

---

## Recommended Approach for Your Codebase

**Option 1 (GitHub)** ✅ **Recommended**
- ✅ Already works (Mermaid renders on GitHub)
- ✅ Version-controlled with code
- ✅ Auto-updates with PRs
- ✅ No build step needed
- 📄 See: [EXECUTION_FLOW.md](EXECUTION_FLOW.md)

**Option 2 + Option 1** (Best UX)
- Create local HTML viewer for offline use
- Keep Mermaid diagrams in git
- Update HTML when docs change
- Deploy to docs site if desired

**Option 3** (Future)
- Use if you build a web dashboard
- D3.js enables click-through to code

**Option 4** (Nice-to-have)
- Auto-generate docs on CI/CD
- Detect refactoring impacts
- Update backlog automatically

---

## Viewing the Diagrams Right Now

1. **GitHub (easiest)**: 
   - Open [EXECUTION_FLOW.md](EXECUTION_FLOW.md) on GitHub
   - Mermaid diagrams render inline
   - Click to drag, zoom with scroll

2. **Local Markdown**:
   - Open [EXECUTION_FLOW.md](EXECUTION_FLOW.md) in your editor
   - Use VS Code Markdown Preview with Mermaid extension
   - `Ctrl+Shift+V` to preview

3. **VS Code Markdown Preview**:
   ```bash
   code EXECUTION_FLOW.md
   # Then Cmd/Ctrl + Shift + V
   ```

4. **Web (npx, instant)**:
   ```bash
   npx -y mmdc -i EXECUTION_FLOW.md -o flow.html
   open flow.html
   ```

---

## Integration with Code Navigation

**VS Code Extension: Code Outline**
- Install "Code Outline" extension
- Hover over function names in `EXECUTION_FLOW.md`
- Cmd+click to jump to definition

**VS Code Breadcrumb**
- Open any file from execution flow
- Breadcrumb shows call chain
- Navigate hierarchy visually

---

## Keeping Diagrams Updated

1. **Manual update**: Edit EXECUTION_FLOW.md when major flows change
2. **Code comments**: Add `# FLOW: <description>` comments in key functions
3. **Automated CI check**: Pre-commit hook validates Mermaid syntax
4. **Documentation review**: Include in pre-PR checklist

---

**Related Resources**:
- [Mermaid.js Docs](https://mermaid.js.org) — Diagram syntax
- [EXECUTION_FLOW.md](EXECUTION_FLOW.md) — Interactive flows (Mermaid)
- [CLAUDE.md](CLAUDE.md) — Architecture overview
- [.python-style-guide.md](.python-style-guide.md) — Code organization

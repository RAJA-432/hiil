"""Generate the H.I.I.L. architecture diagram as a PNG using Graphviz.

Usage:
    python scripts/generate_architecture_diagram.py
    python scripts/generate_architecture_diagram.py --output docs/assets/hiil_architecture

Requires the `graphviz` Python package and the Graphviz `dot` binary:
    pip install graphviz        # + install Graphviz from https://graphviz.org/download/
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

DEFAULT_OUTPUT = "docs/assets/hiil_architecture"


def generate_architecture_diagram(output_path: str = DEFAULT_OUTPUT) -> str:
    try:
        from graphviz import Digraph
    except ImportError:
        raise RuntimeError(
            "the `graphviz` Python package is not installed. "
            "Install it with `pip install graphviz`."
        ) from None
    dot = Digraph("HIIL_Architecture", format="png")
    dot.attr(rankdir="TB", bgcolor="#0F172A", fontname="Helvetica", fontcolor="#F8FAFC")
    dot.attr("node", shape="box", style="filled,rounded", fontname="Helvetica", fontcolor="#FFFFFF")

    dot.node("UI", "USER INTERFACE\n(React SPA / CLI)", fillcolor="#1E293B", color="#0EA5E9")
    dot.node("GW", "FASTAPI GATEWAY\n(Vajra Gate)", fillcolor="#0F2B48", color="#0EA5E9")

    with dot.subgraph(name="cluster_core") as c:
        c.attr(label="H.I.I.L. Core Runtime", color="#334155", fontcolor="#10B981")
        c.node("Agents", "MULTI-AGENT RUNTIME\n\u2022 Agent Registry\n\u2022 Thread Manager\n\u2022 A2A In-box", fillcolor="#182238")
        c.node("RAG", "KNOWLEDGE BASE (RAG)\n\u2022 PDF/DOCX Ingestion\n\u2022 SQLite Vector Store\n\u2022 Context Retrieval", fillcolor="#064E3B", color="#10B981")
        c.node("Tools", "TOOLING (MCP Native)\n\u2022 veda_engine\n\u2022 stdio servers\n\u2022 Custom Connectors", fillcolor="#182238")

    dot.node("LLM", "LLM CONNECTION\n(Ollama / OpenAI Compatible \u2022 Vision & OCR Fallback)", fillcolor="#1E293B", color="#10B981")

    dot.edge("UI", "GW", color="#0EA5E9")
    dot.edge("GW", "Agents", color="#38BDF8")
    dot.edge("GW", "RAG", color="#10B981")
    dot.edge("GW", "Tools", color="#38BDF8")
    dot.edge("Agents", "LLM", color="#38BDF8")
    dot.edge("RAG", "LLM", color="#10B981")
    dot.edge("Tools", "LLM", color="#38BDF8")

    dot.render(output_path, cleanup=True)
    return f"{output_path}.png"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the H.I.I.L. architecture diagram PNG.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Output path without extension (default: %(default)s)")
    args = parser.parse_args()

    output_dir = Path(args.output).parent
    if output_dir != Path("."):
        output_dir.mkdir(parents=True, exist_ok=True)

    try:
        png = generate_architecture_diagram(args.output)
    except Exception as exc:  # graphviz binary missing or rendering failure
        print(f"error: failed to render diagram: {exc}", file=sys.stderr)
        print("  ensure the `graphviz` package is installed and the Graphviz `dot` binary is on PATH.", file=sys.stderr)
        return 1

    print(f"Generated diagram at {png}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

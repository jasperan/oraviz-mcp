#!/usr/bin/env python
"""Generate the paper figures from the benchmark results JSON.

Usage: uv run python paper/make_figures.py
"""

from __future__ import annotations

import json
from pathlib import Path

from matplotlib.backends.backend_pdf import FigureCanvasPdf
from matplotlib.figure import Figure

HERE = Path(__file__).resolve().parent
RESULTS = HERE.parent / "benchmarks" / "results" / "benchmark-results.json"
FIGURES = HERE / "figures"

ORAVIZ_COLOR = "#C74634"  # Oracle red
SQLCL_COLOR = "#7D8491"  # muted grey blue
ENCODING = "cl100k_base"


def load() -> dict:
    return json.loads(RESULTS.read_text())


def series(report: dict, server: str) -> dict[str, int]:
    entry = next(entry for entry in report["servers"] if entry["server"] == server)
    return {
        step["step"]: step["tokens"][ENCODING]
        for step in entry["steps"]
        if not step["setup"] and step["comparable"]
    }


def bar_panel(ax, labels, ours, official, title) -> None:
    y = range(len(labels))
    height = 0.38
    ax.barh([value + height / 2 for value in y], official, height, label="SQLcl MCP", color=SQLCL_COLOR)
    ax.barh([value - height / 2 for value in y], ours, height, label="OraViz MCP", color=ORAVIZ_COLOR)
    for index, (value, other) in enumerate(zip(ours, official)):
        ax.annotate(
            f"{value:,}",
            (value, index - height / 2),
            xytext=(4, 0),
            textcoords="offset points",
            va="center",
            color=ORAVIZ_COLOR,
            fontsize=8,
        )
        ax.annotate(
            f"{other:,}",
            (other, index + height / 2),
            xytext=(4, 0),
            textcoords="offset points",
            va="center",
            color="#4A4A4A",
            fontsize=8,
        )
    ax.set_yticks(list(y))
    ax.set_yticklabels(labels, fontsize=9)
    ax.invert_yaxis()
    ax.set_xlabel("tokens (cl100k_base)", fontsize=9)
    ax.set_title(title, fontsize=11, fontweight="bold", color="#1B1B1B")
    ax.grid(True, axis="x", alpha=0.25, linewidth=0.7)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.legend(fontsize=9, frameon=False)


def figure_steps(report: dict):
    ours = series(report, "oraviz-mcp")
    official = series(report, "sqlcl-mcp")
    labels = list(ours)
    figure = Figure(figsize=(7.2, 3.4), dpi=160)
    FigureCanvasPdf(figure)
    ax = figure.add_subplot()
    bar_panel(
        ax,
        labels,
        [ours[label] for label in labels],
        [official[label] for label in labels],
        "Tokens per question: OraViz vs. SQLcl MCP",
    )
    figure.savefig(FIGURES / "fig_benchmark_steps.pdf", bbox_inches="tight")
    figure.savefig(FIGURES / "fig_benchmark_steps.png", bbox_inches="tight", dpi=200)
    figure.clear()


def figure_totals(report: dict):
    comparison = report["comparison"][ENCODING]
    stages = [
        ("tool schemas", comparison["schema_tokens"]),
        ("tool results", comparison["answer_tokens"]),
        ("total", comparison["grand_total"]),
    ]
    oraviz_totals = next(s for s in report["servers"] if s["server"] == "oraviz-mcp")
    sqlcl_totals = next(s for s in report["servers"] if s["server"] == "sqlcl-mcp")

    figure = Figure(figsize=(7.2, 2.9), dpi=160)
    FigureCanvasPdf(figure)
    ax = figure.add_subplot()
    x = range(len(stages))
    width = 0.38
    ax.bar(
        [value - width / 2 for value in x],
        [row["oraviz-mcp"] for _, row in stages],
        width,
        label="OraViz MCP",
        color=ORAVIZ_COLOR,
    )
    ax.bar(
        [value + width / 2 for value in x],
        [row["sqlcl-mcp"] for _, row in stages],
        width,
        label="SQLcl MCP",
        color=SQLCL_COLOR,
    )
    max_value = max(
        max(row["oraviz-mcp"] for _, row in stages),
        max(row["sqlcl-mcp"] for _, row in stages),
    )
    for index, (_, row) in enumerate(stages):
        ax.annotate(
            f"{row['oraviz-mcp']:,}",
            (index - width / 2, row["oraviz-mcp"]),
            xytext=(0, 3),
            textcoords="offset points",
            ha="center",
            color=ORAVIZ_COLOR,
            fontsize=8,
        )
        ax.annotate(
            f"{row['sqlcl-mcp']:,}",
            (index + width / 2, row["sqlcl-mcp"]),
            xytext=(0, 3),
            textcoords="offset points",
            ha="center",
            color="#4A4A4A",
            fontsize=8,
        )
        ax.annotate(
            f"-{row['savings_pct']:.1f}%",
            (index, max_value * 1.13),
            ha="center",
            va="center",
            fontsize=9,
            fontweight="bold",
            color="#1B1B1B",
        )
    ax.set_ylim(0, max_value * 1.24)
    ax.set_xticks(list(x))
    ax.set_xticklabels([label for label, _ in stages], fontsize=10)
    ax.set_ylabel("tokens (cl100k_base)", fontsize=9)
    ax.set_title("Workflow token budget: schemas + results", fontsize=11, fontweight="bold", color="#1B1B1B")
    ax.grid(True, axis="y", alpha=0.25, linewidth=0.7)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.legend(fontsize=9, frameon=False)
    figure.savefig(FIGURES / "fig_benchmark_totals.pdf", bbox_inches="tight")
    figure.savefig(FIGURES / "fig_benchmark_totals.png", bbox_inches="tight", dpi=200)
    figure.clear()


def main() -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    report = load()
    figure_steps(report)
    figure_totals(report)
    print(f"wrote {FIGURES / 'fig_benchmark_steps.pdf'} and .png")
    print(f"wrote {FIGURES / 'fig_benchmark_totals.pdf'} and .png")


if __name__ == "__main__":
    main()

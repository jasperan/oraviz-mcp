#!/usr/bin/env python
"""Build the results deck (PPTX) for the OraViz MCP server.

Run with an ephemeral dependency, no project install required:

    uv run --with python-pptx python slides/build_deck.py

Output: slides/oraviz-results-deck.pptx
"""

from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Emu, Inches, Pt

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
FIGURES = REPO / "paper" / "figures"
OUTPUT = HERE / "oraviz-results-deck.pptx"

# ---------------------------------------------------------------------------
# Design tokens
# ---------------------------------------------------------------------------

ORACLE_RED = RGBColor(0xC7, 0x46, 0x34)
INK = RGBColor(0x1B, 0x1B, 0x1B)
GREY = RGBColor(0x6B, 0x6B, 0x6B)
LIGHT = RGBColor(0xF4, 0xF1, 0xEE)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)

TITLE_SIZE = Pt(30)
BODY_SIZE = Pt(16)
SMALL_SIZE = Pt(12)
FOOTER_SIZE = Pt(9)


def blank(prs: Presentation):
    return prs.slides.add_slide(prs.slide_layouts[6])


def textbox(slide, left, top, width, height, text, *, size=BODY_SIZE, bold=False, color=INK, align=PP_ALIGN.LEFT):
    box = slide.shapes.add_textbox(left, top, width, height)
    frame = box.text_frame
    frame.word_wrap = True
    paragraph = frame.paragraphs[0]
    paragraph.alignment = align
    run = paragraph.add_run()
    run.text = text
    run.font.size = size
    run.font.bold = bold
    run.font.color.rgb = color
    return box


def bullets(slide, left, top, width, height, items, *, size=BODY_SIZE, spacing=Pt(10)):
    box = slide.shapes.add_textbox(left, top, width, height)
    frame = box.text_frame
    frame.word_wrap = True
    for index, item in enumerate(items):
        paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        paragraph.space_after = spacing
        run = paragraph.add_run()
        run.text = f"\u2022  {item}"
        run.font.size = size
        run.font.color.rgb = INK
    return box


def accent_bar(slide, left, top, width, height=Emu(45720)):
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, height)
    bar.fill.solid()
    bar.fill.fore_color.rgb = ORACLE_RED
    bar.line.fill.background()
    return bar


def chrome(slide, number, title=None):
    """Standard slide furniture: title, accent bar, footer, page number."""
    if title:
        textbox(slide, Inches(0.6), Inches(0.42), Inches(12.1), Inches(0.8), title, size=TITLE_SIZE, bold=True)
        accent_bar(slide, Inches(0.62), Inches(1.18), Inches(1.6))
    textbox(
        slide,
        Inches(0.6),
        Inches(7.08),
        Inches(8.0),
        Inches(0.3),
        "OraViz MCP \u00b7 github.com/jasperan/oraviz-mcp",
        size=FOOTER_SIZE,
        color=GREY,
    )
    textbox(
        slide,
        Inches(12.35),
        Inches(7.08),
        Inches(0.6),
        Inches(0.3),
        str(number),
        size=FOOTER_SIZE,
        color=GREY,
        align=PP_ALIGN.RIGHT,
    )


def stat_card(slide, left, top, width, number, label):
    card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, Inches(1.55))
    card.fill.solid()
    card.fill.fore_color.rgb = LIGHT
    card.line.fill.background()
    frame = card.text_frame
    frame.word_wrap = True
    frame.margin_top = Inches(0.12)
    first = frame.paragraphs[0]
    first.alignment = PP_ALIGN.CENTER
    run = first.add_run()
    run.text = number
    run.font.size = Pt(34)
    run.font.bold = True
    run.font.color.rgb = ORACLE_RED
    second = frame.add_paragraph()
    second.alignment = PP_ALIGN.CENTER
    run = second.add_run()
    run.text = label
    run.font.size = Pt(12)
    run.font.color.rgb = GREY


# ---------------------------------------------------------------------------
# Slides
# ---------------------------------------------------------------------------


def slide_title(prs):
    slide = blank(prs)
    accent_bar(slide, Inches(0.9), Inches(1.55), Inches(2.2), Emu(63500))
    textbox(slide, Inches(0.86), Inches(1.8), Inches(11.6), Inches(1.6), "Writing Efficient MCP Servers", size=Pt(44), bold=True)
    textbox(
        slide,
        Inches(0.9),
        Inches(3.15),
        Inches(11.4),
        Inches(0.9),
        "OraViz: a minimal, visualization-first MCP server for Oracle AI Database",
        size=Pt(20),
        color=GREY,
    )
    textbox(slide, Inches(0.9), Inches(5.6), Inches(11.4), Inches(0.5), "Nacho Martinez  \u00b7  github.com/jasperan", size=Pt(16), bold=True)
    textbox(slide, Inches(0.9), Inches(6.05), Inches(11.4), Inches(0.5), "September 2026  \u00b7  results deck", size=Pt(12), color=GREY)
    return slide


def slide_problem(prs):
    slide = blank(prs)
    chrome(slide, 2, "Agents pay for tools with context")
    bullets(
        slide,
        Inches(0.65),
        Inches(1.65),
        Inches(7.2),
        Inches(4.6),
        [
            "Tool schemas are read once per session, before any work starts.",
            "Tool results are read on every call and stay in the conversation.",
            "General-purpose servers ship big schemas and return unbounded rows.",
            "Faithful formats (CSV, text tables) grow linearly with the data.",
        ],
        size=Pt(17),
    )
    stat_card(slide, Inches(8.3), Inches(1.8), Inches(4.3), "2,139", "tokens of tool schemas \u2014 official SQLcl MCP")
    stat_card(slide, Inches(8.3), Inches(3.6), Inches(4.3), "844", "tokens of tool schemas \u2014 OraViz (60.5% fewer)")
    textbox(
        slide,
        Inches(8.3),
        Inches(5.5),
        Inches(4.3),
        Inches(1.2),
        "The server author decides what the agent must read. That is a design surface.",
        size=Pt(13),
        color=GREY,
    )
    return slide


def slide_rules(prs):
    slide = blank(prs)
    chrome(slide, 3, "Design rules for efficient MCP servers")
    bullets(
        slide,
        Inches(0.65),
        Inches(1.6),
        Inches(7.1),
        Inches(4.8),
        [
            "One tool, one question \u2014 narrow schemas, unambiguous choice.",
            "Declare budgets and enforce them \u2014 cost set by config, not data.",
            "Report truncation honestly \u2014 row counts and explicit markers.",
            "Summarize by value type \u2014 vectors, binary, long text.",
            "Profile before you plot \u2014 aggregate in SQL, chart the result.",
            "Substitute modality \u2014 a picture can answer at constant text cost.",
            "Time-box execution \u2014 a statement timeout, not a hung call.",
        ],
        size=Pt(16),
    )
    card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(8.15), Inches(1.75), Inches(4.5), Inches(3.5))
    card.fill.solid()
    card.fill.fore_color.rgb = LIGHT
    card.line.fill.background()
    frame = card.text_frame
    frame.word_wrap = True
    frame.margin_left = Inches(0.25)
    frame.margin_top = Inches(0.2)
    lines = [
        ("The context contract", True, Pt(18), INK),
        ("preview cap: 25 rows", False, Pt(15), INK),
        ("hard cap: 500 rows", False, Pt(15), INK),
        ("cell limit: 500 chars", False, Pt(15), INK),
        ("statement timeout: 60 s", False, Pt(15), INK),
        ("result cost bounded, independent of table size", False, Pt(13), GREY),
    ]
    for index, (text, bold, size, color) in enumerate(lines):
        paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        paragraph.space_after = Pt(8)
        run = paragraph.add_run()
        run.text = text
        run.font.size = size
        run.font.bold = bold
        run.font.color.rgb = color
    return slide


def slide_architecture(prs):
    slide = blank(prs)
    chrome(slide, 4, "Architecture: one validated query per call")
    boxes = [
        ("MCP client\n(agent)", Inches(0.7)),
        ("Validation\nguard, identifiers, caps", Inches(3.9)),
        ("python-oracledb\nthin mode, timeout", Inches(7.1)),
        ("Oracle AI Database\n26ai Free", Inches(10.3)),
    ]
    for text, left in boxes:
        box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, Inches(2.4), Inches(2.6), Inches(1.3))
        box.fill.solid()
        box.fill.fore_color.rgb = WHITE
        box.line.color.rgb = ORACLE_RED
        box.line.width = Pt(1.5)
        frame = box.text_frame
        frame.word_wrap = True
        frame.paragraphs[0].alignment = PP_ALIGN.CENTER
        run = frame.paragraphs[0].add_run()
        run.text = text
        run.font.size = Pt(13.5)
        run.font.bold = True
        run.font.color.rgb = INK
    for left in (Inches(3.35), Inches(6.55), Inches(9.75)):
        arrow = slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, left, Inches(2.9), Inches(0.5), Inches(0.3))
        arrow.fill.solid()
        arrow.fill.fore_color.rgb = ORACLE_RED
        arrow.line.fill.background()
    render = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(3.9), Inches(4.6), Inches(5.8), Inches(1.0))
    render.fill.solid()
    render.fill.fore_color.rgb = LIGHT
    render.line.fill.background()
    frame = render.text_frame
    frame.paragraphs[0].alignment = PP_ALIGN.CENTER
    run = frame.paragraphs[0].add_run()
    run.text = "Renderer: compact markdown \u00b7 profile \u00b7 chart PNG (+ preview)"
    run.font.size = Pt(14)
    run.font.color.rgb = INK
    up = slide.shapes.add_shape(MSO_SHAPE.UP_ARROW, Inches(0.95), Inches(4.6), Inches(0.5), Inches(1.0))
    up.fill.solid()
    up.fill.fore_color.rgb = ORACLE_RED
    up.line.fill.background()
    textbox(
        slide,
        Inches(1.7),
        Inches(5.85),
        Inches(11.4),
        Inches(0.8),
        "Every result re-enters the conversation under the contract: bounded rows, bounded cells, honest truncation markers, or one image.",
        size=Pt(13),
        color=GREY,
        align=PP_ALIGN.CENTER,
    )
    return slide


def slide_setup(prs):
    slide = blank(prs)
    chrome(slide, 5, "Benchmark: identical questions, same database")
    bullets(
        slide,
        Inches(0.65),
        Inches(1.6),
        Inches(6.1),
        Inches(4.9),
        [
            "OraViz (7 tools) vs. official SQLcl 26.1 MCP server (sql -mcp).",
            "Same Oracle AI Database 26ai Free container and demo data (96 rows).",
            "Five questions: list objects, describe, aggregate, sample 10, full dump.",
            "Counted per question: tool schemas + tool results, tiktoken cl100k.",
            "Chart images excluded from text accounting, reported separately.",
        ],
        size=Pt(15),
    )
    card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(7.2), Inches(1.75), Inches(5.45), Inches(4.4))
    card.fill.solid()
    card.fill.fore_color.rgb = LIGHT
    card.line.fill.background()
    frame = card.text_frame
    frame.word_wrap = True
    frame.margin_left = Inches(0.3)
    frame.margin_top = Inches(0.25)
    lines = [
        ("Reproducible", True, Pt(18), INK),
        ("benchmarks/run_benchmarks.py", False, Pt(13), INK),
        ("benchmarks/results/*.json", False, Pt(13), INK),
        ("paper/paper.pdf", False, Pt(13), INK),
        ("", False, Pt(10), INK),
        ("Deterministic: static database, text-only accounting", False, Pt(12), GREY),
    ]
    for index, (text, bold, size, color) in enumerate(lines):
        paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        paragraph.space_after = Pt(8)
        run = paragraph.add_run()
        run.text = text
        run.font.size = size
        run.font.bold = bold
        run.font.color.rgb = color
    return slide


def slide_steps(prs):
    slide = blank(prs)
    chrome(slide, 6, "Per-question tokens")
    slide.shapes.add_picture(str(FIGURES / "fig_benchmark_steps.png"), Inches(0.9), Inches(1.45), width=Inches(9.0))
    stat_card(slide, Inches(10.15), Inches(1.75), Inches(2.6), "-80.5%", "schema discovery")
    stat_card(slide, Inches(10.15), Inches(3.45), Inches(2.6), "-61.4%", "wide 96-row dump")
    textbox(
        slide,
        Inches(10.15),
        Inches(5.15),
        Inches(2.6),
        Inches(1.6),
        "Small result sets cost ~55% more framing tokens (markdown vs CSV) - bounded by design.",
        size=Pt(11),
        color=GREY,
    )
    return slide


def slide_totals(prs):
    slide = blank(prs)
    chrome(slide, 7, "Workflow totals")
    stat_card(slide, Inches(0.7), Inches(1.5), Inches(3.8), "-60.5%", "tool schemas (844 vs 2,139)")
    stat_card(slide, Inches(4.75), Inches(1.5), Inches(3.8), "-53.7%", "tool results (2,319 vs 5,004)")
    stat_card(slide, Inches(8.8), Inches(1.5), Inches(3.8), "-53.7%", "total (2,319 vs 5,006)")
    picture = slide.shapes.add_picture(str(FIGURES / "fig_benchmark_totals.png"), Inches(2.0), Inches(3.4), height=Inches(2.8))
    picture.left = int((SLIDE_W - picture.width) / 2)
    textbox(
        slide,
        Inches(0.7),
        Inches(6.65),
        Inches(11.9),
        Inches(0.4),
        "o200k_base agrees within one point (53.6% total savings).",
        size=Pt(12),
        color=GREY,
        align=PP_ALIGN.CENTER,
    )
    return slide


def slide_edges(prs):
    slide = blank(prs)
    chrome(slide, 8, "The honest edges")
    textbox(slide, Inches(0.65), Inches(1.6), Inches(5.9), Inches(0.5), "Where minimalism loses", size=Pt(18), bold=True, color=ORACLE_RED)
    bullets(
        slide,
        Inches(0.65),
        Inches(2.2),
        Inches(5.9),
        Inches(4.0),
        [
            "Small results: markdown framing costs ~55% more than CSV.",
            "But that overhead is bounded by columns and caps, not row count.",
            "Unbounded formats grow with the data; bounded ones do not.",
        ],
        size=Pt(14),
    )
    textbox(slide, Inches(7.05), Inches(1.6), Inches(5.6), Inches(0.5), "And where structure wins", size=Pt(18), bold=True, color=ORACLE_RED)
    bullets(
        slide,
        Inches(7.05),
        Inches(2.2),
        Inches(5.6),
        Inches(4.0),
        [
            "Charts: the aggregate rendered to PNG costs 123 text tokens.",
            "No chart tool exists in the official server (capability add-on).",
            "Truncation markers keep the agent in control of its budget.",
        ],
        size=Pt(14),
    )
    return slide


def slide_process(prs):
    slide = blank(prs)
    chrome(slide, 9, "How the result was produced")
    steps = [
        ("Design\ncontract", "budgets + 7 tools"),
        ("Build\nartifact", "~630 statements"),
        ("Test\nsuite", "146 unit + 9 live"),
        ("Agent\nintegration", "stdio MCP client"),
        ("Benchmark\nvs SQLcl", "tiktoken accounting"),
        ("Paper\n+ site", "results & repro"),
    ]
    left = Inches(0.55)
    width = Inches(1.85)
    for index, (title, detail) in enumerate(steps):
        box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, Inches(2.3), width, Inches(1.6))
        box.fill.solid()
        box.fill.fore_color.rgb = WHITE
        box.line.color.rgb = ORACLE_RED
        frame = box.text_frame
        frame.word_wrap = True
        frame.paragraphs[0].alignment = PP_ALIGN.CENTER
        run = frame.paragraphs[0].add_run()
        run.text = title
        run.font.size = Pt(14)
        run.font.bold = True
        run.font.color.rgb = INK
        paragraph = frame.add_paragraph()
        paragraph.alignment = PP_ALIGN.CENTER
        run = paragraph.add_run()
        run.text = detail
        run.font.size = Pt(10.5)
        run.font.color.rgb = GREY
        if index < len(steps) - 1:
            arrow = slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, left + width + Inches(0.03), Inches(2.98), Inches(0.24), Inches(0.24))
            arrow.fill.solid()
            arrow.fill.fore_color.rgb = ORACLE_RED
            arrow.line.fill.background()
        left = left + width + Inches(0.3)
    textbox(
        slide,
        Inches(0.65),
        Inches(4.6),
        Inches(12.0),
        Inches(1.8),
        "97.9% line coverage, CI-gated at 90%  \u00b7  container image on GHCR  \u00b7  live Oracle integration tests  \u00b7  "
        "review-driven hardening before the benchmark (bounded discovery, statement timeout, health checks, silent secrets).",
        size=Pt(13),
        color=GREY,
    )
    return slide


def slide_takeaways(prs):
    slide = blank(prs)
    chrome(slide, 10, "Takeaways")
    bullets(
        slide,
        Inches(0.65),
        Inches(1.6),
        Inches(11.9),
        Inches(3.4),
        [
            "MCP server design is context engineering: schemas and results are budgets you control.",
            "A bounded contract turns result cost into configuration, not data size.",
            "Minimal surfaces + visualization answer questions at a fraction of the text.",
            "Measure honestly: report the stages where the lightweight server loses, and why they stay bounded.",
        ],
        size=Pt(17),
    )
    box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.65), Inches(5.0), Inches(11.9), Inches(1.5))
    box.fill.solid()
    box.fill.fore_color.rgb = LIGHT
    box.line.fill.background()
    frame = box.text_frame
    frame.word_wrap = True
    frame.margin_left = Inches(0.3)
    frame.margin_top = Inches(0.15)
    lines = [
        ("Server:  github.com/jasperan/oraviz-mcp", True, Pt(15), INK),
        ("Benchmark:  benchmarks/  \u00b7  Paper:  paper/paper.pdf  \u00b7  Site:  jasperan.github.io/oraviz-mcp", False, Pt(14), GREY),
    ]
    for index, (text, bold, size, color) in enumerate(lines):
        paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        run = paragraph.add_run()
        run.text = text
        run.font.size = size
        run.font.bold = bold
        run.font.color.rgb = color
    return slide


def main() -> None:
    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H

    slide_title(prs)
    slide_problem(prs)
    slide_rules(prs)
    slide_architecture(prs)
    slide_setup(prs)
    slide_steps(prs)
    slide_totals(prs)
    slide_edges(prs)
    slide_process(prs)
    slide_takeaways(prs)

    prs.core_properties.title = "Writing Efficient MCP Servers"
    prs.core_properties.author = "Nacho Martinez"
    prs.core_properties.comments = "Results deck for the OraViz MCP server (github.com/jasperan/oraviz-mcp)"

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    prs.save(OUTPUT)
    print(f"wrote {OUTPUT} ({len(prs.slides)} slides)")


if __name__ == "__main__":
    main()

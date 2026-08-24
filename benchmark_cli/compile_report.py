"""Merge Domain Expertise + Data Discovery results into one compiled report.

Deliberately does NOT collapse the two suites into a single blended score --
a qualitative LLM-judge percentage and a programmatic archive-query
pass/fail aren't the same kind of measurement, and averaging them would
imply a false equivalence. The report shows both suites side by side, each
with its own subtotal.
"""

from __future__ import annotations

import csv
import html
import statistics
from datetime import datetime, timezone
from pathlib import Path

from benchmark_cli import data_discovery, domain_expertise


def compile_rows(root: Path, domain_expertise_run_id: str | None, data_discovery_run_id: str | None) -> list[dict]:
    return domain_expertise.load_rows(root, domain_expertise_run_id) + data_discovery.load_rows(
        root, data_discovery_run_id
    )


def _mean(rows: list[dict]) -> float | None:
    scores = [r["score_pct"] for r in rows]
    return round(statistics.fmean(scores), 1) if scores else None


def write_report(
    root: Path,
    rows: list[dict],
    run_id: str | None = None,
    suites: tuple[str, ...] = ("domain-expertise", "data-discovery"),
) -> tuple[Path, Path]:
    run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out_dir = root / "runs" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    csv_path = out_dir / "summary.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["suite", "task_id", "category", "trial", "score_pct", "agent", "model"])
        for row in rows:
            writer.writerow(
                [
                    row["suite"],
                    row["task_id"],
                    row["category"],
                    row.get("trial", ""),
                    row["score_pct"],
                    row.get("agent", ""),
                    row.get("model", ""),
                ]
            )

    md_path = out_dir / "summary.md"
    md_path.write_text(_build_markdown(rows, run_id, suites, data_discovery_section=_data_discovery_table))

    return csv_path, md_path


def write_pdf_source(root: Path, rows: list[dict], run_id: str, suites: tuple[str, ...]) -> Path:
    """A second markdown rendering of the same rows, meant only to be fed through
    dkqa.pdf_report.plain_markdown_to_pdf (never shown to a human directly): the
    data-discovery section renders as per-task labeled blocks instead of
    _data_discovery_table's wide table, since this xhtml2pdf install doesn't
    reliably size/wrap that many columns of long content (see
    dkqa/pdf_report.py's plain_markdown_to_pdf docstring). This is the compact
    compiled-summary view -- same fields as summary.md's table, one task per
    block instead of one row -- with no Prompt/Grading detail; see
    write_task_pdfs() for the per-task detailed report. Written into the same
    run directory as summary.md/summary.csv; the caller is expected to delete it
    once the PDF is rendered."""
    out_dir = root / "runs" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "summary_pdf_source.md"
    path.write_text(_build_markdown(rows, run_id, suites, data_discovery_section=_data_discovery_summary_blocks))
    return path


def write_task_pdfs(root: Path, rows: list[dict], run_id: str) -> list[Path]:
    """One detailed PDF per data-discovery (task, trial) -- task name, metadata,
    Prompt (the task's instruction.md), and a Grading table (per-test
    id/summary/pass-fail) -- mirroring Domain Expertise's own per-task PDF
    reports (domain-expertise/results/<run-id>/pdf/<task_id>__trial<N>.pdf),
    which summary.pdf's compact blocks deliberately don't include. Written to
    runs/<run-id>/pdf/<task_id>__trial<N>.pdf; returns the PDF paths."""
    pdf_dir = root / "runs" / run_id / "pdf"
    pdf_dir.mkdir(parents=True, exist_ok=True)

    pdf_paths = []
    for row in rows:
        stem = f"{row['task_id']}__trial{row.get('trial') or '1'}"
        src_path = pdf_dir / f"{stem}_source.md"
        pdf_path = pdf_dir / f"{stem}.pdf"
        src_path.write_text(_data_discovery_detail_markdown(root, row))
        domain_expertise.render_markdown_pdf(root, src_path, pdf_path)
        src_path.unlink()
        pdf_paths.append(pdf_path)
    return pdf_paths


def _build_markdown(rows: list[dict], run_id: str, suites: tuple[str, ...], data_discovery_section) -> str:
    lines = [f"# Compiled results — {run_id}", ""]
    for suite in suites:
        suite_rows = sorted(
            (r for r in rows if r["suite"] == suite), key=lambda r: (r["task_id"], r.get("trial") or 0)
        )
        lines.append(f"## {suite}")
        lines.append("")
        if not suite_rows:
            lines.append("_No results found for this suite._")
            lines.append("")
            continue
        lines += data_discovery_section(suite_rows) if suite == "data-discovery" else _plain_table(suite_rows)
        mean = _mean(suite_rows)
        lines.append("")
        lines.append(f"**{suite} mean: {mean}%** ({len(suite_rows)} task(s))")
        lines.append("")
    return "\n".join(lines)


def _plain_table(rows: list[dict]) -> list[str]:
    lines = ["| Task | Category | Score |", "|---|---|---|"]
    for row in rows:
        lines.append(f"| {row['task_id']} | {row['category']} | {row['score_pct']}% |")
    return lines


def _instruction_as_markdown(text: str) -> str:
    """A task's instruction.md, prepared so it can go through the normal
    markdown->HTML pass (letting **bold**, `code`, and other inline markdown
    the instructions use render properly) while defusing the two things that
    pass would otherwise get wrong:
      - several tasks' instructions embed a literal JSON output schema with
        placeholders like <float> or an angle-bracket comment -- fed through
        as plain markdown, those parse as unrecognized (and silently dropped)
        HTML tags, corrupting the visible instructions. HTML-escaping first
        neutralizes stray &/</> as plain text without touching any markdown
        syntax (none of which uses those characters), so it renders as
        literal "<float>" instead of vanishing.
      - a leading "#" would turn into a real heading that visually competes
        with the report's own headings. Escaping it with a backslash is
        markdown's own literal-character escape, so it stays "#" as plain
        text instead of becoming an ATX heading.
    Two trailing spaces per line are markdown's own hard-line-break syntax,
    preserving the instructions' original line structure (important for
    embedded JSON-schema-like blocks) without depending on this xhtml2pdf
    install's <pre>/white-space CSS support, which doesn't actually preserve
    embedded newlines (see dkqa/pdf_report.py's plain_markdown_to_pdf
    docstring)."""
    lines = []
    for line in text.splitlines():
        escaped = html.escape(line)
        stripped = escaped.lstrip()
        if stripped.startswith("#"):
            indent = escaped[: len(escaped) - len(stripped)]
            escaped = f"{indent}\\{stripped}"
        lines.append(escaped + "  ")
    return "\n".join(lines)


def _agent_model(row: dict) -> str:
    agent = row.get("agent") or "?"
    model = row.get("model")
    return f"{agent} / {model}" if model else agent


def _status(row: dict) -> str:
    return f"⚠️ {row['error']}" if row.get("error") else "ok"


def _data_discovery_table(rows: list[dict]) -> list[str]:
    """More detail than _plain_table -- agent/model, how long each trial took, and
    whether it errored -- since that's what you actually need to tell a real failure
    (verifier disagreed with the agent) apart from a broken trial (agent/container crashed)
    without opening the raw result.json yourself. Markdown/terminal only -- see
    _data_discovery_blocks for the PDF rendering of the same rows."""
    lines = [
        "| Task | Category | Trial | Score | Agent / Model | Duration | Status |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        duration = f"{row['duration_s']}s" if row.get("duration_s") is not None else "?"
        trial = row.get("trial") or "?"
        lines.append(
            f"| {row['task_id']} | {row['category']} | {trial} | {row['score_pct']}% "
            f"| {_agent_model(row)} | {duration} | {_status(row)} |"
        )
    return lines


def _format_test_id(name: str) -> str:
    """A test function name with underscores swapped for spaces, so the PDF
    renderer -- which wraps table cell text fine at whitespace but not inside a
    long unbroken token (see dkqa/pdf_report.py's plain_markdown_to_pdf
    docstring) -- can actually wrap a long test name instead of overflowing it
    into the next column."""
    return name.replace("_", " ")


def _data_discovery_metadata_lines(row: dict) -> list[str]:
    """The bold-labeled metadata fields shared by both the compiled summary's
    per-task blocks and the detailed per-task report -- same fields as
    _data_discovery_table's columns, just as labeled lines instead of a table
    row (see dkqa/pdf_report.py's plain_markdown_to_pdf docstring for why:
    this renderer wraps prose fine but not a wide table with long cell
    content)."""
    duration = f"{row['duration_s']}s" if row.get("duration_s") is not None else "?"
    return [
        f"**Category:** {row['category']}  ",
        f"**Trial #:** {row.get('trial') or '?'}  ",
        f"**Agent / Model:** {_agent_model(row)}  ",
        f"**Final score:** {row['score_pct']}%  ",
        f"**Duration:** {duration}  ",
        f"**Status:** {_status(row)}",
        "",
    ]


def _data_discovery_summary_blocks(rows: list[dict]) -> list[str]:
    """Same fields as _data_discovery_table, one labeled block per task instead of
    a table row -- for the compiled summary.pdf. No Prompt/Grading detail here;
    see _data_discovery_detail_markdown() for the separate per-task report that
    has it."""
    lines = []
    for row in rows:
        lines.append(f"### {row['task_id']}")
        lines.append("")
        lines += _data_discovery_metadata_lines(row)
    return lines


def _data_discovery_detail_markdown(root: Path, row: dict) -> str:
    """A standalone, single-task report: task name, metadata, a Prompt section
    (the task's instruction.md) and a Grading section (per-test
    id/summary/pass-fail from data_discovery.grading_detail()) -- mirroring
    Domain Expertise's own per-task PDF structure. Used by write_task_pdfs()
    for runs/<run-id>/pdf/<task_id>__trial<N>.pdf, one file per (task, trial)."""
    lines = [f"# {row['task_id']}", ""]
    lines += _data_discovery_metadata_lines(row)

    instruction = data_discovery.instruction(root, row["task_id"])
    if instruction:
        lines.append("## Prompt")
        lines.append("")
        lines.append(_instruction_as_markdown(instruction))
        lines.append("")

    grading = data_discovery.grading_detail(root, row["task_id"], row["trial_dir"]) if row.get("trial_dir") else None
    lines.append("## Grading")
    lines.append("")
    if grading:
        lines.append("| ID | Summary | Satisfied |")
        lines.append("|---|---|---|")
        for test in grading:
            satisfied = "✅" if test["satisfied"] else "❌"
            lines.append(f"| {_format_test_id(test['id'])} | {test['summary']} | {satisfied} |")
    else:
        lines.append(
            "_No per-test detail available for this trial -- either it predates "
            "test.sh writing verifier/report.json, or this task's verifier doesn't produce one._"
        )
    lines.append("")

    return "\n".join(lines)

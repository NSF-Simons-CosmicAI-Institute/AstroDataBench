"""Render a grade markdown report as a human-readable PDF.

Uses `markdown` + `xhtml2pdf` (both pure pip installs, no system libraries like
Homebrew's pango/cairo required) rather than WeasyPrint, which needs those
installed outside of pip.

The report is rendered in three pieces -- header/prompt, the model's own answer,
and the grading section -- rather than as one markdown->HTML pass, so that:
  - headers embedded in the *candidate's own* answer text (it's free-form
    markdown we don't control) can be visually scaled down relative to our own
    report headers, via a `.model-answer` CSS scope.
  - bold labels in our own report text (e.g. "**Category:**") can use a real
    bold font face (Helvetica-Bold, a core PDF font -- Arial Unicode, used for
    its broad glyph coverage, has no bundled bold weight), while bold text
    inside the candidate's answer keeps using the Unicode-safe font so any
    bolded Greek letters/symbols there don't silently drop out.

This depends on markdown_report.render_grade_markdown() always emitting the
literal headings "## Model Answer" and "## Grading" -- if that ever changes,
_split_sections() needs to change with it.
"""

from __future__ import annotations

from pathlib import Path

import markdown as _markdown
from xhtml2pdf import pisa

# A broad-coverage Unicode font so Greek letters, arrows, and other symbols
# common in astronomy text (e.g. "theta ~ lambda/D", "->") render correctly --
# xhtml2pdf's default fonts only cover roughly the Latin-1 range otherwise.
_UNICODE_FONT_CANDIDATES = [
    Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
]
_UNICODE_FONT_PATH = next((p for p in _UNICODE_FONT_CANDIDATES if p.exists()), None)

_FONT_FACE_CSS = (
    f"""
    @font-face {{
        font-family: "ReportUnicode";
        src: url("{_UNICODE_FONT_PATH}");
    }}
    """
    if _UNICODE_FONT_PATH
    else ""
)

_BODY_FONT = "ReportUnicode" if _UNICODE_FONT_PATH else "Helvetica"

_HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
{font_face_css}
@page {{
    size: letter;
    margin: 2cm 1.8cm;
}}
body {{
    font-family: "{body_font}", sans-serif;
    font-size: 10pt;
    line-height: 1.45;
    color: #1a1a1a;
}}

/* Task name (h1) and our own section headers (## Prompt / ## Model Answer /
   ## Grading, all h2) are the same size and the largest headers in the report. */
h1, h2 {{
    font-size: 15pt;
    font-weight: bold;
    margin-top: 16pt;
    margin-bottom: 6pt;
    padding-bottom: 3pt;
    border-bottom: 1px solid #ccc;
}}
h1 {{ margin-top: 0; }}
h3 {{
    font-size: 12pt;
    font-weight: bold;
    margin-top: 12pt;
    margin-bottom: 4pt;
}}

/* Headers embedded in the candidate's own free-form answer are scaled down so
   they don't visually compete with the report's own section headers. */
.model-answer h1, .model-answer h2, .model-answer h3,
.model-answer h4, .model-answer h5, .model-answer h6 {{
    font-size: 10.5pt;
    font-weight: bold;
    margin-top: 8pt;
    margin-bottom: 3pt;
    border-bottom: none;
}}

/* Bold labels in our own report text use a real bold face (Helvetica-Bold is
   a core PDF font with no embedding needed). Bold text inside the candidate's
   answer keeps the Unicode-safe font instead, so bolded Greek letters/symbols
   there don't drop out -- it just won't render visually heavier. */
strong, b {{ font-family: "Helvetica-Bold", sans-serif; font-weight: bold; }}
.model-answer strong, .model-answer b {{ font-family: "{body_font}", sans-serif; }}

/* Explanatory asides ("> ...") describing how each grading step works --
   visually distinct from the data (evidence, scores, tables) around them. */
blockquote {{
    margin: 10pt 0;
    padding: 5pt 10pt;
    border-left: 3px solid #bbb;
    background-color: #f6f6f6;
    color: #444;
    font-size: 9pt;
    font-style: italic;
}}
blockquote p {{ margin: 0; }}

hr {{
    border: none;
    border-top: 1pt solid #dddddd;
    color: #dddddd;
    height: 0;
    background: none;
    margin: 14pt 0;
}}

table {{
    border-collapse: collapse;
    width: 100%;
    margin: 6pt 0 10pt 0;
    table-layout: fixed;
}}
th, td {{
    border: 1px solid #999;
    padding: 4pt 6pt;
    text-align: left;
    vertical-align: top;
    font-size: 9pt;
    word-wrap: break-word;
    overflow-wrap: break-word;
    word-break: break-word;
}}
th {{ background-color: #e8e8e8; font-family: "Helvetica-Bold", sans-serif; }}
tr:nth-child(even) td {{ background-color: #fafafa; }}

/* Checklist table only (Rubric table keeps default even column widths):
   narrower Weight/Satisfied columns, wider Evidence column. */
.checklist-table th:nth-child(1), .checklist-table td:nth-child(1) {{ width: 9%; }}   /* ID */
.checklist-table th:nth-child(2), .checklist-table td:nth-child(2) {{ width: 26%; }}  /* Summary */
.checklist-table th:nth-child(3), .checklist-table td:nth-child(3) {{ width: 7%; }}   /* Weight */
.checklist-table th:nth-child(4), .checklist-table td:nth-child(4) {{ width: 8%; }}   /* Satisfied */
.checklist-table th:nth-child(5), .checklist-table td:nth-child(5) {{ width: 50%; }}  /* Evidence */

code, pre {{
    font-family: "Courier New", monospace;
    font-size: 8.5pt;
    white-space: pre-wrap;
    word-wrap: break-word;
}}
</style>
</head>
<body>
{body}
</body>
</html>
"""

_MODEL_ANSWER_HEADING = "## Model Answer"
_GRADING_HEADING = "## Grading"


def _split_sections(markdown_text: str) -> tuple[str, str, str]:
    """Split into (header+prompt, model-answer body, grading section), anchored
    on our own literal section headings rather than the "---" rules the report
    also contains, since the candidate's own answer may itself contain "---"
    horizontal rules that would otherwise throw off a naive split."""
    lines = markdown_text.split("\n")

    def _index_of(heading: str) -> int:
        for i, line in enumerate(lines):
            if line.strip() == heading:
                return i
        raise ValueError(f"Expected to find a '{heading}' heading in the report markdown")

    model_answer_idx = _index_of(_MODEL_ANSWER_HEADING)
    grading_idx = _index_of(_GRADING_HEADING)

    before = "\n".join(lines[: model_answer_idx + 1])  # includes the "## Model Answer" heading itself
    model_answer_body = "\n".join(lines[model_answer_idx + 1 : grading_idx])
    grading = "\n".join(lines[grading_idx:])
    return before, model_answer_body, grading


def _style_satisfied_markers(markdown_text: str) -> str:
    """Swap the checklist's checkmark/cross emoji for colored Unicode
    check/X glyphs, since the emoji versions aren't reliably present in
    non-emoji PDF fonts."""
    return markdown_text.replace(
        "✅", '<span style="color:#1a7f37;">&#10003;</span>'
    ).replace("❌", '<span style="color:#cf222e;">&#10007;</span>')


def _style_warning_markers(markdown_text: str) -> str:
    """Swap a leading warning emoji (used for a failed/errored data-discovery
    trial) for a plain colored "ERROR:" label -- like the checklist's
    checkmark/cross, the emoji glyph isn't reliably present in non-emoji PDF
    fonts and renders as a tofu box."""
    return markdown_text.replace("⚠️ ", '<span style="color:#cf222e;">ERROR:</span> ')


def _mark_checklist_table(grading_html: str) -> str:
    """Tag the first table in the grading section (always the Checklist table --
    Rubric always follows it) so the column-width CSS can target it specifically."""
    return grading_html.replace("<table>", '<table class="checklist-table">', 1)


def _render_html(body_html: str, output_path: Path) -> None:
    html = _HTML_TEMPLATE.format(font_face_css=_FONT_FACE_CSS, body_font=_BODY_FONT, body=body_html)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        result = pisa.CreatePDF(html, dest=f, encoding="utf-8")

    if result.err:
        raise RuntimeError(f"Failed to render PDF for {output_path} ({result.err} error(s))")


def markdown_to_pdf(markdown_text: str, output_path: Path) -> None:
    before, model_answer_body, grading = _split_sections(markdown_text)
    grading = _style_satisfied_markers(grading)

    md_kwargs = {"extensions": ["tables", "fenced_code"]}
    before_html = _markdown.markdown(before, **md_kwargs)
    model_answer_html = _markdown.markdown(model_answer_body, **md_kwargs)
    grading_html = _mark_checklist_table(_markdown.markdown(grading, **md_kwargs))

    body_html = f'{before_html}<div class="model-answer">{model_answer_html}</div>{grading_html}'
    _render_html(body_html, output_path)


def plain_markdown_to_pdf(markdown_text: str, output_path: Path) -> None:
    """Render a plain markdown document (no candidate-answer/grading split) to PDF
    using the same header/table/font styling as markdown_to_pdf(). Used for the
    compiled run-summary report (benchmark.py report --pdf).

    This xhtml2pdf install wraps table cell text fine at whitespace (confirmed
    against markdown_to_pdf()'s own checklist table with realistic long prose),
    but does NOT wrap a long *unbroken* token -- no spaces at all, e.g. a
    hyphenated task id or a snake_case test name -- inside a narrow cell; it just
    overflows into the next cell instead (tried CSS nth-child/inline/<col>
    widths and <wbr/>/soft-hyphen break hints -- none of them help). Callers
    with that kind of content should either keep it out of tables (see
    benchmark_cli/compile_report.py's per-task blocks for data-discovery) or
    give the renderer real word breaks first, e.g. swap underscores for spaces
    the way compile_report.py's grading table does for test ids."""
    markdown_text = _style_warning_markers(_style_satisfied_markers(markdown_text))
    md_kwargs = {"extensions": ["tables", "fenced_code"]}
    body_html = _markdown.markdown(markdown_text, **md_kwargs)
    _render_html(body_html, output_path)

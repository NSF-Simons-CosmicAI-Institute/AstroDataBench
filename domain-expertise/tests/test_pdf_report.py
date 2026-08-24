import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from dkqa.pdf_report import _mark_checklist_table, _split_sections, _style_satisfied_markers, markdown_to_pdf

SAMPLE_REPORT = """# t1

**Category:** radio
**Trial #:** 1
**Model:** claude-sonnet-5
**Final score:** 0.75  (checklist coverage: 0.70, rubric: 0.85)

## Prompt

What does theta ~ lambda/D mean? (Unicode check: θ ≈ λ/D, →)

---

## Model Answer

# A candidate's own header

Some answer text with **bold** content, including a divider below.

---

More answer text after a "---" the candidate itself wrote.

---

## Grading

**Judge Model:** claude-opus-5

### Checklist

| ID | Summary | Weight | Satisfied | Evidence |
|---|---|---|---|---|
| a | Fact a | 1.0 | ✅ | quote a |
| b | Fact b | 0.5 | ❌ | missing |

### Rubric

| Criterion | Description | Score | Justification |
|---|---|---|---|
| accuracy | Is it correct? | 4/5 | solid |
"""


def test_split_sections_isolates_model_answer_body():
    before, model_answer_body, grading = _split_sections(SAMPLE_REPORT)

    assert "# t1" in before
    assert "## Prompt" in before
    assert "## Model Answer" in before  # heading itself stays with the "before" chunk
    assert "A candidate's own header" not in before

    assert "A candidate's own header" in model_answer_body
    assert 'a "---" the candidate itself wrote' in model_answer_body
    assert "## Grading" not in model_answer_body

    assert "## Grading" in grading
    assert "### Checklist" in grading
    assert "A candidate's own header" not in grading


def test_split_sections_missing_heading_raises():
    with pytest.raises(ValueError):
        _split_sections("# t1\n\nNo model answer or grading heading here.")


def test_style_satisfied_markers_replaces_emoji_with_colored_glyphs():
    styled = _style_satisfied_markers("| a | ✅ |\n| b | ❌ |")

    assert "✅" not in styled
    assert "❌" not in styled
    assert "color:#1a7f37" in styled  # green check
    assert "color:#cf222e" in styled  # red X


def test_mark_checklist_table_tags_only_first_table():
    html = "<table><tr><td>checklist</td></tr></table><table><tr><td>rubric</td></tr></table>"
    marked = _mark_checklist_table(html)

    assert marked.count('class="checklist-table"') == 1
    assert marked.startswith('<table class="checklist-table">')
    assert marked.endswith("<table><tr><td>rubric</td></tr></table>")


def test_markdown_to_pdf_produces_valid_pdf(tmp_path):
    out_path = tmp_path / "report.pdf"

    markdown_to_pdf(SAMPLE_REPORT, out_path)

    assert out_path.exists()
    data = out_path.read_bytes()
    assert data.startswith(b"%PDF")
    assert len(data) > 500  # not a near-empty/broken file


def test_markdown_to_pdf_creates_parent_directories(tmp_path):
    out_path = tmp_path / "nested" / "dir" / "report.pdf"

    markdown_to_pdf(SAMPLE_REPORT, out_path)

    assert out_path.exists()

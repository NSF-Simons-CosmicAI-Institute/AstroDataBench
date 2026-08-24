import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchmark_cli.compile_report import _instruction_as_markdown, write_report


def _rows():
    return [
        {"suite": "domain-expertise", "task_id": "seeing", "category": "optical", "score_pct": 80.0},
        {"suite": "domain-expertise", "task_id": "interferometry", "category": "radio", "score_pct": 60.0},
        {"suite": "data-discovery", "task_id": "alma-HH212-observations", "category": "data-query", "score_pct": 100.0},
    ]


def test_write_report_creates_csv_with_all_rows(tmp_path):
    csv_path, _ = write_report(tmp_path, _rows(), run_id="test-run")

    with open(csv_path) as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 3
    assert {r["task_id"] for r in rows} == {"seeing", "interferometry", "alma-HH212-observations"}
    assert {r["suite"] for r in rows} == {"domain-expertise", "data-discovery"}


def test_write_report_creates_markdown_with_per_suite_sections(tmp_path):
    _, md_path = write_report(tmp_path, _rows(), run_id="test-run")
    md = md_path.read_text()

    assert "## domain-expertise" in md
    assert "## data-discovery" in md
    assert "seeing" in md
    assert "alma-HH212-observations" in md


def test_write_report_shows_per_suite_mean_not_blended_overall(tmp_path):
    _, md_path = write_report(tmp_path, _rows(), run_id="test-run")
    md = md_path.read_text()

    # domain-expertise mean: (80.0 + 60.0) / 2 = 70.0
    assert "domain-expertise mean: 70.0%" in md
    # data-discovery mean: 100.0 (only one row)
    assert "data-discovery mean: 100.0%" in md
    # no single number that pretends to average across both suites' different scoring semantics
    assert "overall" not in md.lower()


def test_write_report_handles_suite_with_no_rows(tmp_path):
    only_domain_expertise = [r for r in _rows() if r["suite"] == "domain-expertise"]
    _, md_path = write_report(tmp_path, only_domain_expertise, run_id="test-run")
    md = md_path.read_text()

    assert "## data-discovery" in md
    assert "No results found for this suite" in md


def test_write_report_uses_timestamp_run_id_when_omitted(tmp_path):
    csv_path, _ = write_report(tmp_path, _rows())

    assert csv_path.parent.parent == tmp_path / "runs"
    assert csv_path.parent.name  # non-empty auto-generated run id


def test_instruction_as_markdown_preserves_markdown_emphasis():
    # unlike an escaped raw-HTML block, this goes through the normal
    # markdown->HTML pass, so **bold**/`code` syntax must survive untouched
    assert "**bold**" in _instruction_as_markdown("Use **bold** text.")
    assert "`code`" in _instruction_as_markdown("Use `code` here.")


def test_instruction_as_markdown_escapes_angle_bracket_placeholders():
    result = _instruction_as_markdown('Schema: {"x": <float>}')
    assert "<float>" not in result  # would parse as an (unrecognized, dropped) HTML tag otherwise
    assert "&lt;float&gt;" in result


def test_instruction_as_markdown_escapes_leading_hash_so_it_stays_plain_text():
    result = _instruction_as_markdown("# Big Heading")
    assert result.startswith("\\#")  # markdown's literal-character escape, not an ATX heading marker
    assert "Big Heading" in result


def test_instruction_as_markdown_hard_breaks_every_line():
    result = _instruction_as_markdown("line one\nline two")
    lines = result.split("\n")
    assert lines[0].endswith("  ")  # two trailing spaces = markdown hard line break
    assert lines[1].endswith("  ")

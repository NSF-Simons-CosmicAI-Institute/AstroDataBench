import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchmark_cli import domain_expertise


def _write_summary(root: Path, run_id: str, tasks: list[dict]) -> None:
    results_dir = root / "domain-expertise" / "results" / run_id
    results_dir.mkdir(parents=True)
    (results_dir / "summary.json").write_text(json.dumps({"run_id": run_id, "tasks": tasks}))


def test_latest_run_id_picks_lexicographically_last(tmp_path):
    _write_summary(tmp_path, "20260101-000000", [])
    _write_summary(tmp_path, "20260301-000000", [])
    _write_summary(tmp_path, "20260201-000000", [])

    assert domain_expertise.latest_run_id(tmp_path) == "20260301-000000"


def test_latest_run_id_none_when_no_results(tmp_path):
    assert domain_expertise.latest_run_id(tmp_path) is None


def test_load_rows_normalizes_to_percentage(tmp_path):
    _write_summary(
        tmp_path,
        "20260101-000000",
        [
            {"task_id": "seeing", "category": "optical", "mean_final_score": 0.834},
            {"task_id": "interferometry", "category": "radio", "mean_final_score": 0.5},
        ],
    )

    rows = domain_expertise.load_rows(tmp_path, "20260101-000000")

    assert rows == [
        {"suite": "domain-expertise", "task_id": "seeing", "category": "optical", "score_pct": 83.4},
        {"suite": "domain-expertise", "task_id": "interferometry", "category": "radio", "score_pct": 50.0},
    ]


def test_load_rows_defaults_to_latest_when_run_id_omitted(tmp_path):
    _write_summary(tmp_path, "20260101-000000", [{"task_id": "old", "category": "x", "mean_final_score": 0.1}])
    _write_summary(tmp_path, "20260201-000000", [{"task_id": "new", "category": "x", "mean_final_score": 0.9}])

    rows = domain_expertise.load_rows(tmp_path, None)

    assert [r["task_id"] for r in rows] == ["new"]


def test_load_rows_empty_when_no_run_exists(tmp_path):
    assert domain_expertise.load_rows(tmp_path, None) == []


def test_load_rows_falls_back_to_uncategorized(tmp_path):
    _write_summary(tmp_path, "20260101-000000", [{"task_id": "t", "mean_final_score": 0.5}])

    rows = domain_expertise.load_rows(tmp_path, "20260101-000000")

    assert rows[0]["category"] == "uncategorized"


def test_render_task_pdfs_returns_a_pdf_path_per_markdown_report(tmp_path):
    markdown_dir = tmp_path / "domain-expertise" / "results" / "20260101-000000" / "markdown"
    markdown_dir.mkdir(parents=True)
    (markdown_dir / "seeing__trial1.md").write_text("# seeing")
    (markdown_dir / "interferometry__trial1.md").write_text("# interferometry")
    dest_dir = tmp_path / "runs" / "myrun" / "pdf"

    with (
        patch.object(domain_expertise, "ensure_venv"),
        patch("benchmark_cli.domain_expertise.subprocess.run") as mock_run,
    ):
        rendered = domain_expertise.render_task_pdfs(tmp_path, "20260101-000000", dest_dir)

    assert sorted(p.name for p in rendered) == ["interferometry__trial1.pdf", "seeing__trial1.pdf"]
    # rendering itself (markdown -> PDF) happens in the subprocess, not here --
    # this just checks the wrapper invoked it with the right run id/out-dir.
    cmd = mock_run.call_args.args[0]
    assert "--run-id" in cmd and "20260101-000000" in cmd
    assert "--out-dir" in cmd and str(dest_dir) in cmd


def test_render_task_pdfs_empty_and_no_subprocess_when_run_has_no_markdown_dir(tmp_path):
    (tmp_path / "domain-expertise" / "results" / "20260101-000000").mkdir(parents=True)

    with (
        patch.object(domain_expertise, "ensure_venv"),
        patch("benchmark_cli.domain_expertise.subprocess.run") as mock_run,
    ):
        result = domain_expertise.render_task_pdfs(tmp_path, "20260101-000000", tmp_path / "runs" / "myrun" / "pdf")

    assert result == []
    mock_run.assert_not_called()

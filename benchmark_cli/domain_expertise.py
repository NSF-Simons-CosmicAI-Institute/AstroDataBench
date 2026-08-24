"""Domain Expertise suite: invoke its native runner, and normalize its results
for the cross-suite compiled report.

This module intentionally has no third-party dependencies (no `anthropic`,
`python-dotenv`, etc.) -- those live in domain-expertise/.venv, which this
module never imports into. It only shells out to that suite's own scripts and
reads the plain JSON they produce.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

SUITE_DIR_NAME = "domain-expertise"


def suite_dir(root: Path) -> Path:
    return root / SUITE_DIR_NAME


def venv_python(root: Path) -> Path:
    return suite_dir(root) / ".venv" / "bin" / "python3"


def ensure_venv(root: Path) -> None:
    """Create domain-expertise/.venv and install its requirements if missing.
    A fresh clone has no venv (it's gitignored) -- set it up automatically on
    first use rather than making the user discover and run separate setup
    steps themselves."""
    venv_dir = suite_dir(root) / ".venv"
    if venv_python(root).exists():
        return

    print("Setting up the domain-expertise environment (first run only)...", file=sys.stderr)
    subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
    subprocess.run(
        [str(venv_python(root)), "-m", "pip", "install", "-q", "-r", "requirements.txt"],
        cwd=suite_dir(root),
        check=True,
    )


def run(root: Path, args: list[str]) -> int:
    """Run the suite via its own run_benchmark.sh, with the venv's python
    resolved first on PATH so the script's internal `python3` calls use it."""
    ensure_venv(root)

    env = dict(os.environ)
    env["PATH"] = f"{venv_python(root).parent}:{env.get('PATH', '')}"

    script = suite_dir(root) / "scripts" / "run_benchmark.sh"
    result = subprocess.run(["bash", str(script), *args], env=env)
    return result.returncode


def render_markdown_pdf(root: Path, md_path: Path, pdf_path: Path) -> None:
    """Render an arbitrary markdown file to PDF via dkqa's report styling
    (markdown + xhtml2pdf, only pip-installed in domain-expertise/.venv) -- lets
    `benchmark.py report --pdf` produce a styled PDF for either suite's compiled
    summary without a second copy of these dependencies just for data-discovery."""
    ensure_venv(root)
    script = suite_dir(root) / "scripts" / "render_markdown_pdf.py"
    subprocess.run([str(venv_python(root)), str(script), str(md_path), str(pdf_path)], check=True)


def render_task_pdfs(root: Path, run_id: str, dest_dir: Path) -> list[Path]:
    """Render this run's per-task PDFs into dest_dir, on demand -- `run`
    (specifically scripts/grade.py) only writes markdown/<task_id>__trial<N>.md;
    PDF rendering happens here instead, only when `benchmark.py report
    --task-pdfs` actually asks for it, straight into the wrapper's own
    runs/<run-id>/pdf/ (alongside data-discovery's per-task PDFs, which are
    rendered the same on-demand way -- see compile_report.write_task_pdfs()).
    Returns [] if this run has no markdown/ directory -- e.g. it hasn't been
    graded yet."""
    markdown_dir = suite_dir(root) / "results" / run_id / "markdown"
    if not markdown_dir.exists():
        return []
    ensure_venv(root)
    script = suite_dir(root) / "scripts" / "render_task_pdfs.py"
    subprocess.run(
        [str(venv_python(root)), str(script), "--run-id", run_id, "--out-dir", str(dest_dir)],
        check=True,
    )
    return sorted(dest_dir / md_path.with_suffix(".pdf").name for md_path in markdown_dir.glob("*.md"))


def new_task(root: Path, args: list[str]) -> int:
    ensure_venv(root)
    script = suite_dir(root) / "scripts" / "new_task.py"
    result = subprocess.run([str(venv_python(root)), str(script), *args], cwd=suite_dir(root))
    return result.returncode


def latest_run_id(root: Path) -> str | None:
    results_dir = suite_dir(root) / "results"
    if not results_dir.exists():
        return None
    candidates = sorted(
        (p.name for p in results_dir.iterdir() if p.is_dir() and (p / "summary.json").exists())
    )
    return candidates[-1] if candidates else None


def load_rows(root: Path, run_id: str | None) -> list[dict]:
    """Normalized rows for the compiled report: one per task, already scored
    0-100. Returns [] if this suite has no matching run rather than raising --
    the compiled report is meant to work even when only one suite has run."""
    resolved_run_id = run_id or latest_run_id(root)
    if resolved_run_id is None:
        return []

    summary_path = suite_dir(root) / "results" / resolved_run_id / "summary.json"
    if not summary_path.exists():
        return []

    summary = json.loads(summary_path.read_text())
    rows = []
    for task in summary.get("tasks", []):
        rows.append(
            {
                "suite": "domain-expertise",
                "task_id": task["task_id"],
                "category": task.get("category") or "uncategorized",
                "score_pct": round(task["mean_final_score"] * 100, 1),
            }
        )
    return rows

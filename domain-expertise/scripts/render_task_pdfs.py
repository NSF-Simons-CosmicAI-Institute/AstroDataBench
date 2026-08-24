#!/usr/bin/env python3
"""CLI: render every markdown/<task_id>__trial<N>.md report for a run to PDF.

PDF rendering isn't part of `grade.py`'s output anymore -- markdown reports are
cheap and always written, but PDFs cost real render time and most runs don't
need them, so they're produced on demand here instead, by
`benchmark.py report --task-pdfs` (see benchmark_cli/domain_expertise.py's
render_task_pdfs()). --out-dir is a separate argument (rather than always
results/<run-id>/pdf/) so the wrapper can render straight into its own
runs/<run-id>/pdf/, alongside data-discovery's per-task PDFs.

Usage:
    python scripts/render_task_pdfs.py --run-id 20260810-153000 --out-dir /path/to/pdf
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dkqa.config import load_config
from dkqa.pdf_report import markdown_to_pdf


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    config = load_config()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--out-dir", required=True, help="Directory to write <task_id>__trial<N>.pdf files into")
    parser.add_argument("--results-dir", default=config["results_dir"])
    args = parser.parse_args()

    markdown_dir = root / args.results_dir / args.run_id / "markdown"
    if not markdown_dir.exists():
        print(f"No markdown reports found in {markdown_dir}; run scripts/grade.py first.", file=sys.stderr)
        return 1

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    for md_path in sorted(markdown_dir.glob("*.md")):
        pdf_path = out_dir / md_path.with_suffix(".pdf").name
        markdown_to_pdf(md_path.read_text(), pdf_path)
        print(f"Wrote {pdf_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

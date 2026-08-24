#!/usr/bin/env python3
"""CLI: render an arbitrary markdown file to PDF using dkqa's report styling.

Used by the repo-root wrapper (benchmark.py report --pdf) to turn the compiled
cross-suite summary.md into summary.pdf, reusing the same look as the per-task
Domain Expertise PDFs without a second copy of markdown/xhtml2pdf just for
Data Discovery.

Usage:
    python scripts/render_markdown_pdf.py <input.md> <output.pdf>
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dkqa.pdf_report import plain_markdown_to_pdf


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: render_markdown_pdf.py <input.md> <output.pdf>", file=sys.stderr)
        return 1

    md_path, pdf_path = Path(sys.argv[1]), Path(sys.argv[2])
    plain_markdown_to_pdf(md_path.read_text(), pdf_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

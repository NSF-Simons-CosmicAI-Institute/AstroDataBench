#!/usr/bin/env python3
"""CLI: build summary.json + summary.csv for a run from its grades/*.json.

Usage:
    python scripts/report.py --run-id 20260810-153000
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dkqa.config import load_config
from dkqa.report import write_summary


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    config = load_config()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--results-dir", default=config["results_dir"])
    args = parser.parse_args()

    run_dir = root / args.results_dir / args.run_id
    if not (run_dir / "grades").exists():
        print(f"No grades found in {run_dir}; run scripts/grade.py first.", file=sys.stderr)
        sys.exit(1)

    json_path, csv_path = write_summary(run_dir)
    print(f"Wrote {json_path}")
    print(f"Wrote {csv_path}")


if __name__ == "__main__":
    main()

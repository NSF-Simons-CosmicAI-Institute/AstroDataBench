#!/usr/bin/env python3
"""CLI: run the candidate model over the task bank and record its raw answers.

Usage:
    python scripts/run.py --run-id 20260810-153000 [--model claude-sonnet-5]
                           [--filter category=optical] [--trials 1]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

from dkqa.config import load_config
from dkqa.models.anthropic_client import AnthropicClient
from dkqa.runner import run_tasks
from dkqa.task_loader import filter_tasks, load_tasks


def main() -> None:
    load_dotenv()
    root = Path(__file__).resolve().parent.parent
    config = load_config()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True, help="Identifier for this run; results go to results/<run-id>/")
    parser.add_argument("--model", default=config["candidate_model"], help="Candidate model id to evaluate")
    parser.add_argument("--filter", default=None, help="Optional key=value filter, e.g. category=optical or id=optical-seeing")
    parser.add_argument("--trials", type=int, default=1, help="Number of independent trials per task")
    parser.add_argument("--tasks-dir", default=config["tasks_dir"], help="Directory containing task YAML files")
    parser.add_argument("--results-dir", default=config["results_dir"], help="Directory to write run results under")
    args = parser.parse_args()

    tasks = load_tasks(root / args.tasks_dir)
    tasks = filter_tasks(tasks, args.filter)
    if not tasks:
        print("No tasks matched; nothing to run.", file=sys.stderr)
        sys.exit(1)

    run_dir = root / args.results_dir / args.run_id
    client = AnthropicClient(model=args.model)

    written = run_tasks(
        client,
        tasks,
        run_dir,
        trials=args.trials,
        max_tokens=config["candidate_max_tokens"],
    )

    print(f"Ran {len(tasks)} task(s) x {args.trials} trial(s) -> {len(written)} response file(s) in {run_dir / 'responses'}")


if __name__ == "__main__":
    main()

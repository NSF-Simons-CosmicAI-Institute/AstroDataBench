#!/usr/bin/env python3
"""CLI: grade every response recorded for a run against its task's checklist + rubric.

Usage:
    python scripts/grade.py --run-id 20260810-153000 [--judge-model claude-opus-5]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

from dkqa.config import load_config
from dkqa.grader import grade_response_file
from dkqa.markdown_report import render_grade_markdown
from dkqa.models.anthropic_client import AnthropicClient
from dkqa.scorer import score
from dkqa.schema import Grade
from dkqa.task_loader import load_tasks


def main() -> None:
    load_dotenv()
    root = Path(__file__).resolve().parent.parent
    config = load_config()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True, help="Run identifier previously produced by run.py")
    parser.add_argument("--judge-model", default=config["judge_model"], help="Judge model id used for grading")
    parser.add_argument("--tasks-dir", default=config["tasks_dir"], help="Directory containing task YAML files")
    parser.add_argument("--results-dir", default=config["results_dir"], help="Directory results are stored under")
    args = parser.parse_args()

    run_dir = root / args.results_dir / args.run_id
    responses_dir = run_dir / "responses"
    grades_dir = run_dir / "grades"
    markdown_dir = run_dir / "markdown"
    grades_dir.mkdir(parents=True, exist_ok=True)
    markdown_dir.mkdir(parents=True, exist_ok=True)

    tasks_by_id = {t.id: t for t in load_tasks(root / args.tasks_dir)}
    judge_client = AnthropicClient(model=args.judge_model)

    response_files = sorted(responses_dir.glob("*.json"))
    if not response_files:
        print(f"No response files found in {responses_dir}; run scripts/run.py first.", file=sys.stderr)
        sys.exit(1)

    for response_path in response_files:
        response = json.loads(response_path.read_text())
        task = tasks_by_id.get(response["task_id"])
        if task is None:
            print(f"Skipping {response_path.name}: unknown task id '{response['task_id']}'", file=sys.stderr)
            continue

        record = grade_response_file(
            judge_client, task, response_path, max_tokens=config["judge_max_tokens"], judge_model=args.judge_model
        )
        result = score(task, Grade.model_validate(record["grade"]))
        record["score"] = result.model_dump()

        out_path = grades_dir / response_path.name
        out_path.write_text(json.dumps(record, indent=2))

        markdown = render_grade_markdown(task, response, record)
        markdown_path = markdown_dir / response_path.name.replace(".json", ".md")
        markdown_path.write_text(markdown)

        print(f"Graded {response_path.name}: final_score={result.final_score:.2f}")

    print(f"Wrote grades to {grades_dir}")
    print(f"Wrote markdown reports to {markdown_dir}")
    print("(PDF reports aren't generated here -- run `benchmark.py report --task-pdfs` when you want them)")


if __name__ == "__main__":
    main()

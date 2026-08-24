"""Aggregate a run's grades/*.json into summary.json and summary.csv."""

from __future__ import annotations

import csv
import json
from pathlib import Path


def build_summary(run_dir: Path) -> dict:
    grades_dir = run_dir / "grades"
    records = [json.loads(p.read_text()) for p in sorted(grades_dir.glob("*.json"))]

    by_task: dict[str, list[dict]] = {}
    for r in records:
        by_task.setdefault(r["task_id"], []).append(r)

    tasks_summary = []
    for task_id, trials in by_task.items():
        final_scores = [t["score"]["final_score"] for t in trials]
        checklist_coverages = [t["score"]["checklist_coverage"] for t in trials]
        rubric_normalized = [t["score"]["rubric_normalized"] for t in trials]
        tasks_summary.append(
            {
                "task_id": task_id,
                "category": trials[0]["category"],
                "candidate_model": trials[0]["candidate_model"],
                "n_trials": len(trials),
                "mean_final_score": sum(final_scores) / len(final_scores),
                "mean_checklist_coverage": sum(checklist_coverages) / len(checklist_coverages),
                "mean_rubric_normalized": sum(rubric_normalized) / len(rubric_normalized),
                "trials": trials,
            }
        )

    tasks_summary.sort(key=lambda t: t["task_id"])
    overall_mean = (
        sum(t["mean_final_score"] for t in tasks_summary) / len(tasks_summary) if tasks_summary else 0.0
    )

    return {
        "run_id": run_dir.name,
        "n_tasks": len(tasks_summary),
        "overall_mean_final_score": overall_mean,
        "tasks": tasks_summary,
    }


def write_summary(run_dir: Path) -> tuple[Path, Path]:
    summary = build_summary(run_dir)

    json_path = run_dir / "summary.json"
    json_path.write_text(json.dumps(summary, indent=2))

    csv_path = run_dir / "summary.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["task_id", "category", "candidate_model", "n_trials", "mean_checklist_coverage", "mean_rubric_normalized", "mean_final_score"]
        )
        for t in summary["tasks"]:
            writer.writerow(
                [
                    t["task_id"],
                    t["category"],
                    t["candidate_model"],
                    t["n_trials"],
                    f"{t['mean_checklist_coverage']:.4f}",
                    f"{t['mean_rubric_normalized']:.4f}",
                    f"{t['mean_final_score']:.4f}",
                ]
            )

    return json_path, csv_path

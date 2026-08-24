"""Run the candidate model over a set of tasks and record its raw answers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from dkqa.models.base import ModelClient
from dkqa.schema import Task


def response_path(run_dir: Path, task_id: str, trial: int) -> Path:
    return run_dir / "responses" / f"{task_id}__trial{trial}.json"


def run_task(client: ModelClient, task: Task, *, trial: int, max_tokens: int) -> dict:
    response = client.generate(task.prompt, max_tokens=max_tokens)
    return {
        "task_id": task.id,
        "category": task.category,
        "trial": trial,
        "prompt": task.prompt,
        "response_text": response.text,
        "model": response.model,
        "input_tokens": response.input_tokens,
        "output_tokens": response.output_tokens,
        "latency_s": response.latency_s,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def run_tasks(client: ModelClient, tasks: list[Task], run_dir: Path, *, trials: int, max_tokens: int) -> list[Path]:
    (run_dir / "responses").mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    for task in tasks:
        for trial in range(1, trials + 1):
            record = run_task(client, task, trial=trial, max_tokens=max_tokens)
            path = response_path(run_dir, task.id, trial)
            path.write_text(json.dumps(record, indent=2))
            written.append(path)

    return written

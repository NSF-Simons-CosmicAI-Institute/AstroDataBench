"""Load and validate task YAML files from a tasks directory."""

from __future__ import annotations

from pathlib import Path

import yaml

from dkqa.schema import Task


def load_tasks(tasks_dir: Path) -> list[Task]:
    """Recursively load every ``*.yaml`` file under ``tasks_dir`` into a Task.

    Raises a ValueError (with the offending file path) on the first invalid file,
    rather than silently skipping it.
    """
    tasks: list[Task] = []
    seen_ids: dict[str, Path] = {}

    for path in sorted(tasks_dir.rglob("*.yaml")):
        raw = yaml.safe_load(path.read_text())
        try:
            task = Task.model_validate({**raw, "source_path": path})
        except Exception as exc:
            raise ValueError(f"Invalid task file {path}: {exc}") from exc

        if task.id in seen_ids:
            raise ValueError(
                f"Duplicate task id '{task.id}' in {path} (already used by {seen_ids[task.id]})"
            )
        seen_ids[task.id] = path
        tasks.append(task)

    return tasks


def filter_tasks(tasks: list[Task], filter_expr: str | None) -> list[Task]:
    """Apply a simple ``key=value`` filter, e.g. ``category=optical`` or ``id=optical-seeing``."""
    if not filter_expr:
        return tasks

    if "=" not in filter_expr:
        raise ValueError(f"Invalid --filter '{filter_expr}', expected key=value (e.g. category=optical)")

    key, value = filter_expr.split("=", 1)
    key = key.strip()
    value = value.strip()

    if key not in {"id", "category"}:
        raise ValueError(f"Invalid --filter key '{key}', must be 'id' or 'category'")

    return [t for t in tasks if getattr(t, key) == value]

"""Pure scoring logic: combine a judge's Grade with a Task's checklist/rubric weights
into a single composite score. No API calls here -- fully unit-testable.
"""

from __future__ import annotations

from dkqa.schema import Grade, ScoreResult, ScoringConfig, Task

DEFAULT_SCORING = ScoringConfig()


def resolve_scoring(task: Task, scoring: ScoringConfig | None = None) -> ScoringConfig:
    """The weighting a task actually scores with: an explicit override, else the
    task's own `scoring:` block, else the global default. Shared by score() and
    by the report renderers so the displayed weights always match what was used."""
    return scoring or task.scoring or DEFAULT_SCORING


def _checklist_coverage(task: Task, grade: Grade) -> float:
    satisfied_by_id = {r.id: r.satisfied for r in grade.checklist_results}
    total_weight = sum(item.weight for item in task.checklist)
    if total_weight == 0:
        return 0.0

    earned_weight = sum(
        item.weight for item in task.checklist if satisfied_by_id.get(item.id, False)
    )
    return earned_weight / total_weight


def _rubric_normalized(task: Task, grade: Grade) -> float:
    scale_by_name = {c.name: c.scale for c in task.rubric}
    weight_by_name = {c.name: c.weight for c in task.rubric}

    total_weight = sum(weight_by_name.values())
    if total_weight == 0:
        return 0.0

    earned = 0.0
    for r in grade.rubric_scores:
        scale = scale_by_name.get(r.name)
        weight = weight_by_name.get(r.name)
        if scale is None or weight is None:
            continue  # judge referenced a criterion not defined on the task; ignore
        earned += weight * (r.score / scale)

    return earned / total_weight


def score(task: Task, grade: Grade, scoring: ScoringConfig | None = None) -> ScoreResult:
    if task.id != grade.task_id:
        raise ValueError(f"Task/grade id mismatch: {task.id} != {grade.task_id}")

    cfg = resolve_scoring(task, scoring)

    checklist_coverage = _checklist_coverage(task, grade)
    rubric_normalized = _rubric_normalized(task, grade)
    final_score = cfg.checklist_weight * checklist_coverage + cfg.rubric_weight * rubric_normalized

    return ScoreResult(
        task_id=task.id,
        checklist_coverage=checklist_coverage,
        rubric_normalized=rubric_normalized,
        final_score=final_score,
    )

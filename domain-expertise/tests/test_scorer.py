import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from dkqa.schema import ChecklistItem, ChecklistResult, Grade, RubricCriterion, RubricScore, ScoringConfig, Task
from dkqa.scorer import score
from dkqa.task_loader import filter_tasks, load_tasks

ROOT = Path(__file__).resolve().parent.parent


def make_task(**overrides) -> Task:
    defaults = dict(
        id="t1",
        category="optical",
        prompt="Some question?",
        checklist=[
            ChecklistItem(id="a", text="fact a", weight=1.0),
            ChecklistItem(id="b", text="fact b", weight=1.0),
            ChecklistItem(id="c", text="bonus fact c", weight=0.5),
        ],
        rubric=[
            RubricCriterion(name="accuracy", description="...", scale=5, weight=1.0),
            RubricCriterion(name="clarity", description="...", scale=5, weight=0.5),
        ],
        scoring=ScoringConfig(checklist_weight=0.6, rubric_weight=0.4),
    )
    defaults.update(overrides)
    return Task(**defaults)


def test_perfect_score():
    task = make_task()
    grade = Grade(
        task_id="t1",
        checklist_results=[
            ChecklistResult(id="a", satisfied=True, evidence="..."),
            ChecklistResult(id="b", satisfied=True, evidence="..."),
            ChecklistResult(id="c", satisfied=True, evidence="..."),
        ],
        rubric_scores=[
            RubricScore(name="accuracy", score=5, justification="..."),
            RubricScore(name="clarity", score=5, justification="..."),
        ],
    )
    result = score(task, grade)
    assert result.checklist_coverage == pytest.approx(1.0)
    assert result.rubric_normalized == pytest.approx(1.0)
    assert result.final_score == pytest.approx(1.0)


def test_zero_score():
    task = make_task()
    grade = Grade(
        task_id="t1",
        checklist_results=[
            ChecklistResult(id="a", satisfied=False, evidence="..."),
            ChecklistResult(id="b", satisfied=False, evidence="..."),
            ChecklistResult(id="c", satisfied=False, evidence="..."),
        ],
        rubric_scores=[
            RubricScore(name="accuracy", score=1, justification="..."),
            RubricScore(name="clarity", score=1, justification="..."),
        ],
    )
    result = score(task, grade)
    assert result.checklist_coverage == pytest.approx(0.0)
    # score=1 on a 1-5 scale is not zero credit
    assert result.rubric_normalized == pytest.approx(1 / 5)
    assert result.final_score == pytest.approx(0.6 * 0.0 + 0.4 * 0.2)


def test_partial_checklist_weighting():
    task = make_task()
    grade = Grade(
        task_id="t1",
        checklist_results=[
            ChecklistResult(id="a", satisfied=True, evidence="..."),
            ChecklistResult(id="b", satisfied=False, evidence="..."),
            ChecklistResult(id="c", satisfied=True, evidence="..."),
        ],
        rubric_scores=[
            RubricScore(name="accuracy", score=4, justification="..."),
            RubricScore(name="clarity", score=3, justification="..."),
        ],
    )
    result = score(task, grade)
    # earned weight = 1.0 (a) + 0.5 (c) = 1.5 ; total weight = 1.0+1.0+0.5 = 2.5
    assert result.checklist_coverage == pytest.approx(1.5 / 2.5)
    # earned = 1.0*(4/5) + 0.5*(3/5) = 0.8 + 0.3 = 1.1 ; total weight = 1.5
    assert result.rubric_normalized == pytest.approx(1.1 / 1.5)


def test_missing_checklist_result_counts_as_unsatisfied():
    task = make_task()
    grade = Grade(
        task_id="t1",
        checklist_results=[
            ChecklistResult(id="a", satisfied=True, evidence="..."),
            # 'b' and 'c' omitted entirely
        ],
        rubric_scores=[
            RubricScore(name="accuracy", score=5, justification="..."),
            RubricScore(name="clarity", score=5, justification="..."),
        ],
    )
    result = score(task, grade)
    assert result.checklist_coverage == pytest.approx(1.0 / 2.5)


def test_task_id_mismatch_raises():
    task = make_task()
    grade = Grade(
        task_id="other-task",
        checklist_results=[ChecklistResult(id="a", satisfied=True, evidence="...")],
        rubric_scores=[RubricScore(name="accuracy", score=5, justification="...")],
    )
    with pytest.raises(ValueError):
        score(task, grade)


def test_per_task_scoring_override_used_by_default():
    task = make_task(scoring=ScoringConfig(checklist_weight=1.0, rubric_weight=0.0))
    grade = Grade(
        task_id="t1",
        checklist_results=[
            ChecklistResult(id="a", satisfied=True, evidence="..."),
            ChecklistResult(id="b", satisfied=True, evidence="..."),
            ChecklistResult(id="c", satisfied=True, evidence="..."),
        ],
        rubric_scores=[
            RubricScore(name="accuracy", score=1, justification="..."),
            RubricScore(name="clarity", score=1, justification="..."),
        ],
    )
    result = score(task, grade)
    assert result.final_score == pytest.approx(1.0)


def test_seed_task_yaml_files_load_and_validate():
    tasks = load_tasks(ROOT / "tasks")
    assert tasks  # at least one task file present
    for task in tasks:
        assert task.checklist
        assert task.rubric


def test_filter_tasks_by_category():
    tasks = load_tasks(ROOT / "tasks")
    optical = filter_tasks(tasks, "category=optical")
    assert all(t.category == "optical" for t in optical)
    assert len(optical) >= 1


def test_filter_tasks_invalid_key_raises():
    tasks = load_tasks(ROOT / "tasks")
    with pytest.raises(ValueError):
        filter_tasks(tasks, "bogus=optical")

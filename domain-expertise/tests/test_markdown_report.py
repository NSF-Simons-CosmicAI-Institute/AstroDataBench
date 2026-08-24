import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dkqa.markdown_report import _first_sentence, _pct, render_grade_markdown
from dkqa.schema import ChecklistItem, RubricCriterion, ScoringConfig, Task


def make_task(**overrides) -> Task:
    defaults = dict(
        id="t1",
        category="optical",
        prompt="Some question?\nWith a second line.",
        checklist=[
            ChecklistItem(id="a", text="fact a, spelled out at length", summary="Fact a.", weight=1.0),
            ChecklistItem(id="b", text="fact b, spelled out at length", weight=0.5),
        ],
        rubric=[
            RubricCriterion(name="accuracy", description="...", scale=5, weight=1.0),
        ],
    )
    defaults.update(overrides)
    return Task(**defaults)


def make_response() -> dict:
    return {
        "task_id": "t1",
        "trial": 1,
        "response_text": "Line one.\n\nLine two, a separate paragraph.",
    }


def make_grade_record() -> dict:
    return {
        "task_id": "t1",
        "category": "optical",
        "trial": 1,
        "candidate_model": "claude-sonnet-5",
        "judge_model": "claude-opus-5",
        "grade": {
            "task_id": "t1",
            "checklist_results": [
                {"id": "a", "satisfied": True, "evidence": "quote | with a pipe\nand a newline"},
                {"id": "b", "satisfied": False, "evidence": "missing"},
            ],
            "rubric_scores": [
                {"name": "accuracy", "score": 4, "justification": "solid"},
            ],
        },
        "score": {
            "task_id": "t1",
            "checklist_coverage": 0.5,
            "rubric_normalized": 0.8,
            "final_score": 0.62,
        },
    }


def test_markdown_contains_expected_sections():
    md = render_grade_markdown(make_task(), make_response(), make_grade_record())

    assert "# t1" in md
    assert "# t1 — trial" not in md  # trial number no longer appears in the top header
    assert "## Prompt" in md
    assert "## Model Answer" in md
    assert "Line one.\n\nLine two, a separate paragraph." in md
    assert "## Grading" in md
    assert "### Checklist" in md
    assert "### Rubric" in md


def test_metadata_fields():
    md = render_grade_markdown(make_task(), make_response(), make_grade_record())

    assert "**Category:** optical" in md
    assert "**Trial #:** 1" in md
    assert "**Model:** claude-sonnet-5" in md
    assert "**Candidate model:**" not in md  # old label removed
    assert "**Final score:** 62%" in md


def test_judge_model_label_is_lowercase_model():
    md = render_grade_markdown(make_task(), make_response(), make_grade_record())

    assert "**Judge model:** claude-opus-5" in md
    assert "**Judge Model:**" not in md  # old capitalization removed


def test_grading_section_shows_component_scores():
    md = render_grade_markdown(make_task(), make_response(), make_grade_record())

    # default weights: checklist 60%, rubric 40% (from ScoringConfig defaults)
    assert "**Total score (60% checklist, 40% rubric):** 62%" in md
    assert "**Checklist score:** 50%" in md  # checklist_coverage=0.5
    assert "**Rubric score:** 80%" in md  # rubric_normalized=0.8


def test_weights_shown_come_from_task_not_assumed_default():
    task = make_task(scoring=ScoringConfig(checklist_weight=0.7, rubric_weight=0.3))
    md = render_grade_markdown(task, make_response(), make_grade_record())

    assert "**Total score (70% checklist, 30% rubric):** 62%" in md
    assert "60% checklist" not in md


def test_grading_sections_include_explanatory_asides():
    md = render_grade_markdown(make_task(), make_response(), make_grade_record())

    assert "> A separate judge model reviews the answer" in md
    assert "> Each item is marked satisfied or not" in md
    assert "> Each criterion is scored on its own scale" in md


def test_pct_helper_rounds_to_nearest_percent():
    assert _pct(0.6) == "60%"
    assert _pct(0.825) == "82%" or _pct(0.825) == "83%"  # banker's/normal rounding, either acceptable
    assert _pct(1.0) == "100%"
    assert _pct(0.0) == "0%"


def test_checklist_table_uses_summary_when_present_else_text():
    md = render_grade_markdown(make_task(), make_response(), make_grade_record())

    assert "Fact a." in md  # item 'a' has an explicit summary
    assert "fact b, spelled out at length" in md  # item 'b' falls back to text


def test_checklist_table_escapes_pipes_and_flattens_newlines():
    md = render_grade_markdown(make_task(), make_response(), make_grade_record())

    assert "quote \\| with a pipe and a newline" in md


def test_satisfied_markers_present():
    md = render_grade_markdown(make_task(), make_response(), make_grade_record())

    assert "✅" in md  # item a satisfied
    assert "❌" in md  # item b not satisfied


def test_first_sentence_helper():
    assert _first_sentence("Is this correct? This is extra grading instruction.") == "Is this correct?"
    assert _first_sentence("One sentence with no trailing text.") == "One sentence with no trailing text."
    assert _first_sentence("No terminal punctuation") == "No terminal punctuation"


def test_rubric_table_shows_only_first_sentence_of_description():
    task = make_task()
    task.rubric[0].description = (
        "Is everything stated in the response factually correct? "
        "This should be scored independently of checklist coverage and is extra judge-only instruction."
    )
    md = render_grade_markdown(task, make_response(), make_grade_record())

    assert "Is everything stated in the response factually correct?" in md
    assert "extra judge-only instruction" not in md

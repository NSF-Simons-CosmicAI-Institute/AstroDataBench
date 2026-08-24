"""Render a single (task, trial) grade as a human-readable markdown report."""

from __future__ import annotations

import re

from dkqa.schema import Task
from dkqa.scorer import resolve_scoring

_SENTENCE_END = re.compile(r"[.?!](?=\s|$)")


def _escape_cell(text: str) -> str:
    """Flatten a string to a single line and escape pipes so it's safe inside a
    markdown table cell."""
    return " ".join(text.split()).replace("|", "\\|")


def _first_sentence(text: str) -> str:
    """Return just the first sentence of a rubric description, dropping any
    additional grading instructions meant for the judge model rather than a
    human skimming the report."""
    match = _SENTENCE_END.search(text)
    return text[: match.end()].strip() if match else text.strip()


def _pct(value: float) -> str:
    return f"{round(value * 100)}%"


def render_grade_markdown(task: Task, response: dict, grade_record: dict) -> str:
    grade = grade_record["grade"]
    score = grade_record["score"]
    scoring = resolve_scoring(task)

    checklist_by_id = {item.id: item for item in task.checklist}

    lines: list[str] = []
    lines.append(f"# {task.id}")
    lines.append("")
    lines.append(f"**Category:** {task.category}  ")
    lines.append(f"**Trial #:** {response['trial']}  ")
    lines.append(f"**Model:** {grade_record['candidate_model']}  ")
    lines.append(f"**Final score:** {_pct(score['final_score'])}")
    lines.append("")

    lines.append("## Prompt")
    lines.append("")
    lines.append(task.prompt.strip())
    lines.append("")

    lines.append("## Model Answer")
    lines.append("")
    lines.append(response["response_text"].strip())
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Grading")
    lines.append("")
    lines.append(
        "> A separate judge model reviews the answer above against two things: a "
        "checklist of facts the answer should include, and a qualitative rubric "
        "covering accuracy, confidence assessment, and clarity. Each is scored "
        "independently, then combined into the total score using the weights below."
    )
    lines.append("")
    lines.append(f"**Judge model:** {grade_record['judge_model']}  ")
    lines.append(
        f"**Total score ({_pct(scoring.checklist_weight)} checklist, "
        f"{_pct(scoring.rubric_weight)} rubric):** {_pct(score['final_score'])}"
    )
    lines.append("")

    lines.append("### Checklist")
    lines.append("")
    lines.append(
        "> Each item is marked satisfied or not, with supporting evidence quoted "
        "from the answer. The checklist score is the weighted share of items satisfied."
    )
    lines.append("")
    lines.append(f"**Checklist score:** {_pct(score['checklist_coverage'])}")
    lines.append("")
    lines.append("| ID | Summary | Weight | Satisfied | Evidence |")
    lines.append("|---|---|---|---|---|")
    for result in grade["checklist_results"]:
        item = checklist_by_id.get(result["id"])
        summary = (item.summary or item.text) if item else "(unknown checklist item)"
        weight = item.weight if item else "?"
        satisfied = "✅" if result["satisfied"] else "❌"
        lines.append(
            f"| {_escape_cell(result['id'])} | {_escape_cell(summary)} | {weight} "
            f"| {satisfied} | {_escape_cell(result['evidence'])} |"
        )
    lines.append("")

    lines.append("### Rubric")
    lines.append("")
    lines.append(
        "> Each criterion is scored on its own scale by the judge, with a written "
        "justification. The rubric score is the weighted average across criteria, "
        "normalized to a percentage."
    )
    lines.append("")
    lines.append(f"**Rubric score:** {_pct(score['rubric_normalized'])}")
    lines.append("")
    lines.append("| Criterion | Description | Score | Justification |")
    lines.append("|---|---|---|---|")
    rubric_by_name = {c.name: c for c in task.rubric}
    for r in grade["rubric_scores"]:
        criterion = rubric_by_name.get(r["name"])
        scale = criterion.scale if criterion else "?"
        description = _first_sentence(criterion.description) if criterion else ""
        lines.append(
            f"| {_escape_cell(r['name'])} | {_escape_cell(description)} | {r['score']}/{scale} "
            f"| {_escape_cell(r['justification'])} |"
        )
    lines.append("")

    return "\n".join(lines)

"""Grade candidate responses against a task's checklist + rubric using an LLM judge.

The judge is forced (via tool_choice) to call a `submit_grade` tool whose schema
mirrors dkqa.schema.Grade, so the output is always structured and parseable.
"""

from __future__ import annotations

import json
from pathlib import Path

from dkqa.models.base import ModelClient
from dkqa.schema import Grade, Task

GRADE_TOOL_NAME = "submit_grade"


def _grade_tool_schema(task: Task) -> dict:
    checklist_ids = [item.id for item in task.checklist]
    rubric_names = [c.name for c in task.rubric]

    return {
        "type": "object",
        "properties": {
            "checklist_results": {
                "type": "array",
                "description": "One entry per checklist item, in the same order given.",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "enum": checklist_ids},
                        "satisfied": {
                            "type": "boolean",
                            "description": "Whether the candidate answer satisfies this checklist item.",
                        },
                        "evidence": {
                            "type": "string",
                            "description": "Quote or paraphrase from the candidate answer supporting the verdict, "
                            "or a brief note on why it's missing.",
                        },
                    },
                    "required": ["id", "satisfied", "evidence"],
                },
                "minItems": len(checklist_ids),
                "maxItems": len(checklist_ids),
            },
            "rubric_scores": {
                "type": "array",
                "description": "One entry per rubric criterion, in the same order given.",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "enum": rubric_names},
                        "score": {"type": "integer", "description": "Integer score on the criterion's stated scale."},
                        "justification": {"type": "string"},
                    },
                    "required": ["name", "score", "justification"],
                },
                "minItems": len(rubric_names),
                "maxItems": len(rubric_names),
            },
        },
        "required": ["checklist_results", "rubric_scores"],
    }


def _build_grading_prompt(task: Task, candidate_answer: str) -> str:
    checklist_lines = "\n".join(
        f"- [{item.id}] (weight {item.weight}): {item.text}" for item in task.checklist
    )
    rubric_lines = "\n".join(
        f"- {c.name} (1-{c.scale}, weight {c.weight}): {c.description}" for c in task.rubric
    )

    return f"""You are grading an LLM's answer to a multiwavelength astronomy domain-knowledge question.

# Question
{task.prompt}

# Candidate answer
{candidate_answer}

# Gold-standard checklist
Mark each item as satisfied only if the candidate answer actually communicates it (correctly).
Do not give credit for near-misses, vague gestures at the topic, or factually incorrect statements.
{checklist_lines}

# Grading rubric
Score each criterion on its stated integer scale.
{rubric_lines}

Call the `{GRADE_TOOL_NAME}` tool with your full evaluation. Cite specific evidence from the
candidate answer for every checklist verdict and rubric score.
"""


def grade_response(judge_client: ModelClient, task: Task, candidate_answer: str, *, max_tokens: int) -> Grade:
    prompt = _build_grading_prompt(task, candidate_answer)
    raw = judge_client.generate_structured(
        prompt,
        tool_name=GRADE_TOOL_NAME,
        tool_description="Submit the checklist verdicts and rubric scores for this candidate answer.",
        tool_schema=_grade_tool_schema(task),
        max_tokens=max_tokens,
    )
    return Grade.model_validate({**raw, "task_id": task.id})


def grade_response_file(
    judge_client: ModelClient, task: Task, response_path: Path, *, max_tokens: int, judge_model: str
) -> dict:
    response = json.loads(response_path.read_text())
    grade = grade_response(judge_client, task, response["response_text"], max_tokens=max_tokens)
    return {
        "task_id": task.id,
        "category": task.category,
        "trial": response["trial"],
        "candidate_model": response["model"],
        "judge_model": judge_model,
        "grade": grade.model_dump(),
    }

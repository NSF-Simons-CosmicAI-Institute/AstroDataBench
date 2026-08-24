"""Pydantic models describing a domain-knowledge task file and its grading output."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class ChecklistItem(BaseModel):
    id: str
    text: str
    weight: float = 1.0
    summary: Optional[str] = None  # short, one-sentence label for reports; falls back to `text` if unset


class RubricCriterion(BaseModel):
    name: str
    description: str
    scale: int = 5
    weight: float = 1.0


class ScoringConfig(BaseModel):
    checklist_weight: float = 0.6
    rubric_weight: float = 0.4


class Task(BaseModel):
    id: str
    category: str
    prompt: str
    checklist: list[ChecklistItem]
    rubric: list[RubricCriterion]
    scoring: ScoringConfig = Field(default_factory=ScoringConfig)
    source_path: Optional[Path] = None

    @model_validator(mode="after")
    def _non_empty(self) -> "Task":
        if not self.checklist:
            raise ValueError(f"Task '{self.id}' must define at least one checklist item")
        if not self.rubric:
            raise ValueError(f"Task '{self.id}' must define at least one rubric criterion")
        return self


class ChecklistResult(BaseModel):
    id: str
    satisfied: bool
    evidence: str


class RubricScore(BaseModel):
    name: str
    score: int
    justification: str


class Grade(BaseModel):
    """Raw structured output from the judge model for a single (task, response) pair."""

    task_id: str
    checklist_results: list[ChecklistResult]
    rubric_scores: list[RubricScore]


class ScoreResult(BaseModel):
    """Final computed score for a single (task, response) pair."""

    task_id: str
    checklist_coverage: float
    rubric_normalized: float
    final_score: float

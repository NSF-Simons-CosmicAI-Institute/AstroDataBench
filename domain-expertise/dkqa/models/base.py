"""Provider-agnostic model client interface.

Only an Anthropic implementation exists today (see anthropic_client.py), but runner.py
and grader.py are written against this interface so another provider (OpenAI, Gemini, ...)
can be added later as a new ModelClient subclass without touching the pipeline.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from pydantic import BaseModel


class ModelResponse(BaseModel):
    text: str
    model: str
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    latency_s: float


class ModelClient(ABC):
    @abstractmethod
    def generate(self, prompt: str, *, max_tokens: int) -> ModelResponse:
        """Return a single free-text completion for ``prompt``."""

    @abstractmethod
    def generate_structured(
        self,
        prompt: str,
        *,
        tool_name: str,
        tool_description: str,
        tool_schema: dict,
        max_tokens: int,
    ) -> dict:
        """Force a single tool call and return its parsed input as a dict."""

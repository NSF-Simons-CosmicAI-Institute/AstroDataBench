from __future__ import annotations

import time

import anthropic

from dkqa.models.base import ModelClient, ModelResponse

_RETRYABLE = (anthropic.APIConnectionError, anthropic.APIStatusError, anthropic.RateLimitError)


class AnthropicClient(ModelClient):
    def __init__(self, model: str, *, max_retries: int = 1, retry_wait_s: float = 5.0):
        self.model = model
        self.max_retries = max_retries
        self.retry_wait_s = retry_wait_s
        self._client = anthropic.Anthropic()

    def _with_retry(self, fn):
        attempt = 0
        while True:
            try:
                return fn()
            except _RETRYABLE:
                if attempt >= self.max_retries:
                    raise
                attempt += 1
                time.sleep(self.retry_wait_s)

    def generate(self, prompt: str, *, max_tokens: int) -> ModelResponse:
        start = time.monotonic()
        message = self._with_retry(
            lambda: self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
        )
        latency_s = time.monotonic() - start

        text = "".join(block.text for block in message.content if block.type == "text")
        return ModelResponse(
            text=text,
            model=message.model,
            input_tokens=message.usage.input_tokens,
            output_tokens=message.usage.output_tokens,
            latency_s=latency_s,
        )

    def generate_structured(
        self,
        prompt: str,
        *,
        tool_name: str,
        tool_description: str,
        tool_schema: dict,
        max_tokens: int,
    ) -> dict:
        message = self._with_retry(
            lambda: self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
                tools=[
                    {
                        "name": tool_name,
                        "description": tool_description,
                        "input_schema": tool_schema,
                    }
                ],
                tool_choice={"type": "tool", "name": tool_name},
            )
        )

        for block in message.content:
            if block.type == "tool_use" and block.name == tool_name:
                return block.input

        raise RuntimeError(f"Judge model did not return a '{tool_name}' tool call: {message.content}")

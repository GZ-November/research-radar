"""Deterministic structured mock used by the Golden Demo."""

import json
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel


ResponseT = TypeVar("ResponseT", bound=BaseModel)


class MockLLMClient:
    def __init__(self, responses: dict[str, dict] | Path):
        self.responses = (
            json.loads(Path(responses).read_text(encoding="utf-8"))
            if isinstance(responses, Path)
            else responses
        )

    def generate_structured(
        self, *, stage: str, prompt: str, response_model: type[ResponseT]
    ) -> ResponseT:
        if stage not in self.responses:
            raise LookupError(f"mock response missing for stage: {stage}")
        return response_model.model_validate(self.responses[stage])


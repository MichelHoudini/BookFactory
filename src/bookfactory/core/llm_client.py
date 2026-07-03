from __future__ import annotations

from typing import Protocol


class LLMClientError(RuntimeError):
    """Base exception for LLM client failures."""


class LLMRequestError(LLMClientError):
    """Raised when an LLM request fails."""


class EmptyLLMResponseError(LLMClientError):
    """Raised when an LLM returns no usable text."""


class LLMClient(Protocol):
    def generate(self, instructions: str, user_input: str) -> str: ...


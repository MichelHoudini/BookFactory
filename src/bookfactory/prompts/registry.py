from __future__ import annotations

import re
from pathlib import Path
from typing import Final

_PROMPT_NAME: Final[re.Pattern[str]] = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")


class PromptNotFoundError(LookupError):
    """Raised when a named prompt does not exist."""


class InvalidPromptNameError(ValueError):
    """Raised when a prompt name is not a safe logical name."""


class PromptRegistry:
    def __init__(self, prompt_directory: Path) -> None:
        self._prompt_directory = prompt_directory
        self._cache: dict[str, str] = {}

    def load(self, name: str) -> str:
        self._validate_name(name)
        if name in self._cache:
            return self._cache[name]

        path = self._prompt_directory / f"{name}.md"
        try:
            prompt = path.read_text(encoding="utf-8")
        except FileNotFoundError as error:
            raise PromptNotFoundError(f"prompt {name!r} does not exist") from error

        self._cache[name] = prompt
        return prompt

    @staticmethod
    def _validate_name(name: str) -> None:
        if _PROMPT_NAME.fullmatch(name) is None:
            raise InvalidPromptNameError(f"invalid prompt name: {name!r}")


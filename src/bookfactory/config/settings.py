from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Final, Self

from dotenv import load_dotenv

load_dotenv()

DEFAULT_OPENAI_MODEL: Final = "gpt-4.1-mini"


class SettingsError(ValueError):
    """Raised when application settings are missing or invalid."""


@dataclass(frozen=True, slots=True)
class Settings:
    openai_api_key: str = field(repr=False)
    openai_model: str

    def __post_init__(self) -> None:
        if not self.openai_api_key.strip():
            raise SettingsError("OPENAI_API_KEY must not be empty")
        if not self.openai_model.strip():
            raise SettingsError("OPENAI_MODEL must not be empty")

    @classmethod
    def from_environment(cls) -> Self:
        api_key = os.environ.get("OPENAI_API_KEY")
        if api_key is None:
            raise SettingsError("OPENAI_API_KEY is required")
        model = os.environ.get("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
        return cls(openai_api_key=api_key, openai_model=model)

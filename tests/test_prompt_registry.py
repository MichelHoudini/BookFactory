from pathlib import Path

import pytest

from bookfactory.prompts.registry import (
    InvalidPromptNameError,
    PromptNotFoundError,
    PromptRegistry,
)


def test_loads_utf8_markdown_prompt(tmp_path: Path) -> None:
    (tmp_path / "translate.md").write_text(
        "Translate with precisão.", encoding="utf-8"
    )
    registry = PromptRegistry(tmp_path)

    assert registry.load("translate") == "Translate with precisão."


def test_returns_cached_prompt_without_rereading_file(tmp_path: Path) -> None:
    prompt_path = tmp_path / "translate.md"
    prompt_path.write_text("Original prompt", encoding="utf-8")
    registry = PromptRegistry(tmp_path)

    assert registry.load("translate") == "Original prompt"
    prompt_path.unlink()

    assert registry.load("translate") == "Original prompt"


def test_missing_prompt_raises_clear_error(tmp_path: Path) -> None:
    registry = PromptRegistry(tmp_path)

    with pytest.raises(PromptNotFoundError, match="prompt 'missing' does not exist"):
        registry.load("missing")


@pytest.mark.parametrize(
    "name",
    ("", "../translate", "nested/translate", "translate.md", "two words"),
)
def test_rejects_unsafe_prompt_names(tmp_path: Path, name: str) -> None:
    registry = PromptRegistry(tmp_path)

    with pytest.raises(InvalidPromptNameError, match="invalid prompt name"):
        registry.load(name)


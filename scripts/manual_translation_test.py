from __future__ import annotations

from pathlib import Path
from time import perf_counter

from bookfactory.adapters.html_ingest import read_html
from bookfactory.adapters.openai_client import OpenAIClient
from bookfactory.config.settings import Settings
from bookfactory.core.translation_unit import (
    build_translation_unit_text,
    generate_translation_units,
)
from bookfactory.prompts.registry import PromptRegistry

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_PATH = PROJECT_ROOT / "input" / "book.html"
PROMPT_DIRECTORY = PROJECT_ROOT / "prompts"


def main() -> None:
    document = read_html(INPUT_PATH)
    units = generate_translation_units(document)
    if not units:
        raise RuntimeError("input document contains no translation units")

    instructions = PromptRegistry(PROMPT_DIRECTORY).load("translate")
    settings = Settings.from_environment()
    client = OpenAIClient(settings)
    original_text = build_translation_unit_text(document, units[0])

    started_at = perf_counter()
    translated_text = client.generate(instructions, original_text)
    elapsed_seconds = perf_counter() - started_at

    print(f"Original text:\n{original_text}")
    print(f"\nTranslated text:\n{translated_text}")
    print(f"\nElapsed time:\n{elapsed_seconds:.2f} seconds")


if __name__ == "__main__":
    main()

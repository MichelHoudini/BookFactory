from __future__ import annotations

from pathlib import Path
from time import perf_counter

from bookfactory.adapters.epub_export import write_epub
from bookfactory.adapters.epub_ingest import read_epub
from bookfactory.adapters.openai_client import OpenAIClient
from bookfactory.config.settings import Settings
from bookfactory.core.translation import (
    TranslationResult,
    reconstruct_translated_document,
    translate_document,
)
from bookfactory.core.translation_unit import generate_translation_units
from bookfactory.prompts.registry import PromptRegistry

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_PATH = PROJECT_ROOT / "input" / "book.epub"
OUTPUT_PATH = PROJECT_ROOT / "output" / "book_pt.epub"
CACHE_DIRECTORY = PROJECT_ROOT / "output" / "cache"
PROMPT_DIRECTORY = PROJECT_ROOT / "prompts"
MAX_UNITS: int | None = None


def main() -> None:
    started_at = perf_counter()
    document = read_epub(INPUT_PATH)
    units = generate_translation_units(document)
    if not units:
        raise RuntimeError("input document contains no translation units")
    if MAX_UNITS is not None and MAX_UNITS < 0:
        raise ValueError("MAX_UNITS must be non-negative or None")
    units_to_process = units if MAX_UNITS is None else units[:MAX_UNITS]

    instructions: str | None = None
    client: OpenAIClient | None = None
    results: list[TranslationResult] = []

    for index, unit in enumerate(units_to_process, start=1):
        cache_path = CACHE_DIRECTORY / f"{index:04d}.txt"
        if cache_path.exists():
            print(f"Loading cached unit {index}/{len(units_to_process)}")
            translated_text = cache_path.read_text(encoding="utf-8")
        else:
            if client is None:
                instructions = PromptRegistry(PROMPT_DIRECTORY).load("translate")
                settings = Settings.from_environment()
                client = OpenAIClient(settings)

            print(f"Translating unit {index}/{len(units_to_process)}")
            assert instructions is not None
            translated_text = translate_document(
                document, (unit,), instructions, client
            )[0].translated_text
            CACHE_DIRECTORY.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(translated_text, encoding="utf-8", newline="")

        results.append(TranslationResult(unit, translated_text))

    if len(units_to_process) < len(units):
        elapsed_seconds = perf_counter() - started_at
        print(f"Translation units completed: {len(units_to_process)}/{len(units)}")
        print(f"Elapsed time: {elapsed_seconds:.2f} seconds")
        return

    translated_document = reconstruct_translated_document(document, tuple(results))
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    write_epub(
        translated_document,
        OUTPUT_PATH,
        language="pt-BR",
        source_epub=INPUT_PATH,
    )
    elapsed_seconds = perf_counter() - started_at

    print(f"Chapters: {len(document.book.sections)}")
    print(f"Translation units: {len(units)}")
    print(f"Elapsed time: {elapsed_seconds:.2f} seconds")
    print(f"Output file: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

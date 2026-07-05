from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path
from time import perf_counter

from bookfactory.adapters.epub_export import write_epub
from bookfactory.adapters.epub_ingest import read_epub
from bookfactory.adapters.openai_client import OpenAIClient
from bookfactory.config.settings import Settings
from bookfactory.core.document import Document
from bookfactory.core.translation import TranslationResult, translate_document
from bookfactory.core.translation_unit import generate_translation_units
from bookfactory.prompts.registry import PromptRegistry

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_PATH = PROJECT_ROOT / "input" / "book.epub"
OUTPUT_PATH = PROJECT_ROOT / "output" / "book_pt.epub"
CACHE_DIRECTORY = PROJECT_ROOT / "output" / "cache"
PROMPT_DIRECTORY = PROJECT_ROOT / "prompts"


def reconstruct_translated_document(
    document: Document,
    results: tuple[TranslationResult, ...],
) -> Document:
    source_block_ids = tuple(block.block_id for block in document.blocks)
    result_block_ids: list[str] = []
    translated_by_id: dict[str, str] = {}

    for result in results:
        block_ids = result.translation_unit.block_ids
        translated_blocks = _split_translated_text(
            result.translated_text, len(block_ids)
        )
        result_block_ids.extend(block_ids)
        translated_by_id.update(zip(block_ids, translated_blocks, strict=True))

    if tuple(result_block_ids) != source_block_ids:
        raise ValueError(
            "translation results do not cover document blocks exactly in order"
        )

    sections = tuple(
        replace(
            section,
            blocks=tuple(
                replace(block, text=translated_by_id[block.block_id])
                for block in section.blocks
            ),
        )
        for section in document.book.sections
    )
    return replace(document, book=replace(document.book, sections=sections))


def _split_translated_text(text: str, expected_blocks: int) -> tuple[str, ...]:
    blocks = tuple(
        block.strip() for block in re.split(r"\r?\n[ \t]*\r?\n", text.strip())
    )
    if len(blocks) != expected_blocks or any(not block for block in blocks):
        raise ValueError(
            "translated unit did not preserve the source block boundaries: "
            f"expected {expected_blocks}, received {len(blocks)}"
        )
    return blocks


def main() -> None:
    started_at = perf_counter()
    document = read_epub(INPUT_PATH)
    units = generate_translation_units(document)
    if not units:
        raise RuntimeError("input document contains no translation units")

    instructions = PromptRegistry(PROMPT_DIRECTORY).load("translate")
    client: OpenAIClient | None = None
    results: list[TranslationResult] = []

    for index, unit in enumerate(units, start=1):
        cache_path = CACHE_DIRECTORY / f"{index:04d}.txt"
        if cache_path.exists():
            print(f"Loading cached unit {index}/{len(units)}")
            translated_text = cache_path.read_text(encoding="utf-8")
        else:
            if client is None:
                settings = Settings.from_environment()
                client = OpenAIClient(settings)

            print(f"Translating unit {index}/{len(units)}")
            translated_text = translate_document(
                document, (unit,), instructions, client
            )[0].translated_text
            CACHE_DIRECTORY.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(translated_text, encoding="utf-8", newline="")

        results.append(TranslationResult(unit, translated_text))

    translated_document = reconstruct_translated_document(document, tuple(results))
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    write_epub(
        translated_document,
        OUTPUT_PATH,
    )
    elapsed_seconds = perf_counter() - started_at

    print(f"Chapters: {len(document.book.sections)}")
    print(f"Translation units: {len(units)}")
    print(f"Elapsed time: {elapsed_seconds:.2f} seconds")
    print(f"Output file: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

from __future__ import annotations

from collections.abc import Callable
from hashlib import sha256
from pathlib import Path
from time import perf_counter

from bookfactory.adapters.epub_export import write_epub
from bookfactory.adapters.epub_ingest import read_epub
from bookfactory.adapters.openai_client import OpenAIClient
from bookfactory.config.settings import Settings
from bookfactory.core.document import Document
from bookfactory.core.llm_client import LLMClient
from bookfactory.core.translation import (
    ReconstructionError,
    TranslationResult,
    reconstruct_translated_document,
    translate_document,
    validate_translation_markers,
)
from bookfactory.core.translation_unit import (
    TranslationUnit,
    generate_translation_units,
)
from bookfactory.prompts.registry import PromptRegistry

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_PATH = PROJECT_ROOT / "input" / "book.epub"
OUTPUT_DIRECTORY = PROJECT_ROOT / "output"
CACHE_ROOT = PROJECT_ROOT / "output" / "cache"
PROMPT_DIRECTORY = PROJECT_ROOT / "prompts"
MAX_RETRIES = 3
HASH_PREFIX_LENGTH = 16


def compute_book_hash(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def cache_directory_for_book(book_hash: str) -> Path:
    return CACHE_ROOT / book_hash[:HASH_PREFIX_LENGTH]


def output_path_for_input(input_path: Path) -> Path:
    return OUTPUT_DIRECTORY / f"{input_path.stem}_pt.epub"


def translate_units_with_cache(
    document: Document,
    units: tuple[TranslationUnit, ...],
    instructions: str,
    client_factory: Callable[[], LLMClient],
    cache_directory: Path,
) -> tuple[TranslationResult, ...]:
    client: LLMClient | None = None
    results: list[TranslationResult] = []
    total_units = len(units)

    for index, unit in enumerate(units, start=1):
        cache_path = cache_directory / f"{index:04d}.txt"
        translated_text = _load_valid_cache(cache_path, len(unit.block_ids))
        if translated_text is not None:
            print(f"Loading cached unit {index}/{total_units}")
        else:
            if client is None:
                client = client_factory()
            print(f"Translating unit {index}/{total_units}")
            translated_text = _translate_with_retries(
                document, unit, instructions, client, index
            )
            cache_directory.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(translated_text, encoding="utf-8", newline="")
        results.append(TranslationResult(unit, translated_text))

    return tuple(results)


def _load_valid_cache(path: Path, expected_count: int) -> str | None:
    if not path.exists():
        return None
    translated_text = path.read_text(encoding="utf-8")
    try:
        validate_translation_markers(translated_text, expected_count)
    except ReconstructionError:
        path.unlink()
        return None
    return translated_text


def _translate_with_retries(
    document: Document,
    unit: TranslationUnit,
    instructions: str,
    client: LLMClient,
    unit_number: int,
) -> str:
    last_error: ReconstructionError | None = None
    for _retry_count in range(MAX_RETRIES + 1):
        translated_text = translate_document(
            document, (unit,), instructions, client
        )[0].translated_text
        try:
            validate_translation_markers(translated_text, len(unit.block_ids))
        except ReconstructionError as error:
            last_error = error
            continue
        return translated_text

    assert last_error is not None
    raise ReconstructionError(
        f"translation unit {unit_number}: {last_error}; "
        f"retry count: {MAX_RETRIES}"
    ) from last_error


def main() -> None:
    started_at = perf_counter()
    book_hash = compute_book_hash(INPUT_PATH)
    cache_directory = cache_directory_for_book(book_hash)
    document = read_epub(INPUT_PATH)
    translation_units = tuple(generate_translation_units(document))
    total_units = len(translation_units)
    output_path = output_path_for_input(INPUT_PATH)

    print(f"Book: {document.book.title}")
    print(f"Input: {INPUT_PATH}")
    print(f"Book hash: {book_hash}")
    print(f"Translation units: {total_units}")
    print(f"Cache directory: {cache_directory}")

    if total_units == 0:
        raise RuntimeError("input document contains no translation units")

    instructions = PromptRegistry(PROMPT_DIRECTORY).load("translate")
    results = translate_units_with_cache(
        document,
        translation_units,
        instructions,
        lambda: OpenAIClient(Settings.from_environment()),
        cache_directory,
    )

    translated_document = reconstruct_translated_document(document, results)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_epub(
        translated_document,
        output_path,
    )
    elapsed_seconds = perf_counter() - started_at

    print(f"Chapters: {len(document.book.sections)}")
    print(f"Elapsed time: {elapsed_seconds:.2f} seconds")
    print(f"Output file: {output_path}")


if __name__ == "__main__":
    main()

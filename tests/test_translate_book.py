from pathlib import Path
from unittest.mock import patch

import pytest

import scripts.translate_book as runner
from bookfactory.core.document import Block, BlockKind, Book, Document, Section
from bookfactory.core.translation import ReconstructionError, TranslationResult
from bookfactory.core.translation_unit import TranslationUnit
from scripts.translate_book import (
    MAX_RETRIES,
    cache_directory_for_book,
    compute_book_hash,
    output_path_for_input,
    translate_units_with_cache,
)


class FakeLLMClient:
    def __init__(self, responses: list[str]) -> None:
        self.responses = iter(responses)
        self.calls: list[str] = []

    def generate(self, instructions: str, user_input: str) -> str:
        self.calls.append(user_input)
        return next(self.responses)


class CacheCheckingClient(FakeLLMClient):
    def __init__(self, responses: list[str], invalid_path: Path) -> None:
        super().__init__(responses)
        self.invalid_path = invalid_path

    def generate(self, instructions: str, user_input: str) -> str:
        assert not self.invalid_path.exists()
        return super().generate(instructions, user_input)


def _document() -> Document:
    blocks = tuple(
        Block(f"block-{index:06d}", BlockKind.PARAGRAPH, text)
        for index, text in enumerate(("First", "Second", "Third"), start=1)
    )
    return Document(Book("Test", None, (Section(blocks),)))


def _units() -> tuple[TranslationUnit, ...]:
    return tuple(
        TranslationUnit((f"block-{index:06d}",), 1)
        for index in range(1, 4)
    )


def test_changing_epub_changes_cache_directory(tmp_path: Path) -> None:
    epub_path = tmp_path / "book.epub"
    epub_path.write_bytes(b"first book")
    first_hash = compute_book_hash(epub_path)

    epub_path.write_bytes(b"changed book")
    second_hash = compute_book_hash(epub_path)

    assert first_hash != second_hash
    assert cache_directory_for_book(first_hash) != cache_directory_for_book(
        second_hash
    )


def test_different_books_never_share_cache_directory(tmp_path: Path) -> None:
    first_path = tmp_path / "first.epub"
    second_path = tmp_path / "second.epub"
    first_path.write_bytes(b"first")
    second_path.write_bytes(b"second")

    first_cache = cache_directory_for_book(compute_book_hash(first_path))
    second_cache = cache_directory_for_book(compute_book_hash(second_path))

    assert first_cache != second_cache
    assert len(first_cache.name) == 16
    assert len(second_cache.name) == 16


def test_output_filename_follows_input_filename() -> None:
    output_path = output_path_for_input(Path("input/The Fisherman.epub"))

    assert output_path.name == "The Fisherman_pt.epub"


def test_missing_cached_marker_retries_only_that_unit(tmp_path: Path) -> None:
    cached_first = "[[BLOCK_0001]]\nPrimeiro"
    cached_third = "[[BLOCK_0001]]\nTerceiro"
    (tmp_path / "0001.txt").write_text(cached_first, encoding="utf-8")
    invalid_path = tmp_path / "0002.txt"
    invalid_path.write_text("Segundo sem marcador", encoding="utf-8")
    (tmp_path / "0003.txt").write_text(cached_third, encoding="utf-8")
    client = CacheCheckingClient(
        ["Ainda sem marcador", "[[BLOCK_0001]]\nSegundo"], invalid_path
    )

    results = translate_units_with_cache(
        _document(), _units(), "Instructions", lambda: client, tmp_path
    )

    assert client.calls == [
        "[[BLOCK_0001]]\nSecond",
        "[[BLOCK_0001]]\nSecond",
    ]
    assert [result.translated_text for result in results] == [
        cached_first,
        "[[BLOCK_0001]]\nSegundo",
        cached_third,
    ]
    assert (tmp_path / "0001.txt").read_text(encoding="utf-8") == cached_first
    assert (tmp_path / "0003.txt").read_text(encoding="utf-8") == cached_third


def test_reported_total_comes_only_from_generated_units(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    valid = "[[BLOCK_0001]]\nCached"
    for index in range(1, 5):
        (tmp_path / f"{index:04d}.txt").write_text(valid, encoding="utf-8")

    results = translate_units_with_cache(
        _document(),
        _units(),
        "Instructions",
        lambda: (_ for _ in ()).throw(AssertionError("client was created")),
        tmp_path,
    )

    assert len(results) == 3
    assert capsys.readouterr().out.splitlines() == [
        "Loading cached unit 1/3",
        "Loading cached unit 2/3",
        "Loading cached unit 3/3",
    ]


def test_main_generates_units_once_and_reports_stable_startup_total(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    input_path = tmp_path / "A Book.epub"
    input_path.write_bytes(b"epub bytes")
    document = _document()
    units = _units()
    results = tuple(
        TranslationResult(unit, "[[BLOCK_0001]]\nTranslated")
        for unit in units
    )

    with (
        patch.object(runner, "INPUT_PATH", input_path),
        patch.object(runner, "OUTPUT_DIRECTORY", tmp_path / "output"),
        patch.object(runner, "CACHE_ROOT", tmp_path / "cache"),
        patch.object(runner, "read_epub", return_value=document),
        patch.object(
            runner, "generate_translation_units", return_value=units
        ) as generate,
        patch.object(runner, "PromptRegistry") as registry,
        patch.object(
            runner, "translate_units_with_cache", return_value=results
        ),
        patch.object(
            runner, "reconstruct_translated_document", return_value=document
        ),
        patch.object(runner, "write_epub") as write_epub,
    ):
        registry.return_value.load.return_value = "Instructions"
        runner.main()

    generate.assert_called_once_with(document)
    write_epub.assert_called_once_with(
        document, tmp_path / "output" / "A Book_pt.epub"
    )
    output_lines = capsys.readouterr().out.splitlines()
    assert f"Book: {document.book.title}" in output_lines
    assert f"Input: {input_path}" in output_lines
    assert "Translation units: 3" in output_lines
    assert sum(line.startswith("Translation units:") for line in output_lines) == 1


def test_retry_exhaustion_identifies_unit_marker_and_count(tmp_path: Path) -> None:
    unit = _units()[0]
    client = FakeLLMClient(["Missing marker"] * (MAX_RETRIES + 1))

    with pytest.raises(ReconstructionError) as error:
        translate_units_with_cache(
            _document(), (unit,), "Instructions", lambda: client, tmp_path
        )

    message = str(error.value)
    assert "translation unit 1" in message
    assert "missing block marker: [[BLOCK_0001]]" in message
    assert f"retry count: {MAX_RETRIES}" in message
    assert len(client.calls) == MAX_RETRIES + 1
    assert not (tmp_path / "0001.txt").exists()

import pytest

from bookfactory.core.document import Block, BlockKind, Book, Document, Section
from bookfactory.core.llm_client import LLMClient
from bookfactory.core.translation import (
    ReconstructionError,
    TranslationResult,
    reconstruct_translated_document,
    translate_document,
)
from bookfactory.core.translation_unit import TranslationUnit


class FakeLLMClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def generate(self, instructions: str, user_input: str) -> str:
        self.calls.append((instructions, user_input))
        return f"translated-{len(self.calls)}"


def _document() -> Document:
    blocks = (
        Block("block-000001", BlockKind.PARAGRAPH, "First block"),
        Block("block-000002", BlockKind.PARAGRAPH, "Second block"),
        Block("block-000003", BlockKind.PARAGRAPH, "Third block"),
    )
    return Document(Book("Test book", None, (Section(blocks),)))


def test_translates_every_unit_in_order() -> None:
    units = (
        TranslationUnit(("block-000001", "block-000002"), 4),
        TranslationUnit(("block-000003",), 2),
    )
    client = FakeLLMClient()
    llm_client: LLMClient = client

    results = translate_document(_document(), units, "Shared instructions", llm_client)

    assert results == (
        TranslationResult(units[0], "translated-1"),
        TranslationResult(units[1], "translated-2"),
    )
    assert results[0].translation_unit is units[0]
    assert client.calls == [
        (
            "Shared instructions",
            "[[BLOCK_0001]]\nFirst block\n\n[[BLOCK_0002]]\nSecond block",
        ),
        ("Shared instructions", "[[BLOCK_0001]]\nThird block"),
    ]


def _translation_results(
    first_unit_text: str,
) -> tuple[TranslationResult, ...]:
    first_unit = TranslationUnit(("block-000001", "block-000002"), 4)
    second_unit = TranslationUnit(("block-000003",), 2)
    return (
        TranslationResult(first_unit, first_unit_text),
        TranslationResult(second_unit, "[[BLOCK_0001]]\nTerceiro bloco"),
    )


def test_reconstructs_document_without_changing_block_structure() -> None:
    results = _translation_results(
        "[[BLOCK_0001]]\nPrimeiro bloco\n\n"
        "[[BLOCK_0002]]\nSegundo bloco"
    )

    translated = reconstruct_translated_document(_document(), results)

    assert [block.text for block in translated.blocks] == [
        "Primeiro bloco",
        "Segundo bloco",
        "Terceiro bloco",
    ]
    assert [block.block_id for block in translated.blocks] == [
        block.block_id for block in _document().blocks
    ]


@pytest.mark.parametrize(
    ("translated_text", "message"),
    (
        ("[[BLOCK_0001]]\nPrimeiro bloco", "missing block marker"),
        (
            "[[BLOCK_0001]]\nPrimeiro\n[[BLOCK_0001]]\nSegundo",
            "duplicated block marker",
        ),
        (
            "[[BLOCK_0002]]\nSegundo\n[[BLOCK_0001]]\nPrimeiro",
            "block markers are reordered",
        ),
        (
            "[[BLOCK_0001]]\nPrimeiro\n[[BLOCK_9999]]\nSegundo",
            "unknown block marker",
        ),
    ),
)
def test_reconstruction_rejects_invalid_markers(
    translated_text: str, message: str
) -> None:
    with pytest.raises(ReconstructionError, match=message):
        reconstruct_translated_document(
            _document(), _translation_results(translated_text)
        )


def test_reconstruction_preserves_blank_lines_inside_a_block() -> None:
    results = _translation_results(
        "[[BLOCK_0001]]\nPrimeira linha\n\n\nSegunda linha\n\n"
        "[[BLOCK_0002]]\nSegundo bloco"
    )

    translated = reconstruct_translated_document(_document(), results)

    assert translated.blocks[0].text == "Primeira linha\n\n\nSegunda linha"


def test_reconstruction_does_not_require_blank_lines_between_blocks() -> None:
    results = _translation_results(
        "[[BLOCK_0001]]\nPrimeiro bloco\n"
        "[[BLOCK_0002]]\nSegundo bloco"
    )

    translated = reconstruct_translated_document(_document(), results)

    assert [block.text for block in translated.blocks] == [
        "Primeiro bloco",
        "Segundo bloco",
        "Terceiro bloco",
    ]


def test_non_marker_preamble_does_not_define_a_block_boundary() -> None:
    results = _translation_results(
        "Ignored preamble\n\n[[BLOCK_0001]]\nPrimeiro bloco\n"
        "[[BLOCK_0002]]\nSegundo bloco"
    )

    translated = reconstruct_translated_document(_document(), results)

    assert translated.blocks[0].text == "Primeiro bloco"


def test_result_coverage_error_is_not_a_reconstruction_error() -> None:
    result = TranslationResult(
        TranslationUnit(("block-000001",), 2),
        "[[BLOCK_0001]]\nPrimeiro bloco",
    )

    with pytest.raises(ValueError, match="exactly in order") as error:
        reconstruct_translated_document(_document(), (result,))

    assert not isinstance(error.value, ReconstructionError)

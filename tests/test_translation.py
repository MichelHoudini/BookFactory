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
    first_section = (
        Block("block-000001", BlockKind.PARAGRAPH, "First block"),
        Block("block-000002", BlockKind.PARAGRAPH, "Second block"),
    )
    second_section = (
        Block("block-000003", BlockKind.PARAGRAPH, "Third block"),
    )
    return Document(
        Book("Test book", None, (Section(first_section), Section(second_section)))
    )


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


def test_reconstructs_document_without_changing_block_structure() -> None:
    document = _document()
    units = (
        TranslationUnit(("block-000001", "block-000002"), 4),
        TranslationUnit(("block-000003",), 2),
    )
    results = (
        TranslationResult(
            units[0],
            "[[BLOCK_0001]]\nPrimeiro bloco\n\n[[BLOCK_0002]]\nSegundo bloco",
        ),
        TranslationResult(units[1], "[[BLOCK_0001]]\nTerceiro bloco"),
    )

    translated = reconstruct_translated_document(document, results)

    assert [block.text for block in translated.blocks] == [
        "Primeiro bloco",
        "Segundo bloco",
        "Terceiro bloco",
    ]
    assert [block.block_id for block in translated.blocks] == [
        block.block_id for block in document.blocks
    ]
    assert [len(section.blocks) for section in translated.book.sections] == [2, 1]
    assert translated.book.sections[0].blocks[0].kind is BlockKind.PARAGRAPH


@pytest.mark.parametrize(
    ("translated_text", "message"),
    (
        ("[[BLOCK_0001]]\nPrimeiro bloco", "missing block marker"),
        (
            "[[BLOCK_0001]]\nPrimeiro bloco\n[[BLOCK_0001]]\nSegundo bloco",
            "duplicated block marker",
        ),
        (
            "[[BLOCK_0002]]\nSegundo bloco\n[[BLOCK_0001]]\nPrimeiro bloco",
            "block markers are reordered",
        ),
        (
            "[[BLOCK_0001]]\nPrimeiro bloco\n[[BLOCK_9999]]\nSegundo bloco",
            "unknown block marker",
        ),
    ),
)
def test_reconstruction_rejects_invalid_markers(
    translated_text: str, message: str
) -> None:
    unit = TranslationUnit(("block-000001", "block-000002"), 4)

    with pytest.raises(ReconstructionError, match=message):
        reconstruct_translated_document(
            _document(),
            (
                TranslationResult(unit, translated_text),
                TranslationResult(
                    TranslationUnit(("block-000003",), 2),
                    "[[BLOCK_0001]]\nTerceiro bloco",
                ),
            ),
        )


def test_reconstruction_requires_exact_document_block_order() -> None:
    unit = TranslationUnit(("block-000002", "block-000001"), 4)

    with pytest.raises(ReconstructionError, match="exactly in order"):
        reconstruct_translated_document(
            _document(),
            (
                TranslationResult(
                    unit,
                    "[[BLOCK_0001]]\nSegundo bloco\n"
                    "[[BLOCK_0002]]\nPrimeiro bloco",
                ),
            ),
        )


def test_reconstruction_preserves_blank_lines_inside_blocks() -> None:
    units = (
        TranslationUnit(("block-000001", "block-000002"), 4),
        TranslationUnit(("block-000003",), 2),
    )
    results = (
        TranslationResult(
            units[0],
            "[[BLOCK_0001]]\nPrimeira linha\n\nSegunda linha\n\n"
            "[[BLOCK_0002]]\nSegundo bloco",
        ),
        TranslationResult(units[1], "[[BLOCK_0001]]\nTerceiro bloco"),
    )

    translated = reconstruct_translated_document(_document(), results)

    assert translated.blocks[0].text == "Primeira linha\n\nSegunda linha"


def test_reconstruction_accepts_crlf_around_markers() -> None:
    units = (
        TranslationUnit(("block-000001", "block-000002"), 4),
        TranslationUnit(("block-000003",), 2),
    )
    results = (
        TranslationResult(
            units[0],
            "[[BLOCK_0001]]\r\nPrimeiro bloco\r\n\r\n"
            "[[BLOCK_0002]]\r\nSegundo bloco",
        ),
        TranslationResult(units[1], "[[BLOCK_0001]]\r\nTerceiro bloco"),
    )

    translated = reconstruct_translated_document(_document(), results)

    assert [block.text for block in translated.blocks] == [
        "Primeiro bloco",
        "Segundo bloco",
        "Terceiro bloco",
    ]

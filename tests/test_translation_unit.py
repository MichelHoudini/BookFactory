import pytest

from bookfactory.core.document import Block, BlockKind, Book, Document, Section
from bookfactory.core.translation_unit import (
    TranslationUnit,
    build_translation_unit_text,
    count_words,
    generate_translation_units,
)


def _block(number: int, words: int) -> Block:
    text = " ".join(f"word-{index}" for index in range(words))
    return Block(f"block-{number:06d}", BlockKind.PARAGRAPH, text)


def _document(*sections: tuple[Block, ...]) -> Document:
    return Document(Book("Test book", None, tuple(Section(blocks) for blocks in sections)))


def test_groups_blocks_near_target_and_preserves_order() -> None:
    document = _document(
        (_block(1, 500), _block(2, 430), _block(3, 300), _block(4, 400), _block(5, 250))
    )

    units = generate_translation_units(document)

    assert units == (
        TranslationUnit(("block-000001", "block-000002"), 930),
        TranslationUnit(("block-000003", "block-000004", "block-000005"), 950),
    )


def test_uses_lower_boundary_when_distances_are_equal() -> None:
    document = _document((_block(1, 700), _block(2, 400)))

    units = generate_translation_units(document)

    assert units == (
        TranslationUnit(("block-000001",), 700),
        TranslationUnit(("block-000002",), 400),
    )


def test_keeps_oversized_block_in_its_own_unit() -> None:
    document = _document((_block(1, 1_100), _block(2, 200), _block(3, 300)))

    units = generate_translation_units(document)

    assert units == (
        TranslationUnit(("block-000001",), 1_100),
        TranslationUnit(("block-000002", "block-000003"), 500),
    )


def test_preserves_order_across_sections() -> None:
    document = _document((_block(1, 600),), (_block(2, 350), _block(3, 900)))

    units = generate_translation_units(document)

    block_ids = tuple(block_id for unit in units for block_id in unit.block_ids)
    assert block_ids == ("block-000001", "block-000002", "block-000003")


def test_empty_document_produces_no_units() -> None:
    assert generate_translation_units(_document(())) == ()


def test_rejects_non_positive_target() -> None:
    with pytest.raises(ValueError, match="target_word_count must be positive"):
        generate_translation_units(_document((_block(1, 1),)), target_word_count=0)


def test_counts_whitespace_separated_words() -> None:
    assert count_words(" one\n two\tthree ") == 3


def test_builds_translation_text_in_unit_order() -> None:
    document = _document((_block(1, 2), _block(2, 3), _block(3, 1)))
    unit = TranslationUnit(("block-000003", "block-000001"), 3)

    text = build_translation_unit_text(document, unit)

    assert text == "word-0\n\nword-0 word-1"


def test_rejects_translation_unit_with_unknown_block() -> None:
    document = _document((_block(1, 1),))
    unit = TranslationUnit(("block-missing",), 1)

    with pytest.raises(ValueError, match="unknown block 'block-missing'"):
        build_translation_unit_text(document, unit)

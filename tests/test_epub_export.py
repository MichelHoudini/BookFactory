from pathlib import Path

import pytest

from bookfactory.adapters.epub_export import EpubExportError, write_epub
from bookfactory.adapters.epub_ingest import read_epub
from bookfactory.core.document import Block, BlockKind, Book, Document, Section


def _document() -> Document:
    sections = (
        Section(
            (
                Block("block-000001", BlockKind.HEADING, "First <chapter>", 1),
                Block("block-000002", BlockKind.PARAGRAPH, "Text & details."),
            )
        ),
        Section(()),
        Section(
            (
                Block("block-000003", BlockKind.HEADING, "Second chapter", 2),
                Block("block-000004", BlockKind.PARAGRAPH, "More text."),
            )
        ),
    )
    return Document(Book("Exported Book", "Test Author", sections))


def test_exports_valid_epub_from_canonical_document(tmp_path: Path) -> None:
    output_path = tmp_path / "book.epub"

    write_epub(_document(), output_path)
    exported = read_epub(output_path)

    assert exported.book.title == "Exported Book"
    assert exported.book.author == "Test Author"
    assert len(exported.book.sections) == 2
    assert [block.text for block in exported.blocks] == [
        "First <chapter>",
        "Text & details.",
        "Second chapter",
        "More text.",
    ]
    assert [block.heading_level for block in exported.blocks] == [1, None, 2, None]


def test_rejects_document_without_exportable_blocks(tmp_path: Path) -> None:
    document = Document(Book("Empty", None, (Section(()),)))

    with pytest.raises(EpubExportError, match="no exportable blocks"):
        write_epub(document, tmp_path / "empty.epub")


def test_rejects_non_epub_output_path(tmp_path: Path) -> None:
    with pytest.raises(EpubExportError, match="expected an EPUB output path"):
        write_epub(_document(), tmp_path / "book.html")

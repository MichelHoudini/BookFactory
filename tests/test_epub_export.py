from pathlib import Path
from zipfile import ZipFile

import pytest
from ebooklib import epub  # type: ignore[import-untyped]

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

    with ZipFile(output_path) as archive:
        nav = archive.read("EPUB/nav.xhtml").decode("utf-8")
        first_chapter = archive.read("EPUB/section-0001.xhtml").decode("utf-8")
        package = archive.read("EPUB/content.opf").decode("utf-8")
    assert "First &lt;chapter&gt;" in nav
    assert "Second chapter" in nav
    assert "<title>First &lt;chapter&gt;</title>" in first_chapter
    assert 'version="3.0"' in package


def test_preserves_source_language_and_metadata(tmp_path: Path) -> None:
    source_path = tmp_path / "source.epub"
    output_path = tmp_path / "copy.epub"
    source = epub.EpubBook()
    source.set_identifier("original-id")
    source.set_title("Exported Book")
    source.set_language("en-US")
    source.add_author("Test Author")
    source.add_metadata("DC", "publisher", "Original Publisher")
    source_chapter = epub.EpubHtml(title="Source", file_name="source.xhtml")
    source_chapter.content = "<h1>Source</h1>"
    source.add_item(source_chapter)
    source.add_item(epub.EpubNav())
    source.spine = ["nav", source_chapter]
    epub.write_epub(str(source_path), source)

    write_epub(_document(), output_path, source_epub=source_path)
    exported = epub.read_epub(str(output_path))

    assert exported.get_metadata("DC", "language")[0][0] == "en-US"
    assert exported.get_metadata("DC", "identifier")[0][0] == "original-id"
    assert exported.get_metadata("DC", "publisher")[0][0] == "Original Publisher"


def test_sets_brazilian_portuguese_for_translated_book(tmp_path: Path) -> None:
    output_path = tmp_path / "translated.epub"

    write_epub(_document(), output_path, language="pt-BR")
    exported = epub.read_epub(str(output_path))

    assert exported.get_metadata("DC", "language")[0][0] == "pt-BR"


def test_rejects_document_without_exportable_blocks(tmp_path: Path) -> None:
    document = Document(Book("Empty", None, (Section(()),)))

    with pytest.raises(EpubExportError, match="no exportable blocks"):
        write_epub(document, tmp_path / "empty.epub")


def test_rejects_non_epub_output_path(tmp_path: Path) -> None:
    with pytest.raises(EpubExportError, match="expected an EPUB output path"):
        write_epub(_document(), tmp_path / "book.html")

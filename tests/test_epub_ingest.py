from pathlib import Path

import pytest
from ebooklib import epub  # type: ignore[import-untyped]

from bookfactory.adapters.epub_ingest import EpubIngestError, read_epub
from bookfactory.core.document import BlockKind


def _write_epub(path: Path) -> None:
    book = epub.EpubBook()
    book.set_identifier("test-book")
    book.set_title("Spine Order")
    book.set_language("en")
    book.add_author("Test Author")

    first = epub.EpubHtml(title="First", file_name="first.xhtml", lang="en")
    first.content = "<h1>First chapter</h1><p>First paragraph.</p>"
    empty = epub.EpubHtml(title="Empty", file_name="empty.xhtml", lang="en")
    empty.content = "<div>No translatable blocks</div>"
    second = epub.EpubHtml(title="Second", file_name="second.xhtml", lang="en")
    second.content = "<h2>Second chapter</h2><p>Second paragraph.</p>"

    for chapter in (first, empty, second):
        book.add_item(chapter)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", second, empty, first]
    epub.write_epub(str(path), book)


def test_reads_epub_metadata_and_spine_documents(tmp_path: Path) -> None:
    epub_path = tmp_path / "book.epub"
    _write_epub(epub_path)

    document = read_epub(epub_path)

    assert document.book.title == "Spine Order"
    assert document.book.author == "Test Author"
    assert len(document.book.sections) == 2
    assert [block.text for block in document.blocks] == [
        "Second chapter",
        "Second paragraph.",
        "First chapter",
        "First paragraph.",
    ]
    assert [block.block_id for block in document.blocks] == [
        "block-000001",
        "block-000002",
        "block-000003",
        "block-000004",
    ]
    assert document.blocks[0].kind is BlockKind.HEADING
    assert document.blocks[0].heading_level == 2


def test_rejects_invalid_epub(tmp_path: Path) -> None:
    epub_path = tmp_path / "invalid.epub"
    epub_path.write_text("not an EPUB", encoding="utf-8")

    with pytest.raises(EpubIngestError, match="could not read"):
        read_epub(epub_path)


def test_rejects_non_epub_extension(tmp_path: Path) -> None:
    with pytest.raises(EpubIngestError, match="expected an EPUB file"):
        read_epub(tmp_path / "book.html")

from pathlib import Path

from bookfactory.adapters.html_ingest import parse_html, read_html
from bookfactory.core.document import BlockKind

FIXTURE = Path(__file__).parent / "fixtures" / "book.html"


def test_reads_metadata_and_blocks_in_document_order() -> None:
    document = read_html(FIXTURE)

    assert document.book.title == "City of the Dog"
    assert document.book.author == "John Langan"
    assert [block.kind for block in document.blocks] == [
        BlockKind.HEADING,
        BlockKind.PARAGRAPH,
        BlockKind.HEADING,
        BlockKind.PARAGRAPH,
    ]
    assert [block.block_id for block in document.blocks] == [
        "block-000001",
        "block-000002",
        "block-000003",
        "block-000004",
    ]
    assert document.blocks[1].text == "The first paragraph contains inline text."
    assert document.blocks[2].heading_level == 2


def test_uses_first_heading_when_title_and_author_are_absent() -> None:
    document = parse_html("<h1>Fallback title</h1><p>Body</p>", "book")

    assert document.book.title == "Fallback title"
    assert document.book.author is None


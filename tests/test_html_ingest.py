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


def test_parses_div_based_xhtml_without_duplicate_wrapper_text() -> None:
    source = """
        <h2>Existing heading</h2>
        <div class="heading_s1s">Div <span>chapter</span> title</div>
        <div class="class_s2z">Text with <span>inline</span> content.</div>
        <div class="wrapper"><div class="class_s2x">Nested text.</div></div>
        <div><img src="cover.jpg"><svg><title>Cover image</title></svg></div>
        <div>   </div>
        <p>Existing paragraph.</p>
    """

    document = parse_html(source, "book")

    assert [block.text for block in document.blocks] == [
        "Existing heading",
        "Div chapter title",
        "Text with inline content.",
        "Nested text.",
        "Existing paragraph.",
    ]
    assert [block.kind for block in document.blocks] == [
        BlockKind.HEADING,
        BlockKind.HEADING,
        BlockKind.PARAGRAPH,
        BlockKind.PARAGRAPH,
        BlockKind.PARAGRAPH,
    ]
    assert [block.heading_level for block in document.blocks] == [
        2,
        1,
        None,
        None,
        None,
    ]


def test_div_heading_class_words_are_case_insensitive() -> None:
    for class_name in ("HEADING_s1s", "book-title", "ChApTeR_1", "part one"):
        document = parse_html(
            f'<div class="{class_name}">A heading</div>', "book"
        )

        assert document.blocks[0].kind is BlockKind.HEADING


def test_div_heading_class_requires_a_complete_word() -> None:
    document = parse_html('<div class="partial">A paragraph</div>', "book")

    assert document.blocks[0].kind is BlockKind.PARAGRAPH

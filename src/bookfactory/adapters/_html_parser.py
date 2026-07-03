from __future__ import annotations

from html.parser import HTMLParser
from typing import Final

from bookfactory.core.document import Block, BlockKind, Book, Document, Section

_BLOCK_TAGS: Final[frozenset[str]] = frozenset(
    {"p", "h1", "h2", "h3", "h4", "h5", "h6"}
)


class _DocumentParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.author: str | None = None
        self.blocks: list[tuple[str, str]] = []
        self._in_title = False
        self._block_tag: str | None = None
        self._block_parts: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        tag = tag.lower()
        if tag == "title":
            self._in_title = True
        elif tag == "meta":
            self._read_author(attrs)
        elif tag in _BLOCK_TAGS and self._block_tag is None:
            self._block_tag = tag
            self._block_parts = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "title":
            self._in_title = False
        elif tag == self._block_tag:
            text = _normalize_text("".join(self._block_parts))
            if text:
                self.blocks.append((tag, text))
            self._block_tag = None
            self._block_parts = []

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_parts.append(data)
        if self._block_tag is not None:
            self._block_parts.append(data)

    def _read_author(self, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {name.lower(): value for name, value in attrs}
        name = (attributes.get("name") or "").casefold()
        content = attributes.get("content")
        if self.author is None and name == "author" and content:
            self.author = _normalize_text(content)


def parse_html_document(
    source: str,
    fallback_title: str,
    block_id_start: int = 1,
) -> Document:
    parser = _DocumentParser()
    parser.feed(source)
    parser.close()

    blocks = _build_blocks(parser, block_id_start)
    title = _normalize_text("".join(parser.title_parts))
    if not title:
        title = next(
            (block.text for block in blocks if block.kind is BlockKind.HEADING),
            fallback_title,
        )
    book = Book(title=title, author=parser.author, sections=(Section(blocks),))
    return Document(book=book)


def _normalize_text(value: str) -> str:
    return " ".join(value.split())


def _build_blocks(
    parsed: _DocumentParser, block_id_start: int
) -> tuple[Block, ...]:
    blocks: list[Block] = []
    for index, (tag, text) in enumerate(parsed.blocks, start=block_id_start):
        kind = BlockKind.PARAGRAPH if tag == "p" else BlockKind.HEADING
        level = int(tag[1]) if kind is BlockKind.HEADING else None
        blocks.append(Block(f"block-{index:06d}", kind, text, level))
    return tuple(blocks)


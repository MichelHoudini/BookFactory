from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Final

from bookfactory.core.document import Block, BlockKind, Book, Document, Section

_BLOCK_TAGS: Final[frozenset[str]] = frozenset(
    {"div", "p", "h1", "h2", "h3", "h4", "h5", "h6"}
)
_HIDDEN_CONTENT_TAGS: Final[frozenset[str]] = frozenset(
    {"noscript", "script", "style", "svg", "template"}
)
_HEADING_CLASS_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?:^|[^a-z])(heading|title|chapter|part)(?:$|[^a-z])",
    re.IGNORECASE,
)


@dataclass(slots=True)
class _BlockContext:
    tag: str
    class_name: str
    parts: list[str] = field(default_factory=list)
    has_block_descendant: bool = False


class _DocumentParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.author: str | None = None
        self.blocks: list[tuple[str, str]] = []
        self._in_title = False
        self._hidden_depth = 0
        self._block_stack: list[_BlockContext] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        tag = tag.lower()
        if tag == "title":
            self._in_title = True
        elif tag == "meta":
            self._read_author(attrs)
        if tag in _HIDDEN_CONTENT_TAGS:
            self._hidden_depth += 1
        elif tag in _BLOCK_TAGS:
            for context in self._block_stack:
                context.has_block_descendant = True
            attributes = {name.lower(): value or "" for name, value in attrs}
            self._block_stack.append(
                _BlockContext(tag, attributes.get("class", ""))
            )

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "title":
            self._in_title = False
        if tag in _HIDDEN_CONTENT_TAGS:
            self._hidden_depth = max(0, self._hidden_depth - 1)
        elif self._block_stack and tag == self._block_stack[-1].tag:
            context = self._block_stack.pop()
            text = _normalize_text("".join(context.parts))
            if text and not context.has_block_descendant:
                self.blocks.append((_output_tag(context), text))

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_parts.append(data)
        if self._hidden_depth == 0:
            for context in self._block_stack:
                context.parts.append(data)

    def _read_author(self, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {name.lower(): value for name, value in attrs}
        name = (attributes.get("name") or "").casefold()
        content = attributes.get("content")
        if self.author is None and name == "author" and content:
            self.author = _normalize_text(content)


def _output_tag(context: _BlockContext) -> str:
    if context.tag != "div":
        return context.tag
    if _HEADING_CLASS_PATTERN.search(context.class_name):
        return "h1"
    return "p"


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

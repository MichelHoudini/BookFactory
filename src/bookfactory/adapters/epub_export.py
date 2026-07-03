from __future__ import annotations

from hashlib import sha256
from html import escape
from pathlib import Path

from ebooklib import epub  # type: ignore[import-untyped]

from bookfactory.core.document import Block, BlockKind, Document, Section


class EpubExportError(ValueError):
    """Raised when a canonical Document cannot be exported as EPUB."""


def write_epub(document: Document, path: Path) -> None:
    if path.suffix.casefold() != ".epub":
        raise EpubExportError(f"expected an EPUB output path: {path}")

    sections = tuple(section for section in document.book.sections if section.blocks)
    if not sections:
        raise EpubExportError("document contains no exportable blocks")

    book = epub.EpubBook()
    book.set_identifier(_document_identifier(document))
    book.set_title(document.book.title)
    book.set_language("und")
    if document.book.author:
        book.add_author(document.book.author)

    chapters: list[object] = []
    for index, section in enumerate(sections, start=1):
        chapter = epub.EpubHtml(
            title=f"Section {index}",
            file_name=f"section-{index:04d}.xhtml",
            lang="und",
        )
        chapter.content = _render_section(section)
        book.add_item(chapter)
        chapters.append(chapter)

    book.toc = tuple(chapters)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", *chapters]

    try:
        epub.write_epub(str(path), book)
    except (OSError, epub.EpubException) as error:
        raise EpubExportError(f"could not write {path}: {error}") from error


def _render_section(section: Section) -> str:
    return "".join(_render_block(block) for block in section.blocks)


def _render_block(block: Block) -> str:
    text = escape(block.text, quote=False)
    if block.kind is BlockKind.HEADING:
        level = block.heading_level or 1
        return f"<h{level}>{text}</h{level}>"
    return f"<p>{text}</p>"


def _document_identifier(document: Document) -> str:
    values = [document.book.title, document.book.author or ""]
    values.extend(
        f"{block.block_id}\0{block.kind}\0{block.heading_level}\0{block.text}"
        for block in document.blocks
    )
    digest = sha256("\0".join(values).encode("utf-8")).hexdigest()
    return f"urn:bookfactory:{digest}"

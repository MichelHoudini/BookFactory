from __future__ import annotations

from hashlib import sha256
from html import escape
from pathlib import Path
from typing import Any
from zipfile import BadZipFile

from ebooklib import epub  # type: ignore[import-untyped]

from bookfactory.core.document import Block, BlockKind, Document, Section


class EpubExportError(ValueError):
    """Raised when a canonical Document cannot be exported as EPUB."""


def write_epub(
    document: Document,
    path: Path,
    *,
    language: str | None = None,
    source_epub: Path | None = None,
) -> None:
    if path.suffix.casefold() != ".epub":
        raise EpubExportError(f"expected an EPUB output path: {path}")

    sections = tuple(section for section in document.book.sections if section.blocks)
    if not sections:
        raise EpubExportError("document contains no exportable blocks")

    source_book = _read_source_epub(source_epub) if source_epub else None
    book = _build_book(document, source_book, language)
    chapter_language = _first_metadata(book, "language") or "und"

    chapters: list[object] = []
    for index, section in enumerate(sections, start=1):
        section_title = _section_title(section, index)
        chapter = epub.EpubHtml(
            title=section_title,
            file_name=f"section-{index:04d}.xhtml",
            lang=chapter_language,
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


def _read_source_epub(path: Path) -> Any:
    if path.suffix.casefold() != ".epub":
        raise EpubExportError(f"expected a source EPUB path: {path}")
    try:
        return epub.read_epub(str(path))
    except (BadZipFile, OSError, UnicodeError, epub.EpubException) as error:
        raise EpubExportError(f"could not read source EPUB {path}: {error}") from error


def _build_book(
    document: Document, source_book: Any | None, language: str | None
) -> Any:
    book = epub.EpubBook()
    preserve_title = bool(
        source_book
        and _first_metadata(source_book, "title") == document.book.title
    )
    preserve_author = bool(
        source_book
        and _first_metadata(source_book, "creator") == document.book.author
    )
    if source_book is not None:
        preserved_fields = {
            name
            for name, preserve in (
                ("title", preserve_title),
                ("creator", preserve_author),
            )
            if preserve
        }
        _copy_metadata(source_book, book, preserved_fields)
        book.direction = source_book.direction

    identifier = (
        _first_metadata(source_book, "identifier") if source_book else None
    ) or _document_identifier(document)
    book.set_identifier(identifier)
    if not preserve_title:
        book.set_title(document.book.title)
    book.set_language(
        language
        or (_first_metadata(source_book, "language") if source_book else None)
        or "und"
    )
    if document.book.author and not preserve_author:
        book.add_author(document.book.author)
    return book


def _copy_metadata(
    source_book: Any,
    destination_book: Any,
    preserved_dc_fields: set[str],
) -> None:
    excluded_dc_fields = {"identifier", "language", "creator", "title"} - preserved_dc_fields
    destination_book.namespaces.update(source_book.namespaces)
    destination_book.prefixes.extend(
        prefix for prefix in source_book.prefixes if prefix not in destination_book.prefixes
    )
    for namespace, fields in source_book.metadata.items():
        for name, values in fields.items():
            if namespace == epub.NAMESPACES["DC"] and name in excluded_dc_fields:
                continue
            if namespace == epub.NAMESPACES["OPF"] and name == "generator":
                continue
            for value, attributes in values:
                destination_book.add_metadata(
                    namespace, name, value, dict(attributes or {})
                )


def _first_metadata(book: Any, name: str) -> str | None:
    values = book.get_metadata("DC", name)
    if not values:
        return None
    value = values[0][0].strip()
    return value or None


def _section_title(section: Section, index: int) -> str:
    heading = next(
        (block.text for block in section.blocks if block.kind is BlockKind.HEADING),
        None,
    )
    return heading or f"Section {index}"


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

from __future__ import annotations

from pathlib import Path
from typing import Protocol, cast
from zipfile import BadZipFile

from ebooklib import ITEM_DOCUMENT, epub  # type: ignore[import-untyped]

from bookfactory.adapters._html_parser import parse_html_document
from bookfactory.core.document import Book, Document, Section


class EpubIngestError(ValueError):
    """Raised when an EPUB document cannot be ingested."""


class _EpubItem(Protocol):
    def get_type(self) -> int: ...

    def get_content(self) -> bytes: ...


class _EpubBook(Protocol):
    spine: list[tuple[str, str | None]]

    def get_item_with_id(self, item_id: str) -> _EpubItem | None: ...

    def get_metadata(
        self, namespace: str, name: str
    ) -> list[tuple[str, dict[str, str]]]: ...


def read_epub(path: Path) -> Document:
    if path.suffix.casefold() != ".epub":
        raise EpubIngestError(f"expected an EPUB file: {path}")
    try:
        book = cast(_EpubBook, epub.read_epub(str(path)))
        return _build_document(book, path.stem)
    except (BadZipFile, OSError, UnicodeError, epub.EpubException) as error:
        raise EpubIngestError(f"could not read {path}: {error}") from error


def _build_document(book: _EpubBook, fallback_title: str) -> Document:
    sections: list[Section] = []
    next_block_index = 1

    for item_id, _linear in book.spine:
        item = book.get_item_with_id(item_id)
        if (
            item is None
            or item.get_type() != ITEM_DOCUMENT
            or isinstance(item, epub.EpubNav)
        ):
            continue
        chapter = parse_html_document(
            item.get_content().decode("utf-8-sig"),
            fallback_title,
            block_id_start=next_block_index,
        )
        if not chapter.blocks:
            continue
        sections.append(Section(chapter.blocks))
        next_block_index += len(chapter.blocks)

    title = _first_metadata(book, "title") or fallback_title
    author = _first_metadata(book, "creator")
    return Document(Book(title=title, author=author, sections=tuple(sections)))


def _first_metadata(book: _EpubBook, name: str) -> str | None:
    values = book.get_metadata("DC", name)
    if not values:
        return None
    value = values[0][0].strip()
    return value or None

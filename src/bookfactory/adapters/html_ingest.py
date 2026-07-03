from __future__ import annotations

from pathlib import Path

from bookfactory.adapters._html_parser import parse_html_document
from bookfactory.core.document import Document


class HtmlIngestError(ValueError):
    """Raised when an HTML document cannot be ingested."""


def parse_html(source: str, fallback_title: str) -> Document:
    return parse_html_document(source, fallback_title)


def read_html(path: Path) -> Document:
    if path.suffix.casefold() not in {".html", ".htm"}:
        raise HtmlIngestError(f"expected an HTML file: {path}")
    try:
        source = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as error:
        raise HtmlIngestError(f"could not read {path}: {error}") from error
    return parse_html(source, fallback_title=path.stem)

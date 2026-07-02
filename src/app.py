from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from bookfactory.adapters.html_ingest import HtmlIngestError, read_html
from bookfactory.core.document import BlockKind, Document


def format_summary(document: Document) -> str:
    headings = document.count_blocks(BlockKind.HEADING)
    paragraphs = document.count_blocks(BlockKind.PARAGRAPH)
    author = document.book.author or "Not provided"
    return "\n".join(
        (
            "Book Factory",
            "",
            "Book:",
            document.book.title,
            "",
            "Author:",
            author,
            "",
            "Headings:",
            str(headings),
            "",
            "Paragraphs:",
            str(paragraphs),
            "",
            "Status:",
            "Ready",
        )
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read an HTML document into the Book Factory document model."
    )
    parser.add_argument("html_file", type=Path, help="Path to the HTML document")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        document = read_html(args.html_file)
    except HtmlIngestError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print(format_summary(document))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


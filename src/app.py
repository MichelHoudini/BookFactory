from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from bookfactory.adapters.openai_client import OpenAIClient
from bookfactory.adapters.html_ingest import HtmlIngestError, read_html
from bookfactory.config.settings import Settings, SettingsError
from bookfactory.core.document import BlockKind, Document
from bookfactory.core.llm_client import LLMClientError
from bookfactory.core.translation import TranslationResult, translate_document
from bookfactory.core.translation_unit import generate_translation_units
from bookfactory.prompts.registry import PromptNotFoundError, PromptRegistry

PROMPT_DIRECTORY = Path(__file__).resolve().parent.parent / "prompts"


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


def format_translations(results: tuple[TranslationResult, ...]) -> str:
    units = (
        f"Unit {index}:\n{result.translated_text}"
        for index, result in enumerate(results, start=1)
    )
    return "\n\n".join(units)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        document = read_html(args.html_file)
        units = generate_translation_units(document)
        if not units:
            print("Error: document contains no translatable blocks", file=sys.stderr)
            return 1

        instructions = PromptRegistry(PROMPT_DIRECTORY).load("translate")
        settings = Settings.from_environment()
        client = OpenAIClient(settings)
        translations = translate_document(document, units, instructions, client)
    except (HtmlIngestError, PromptNotFoundError, SettingsError, LLMClientError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print(format_summary(document))
    print(f"\nTranslations:\n{format_translations(translations)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from pathlib import Path
from unittest.mock import call, patch

import pytest

from app import format_summary, main
from bookfactory.adapters.html_ingest import read_html
from bookfactory.core.translation_unit import TranslationUnit

FIXTURE = Path(__file__).parent / "fixtures" / "book.html"


def test_formats_readable_summary() -> None:
    output = format_summary(read_html(FIXTURE))

    assert "Book:\nCity of the Dog" in output
    assert "Author:\nJohn Langan" in output
    assert "Headings:\n2" in output
    assert "Paragraphs:\n2" in output
    assert "Status:\nReady" in output


def test_translates_every_unit_and_loads_prompt_once(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    units = (
        TranslationUnit(("block-000001", "block-000002"), 9),
        TranslationUnit(("block-000003", "block-000004"), 8),
    )

    with (
        patch("app.generate_translation_units", return_value=units),
        patch("app.PromptRegistry") as registry_type,
        patch("app.OpenAIClient") as client_type,
    ):
        registry_type.return_value.load.return_value = "Shared instructions"
        client_type.return_value.generate.side_effect = [
            "Primeira tradução",
            "Segunda tradução",
        ]
        exit_code = main([str(FIXTURE)])

    assert exit_code == 0
    registry_type.return_value.load.assert_called_once_with("translate")
    assert client_type.return_value.generate.call_args_list == [
        call(
            "Shared instructions",
            "[[BLOCK_0001]]\nCity of the Dog\n\n"
            "[[BLOCK_0002]]\nThe first paragraph contains inline text.",
        ),
        call(
            "Shared instructions",
            "[[BLOCK_0001]]\nPart One\n\n"
            "[[BLOCK_0002]]\nThe second paragraph follows the second heading.",
        ),
    ]
    output = capsys.readouterr().out
    assert "Unit 1:\nPrimeira tradução" in output
    assert "Unit 2:\nSegunda tradução" in output
    assert output.index("Primeira tradução") < output.index("Segunda tradução")


def test_translates_reconstructs_and_exports_epub(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    document = read_html(FIXTURE)
    units = (
        TranslationUnit(("block-000001", "block-000002"), 9),
        TranslationUnit(("block-000003", "block-000004"), 8),
    )

    with (
        patch("app.read_epub", return_value=document),
        patch("app.generate_translation_units", return_value=units),
        patch("app.PromptRegistry") as registry_type,
        patch("app.OpenAIClient") as client_type,
        patch("app.write_epub") as write_epub,
    ):
        registry_type.return_value.load.return_value = "Shared instructions"
        client_type.return_value.generate.side_effect = [
            "[[BLOCK_0001]]\nCidade do Cão\n\n"
            "[[BLOCK_0002]]\nO primeiro parágrafo.",
            "[[BLOCK_0001]]\nParte Um\n\n"
            "[[BLOCK_0002]]\nO segundo parágrafo.",
        ]

        exit_code = main(["book.epub"])

    assert exit_code == 0
    translated_document, output_path = write_epub.call_args.args
    assert output_path == Path("translated.epub")
    assert write_epub.call_args.kwargs == {
        "language": "pt-BR",
        "source_epub": Path("book.epub"),
    }
    assert [block.text for block in translated_document.blocks] == [
        "Cidade do Cão",
        "O primeiro parágrafo.",
        "Parte Um",
        "O segundo parágrafo.",
    ]
    assert "Output:\ntranslated.epub" in capsys.readouterr().out


def test_does_not_export_epub_when_reconstruction_is_ambiguous(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    document = read_html(FIXTURE)
    units = (TranslationUnit(tuple(block.block_id for block in document.blocks), 17),)

    with (
        patch("app.read_epub", return_value=document),
        patch("app.generate_translation_units", return_value=units),
        patch("app.PromptRegistry") as registry_type,
        patch("app.OpenAIClient") as client_type,
        patch("app.write_epub") as write_epub,
    ):
        registry_type.return_value.load.return_value = "Shared instructions"
        client_type.return_value.generate.return_value = "Merged translation"

        exit_code = main(["book.epub"])

    assert exit_code == 1
    write_epub.assert_not_called()
    error = capsys.readouterr().err
    assert "missing block marker: [[BLOCK_0001]]" in error

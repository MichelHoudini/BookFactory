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
            "City of the Dog\n\nThe first paragraph contains inline text.",
        ),
        call(
            "Shared instructions",
            "Part One\n\nThe second paragraph follows the second heading.",
        ),
    ]
    output = capsys.readouterr().out
    assert "Unit 1:\nPrimeira tradução" in output
    assert "Unit 2:\nSegunda tradução" in output
    assert output.index("Primeira tradução") < output.index("Segunda tradução")

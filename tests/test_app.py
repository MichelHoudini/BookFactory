from pathlib import Path

import pytest

from app import main

FIXTURE = Path(__file__).parent / "fixtures" / "book.html"


def test_prints_readable_summary(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main([str(FIXTURE)])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "Book:\nCity of the Dog" in output
    assert "Author:\nJohn Langan" in output
    assert "Headings:\n2" in output
    assert "Paragraphs:\n2" in output
    assert "Status:\nReady" in output


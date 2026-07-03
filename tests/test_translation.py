from bookfactory.core.document import Block, BlockKind, Book, Document, Section
from bookfactory.core.llm_client import LLMClient
from bookfactory.core.translation import TranslationResult, translate_document
from bookfactory.core.translation_unit import TranslationUnit


class FakeLLMClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def generate(self, instructions: str, user_input: str) -> str:
        self.calls.append((instructions, user_input))
        return f"translated-{len(self.calls)}"


def _document() -> Document:
    blocks = (
        Block("block-000001", BlockKind.PARAGRAPH, "First block"),
        Block("block-000002", BlockKind.PARAGRAPH, "Second block"),
        Block("block-000003", BlockKind.PARAGRAPH, "Third block"),
    )
    return Document(Book("Test book", None, (Section(blocks),)))


def test_translates_every_unit_in_order() -> None:
    units = (
        TranslationUnit(("block-000001", "block-000002"), 4),
        TranslationUnit(("block-000003",), 2),
    )
    client = FakeLLMClient()
    llm_client: LLMClient = client

    results = translate_document(_document(), units, "Shared instructions", llm_client)

    assert results == (
        TranslationResult(units[0], "translated-1"),
        TranslationResult(units[1], "translated-2"),
    )
    assert results[0].translation_unit is units[0]
    assert client.calls == [
        ("Shared instructions", "First block\n\nSecond block"),
        ("Shared instructions", "Third block"),
    ]

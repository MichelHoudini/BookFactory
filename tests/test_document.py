import pytest

from bookfactory.core.document import Block, BlockKind


def test_heading_requires_a_valid_level() -> None:
    with pytest.raises(ValueError, match="level from 1 to 6"):
        Block("block-000001", BlockKind.HEADING, "Heading", heading_level=7)


def test_paragraph_rejects_a_heading_level() -> None:
    with pytest.raises(ValueError, match="cannot have a heading level"):
        Block("block-000001", BlockKind.PARAGRAPH, "Paragraph", heading_level=1)


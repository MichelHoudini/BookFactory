from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class BlockKind(StrEnum):
    HEADING = "heading"
    PARAGRAPH = "paragraph"


@dataclass(frozen=True, slots=True)
class Block:
    block_id: str
    kind: BlockKind
    text: str
    heading_level: int | None = None

    def __post_init__(self) -> None:
        if not self.block_id:
            raise ValueError("block_id must not be empty")
        if not self.text:
            raise ValueError("block text must not be empty")
        if self.kind is BlockKind.HEADING:
            if self.heading_level not in range(1, 7):
                raise ValueError("heading blocks require a level from 1 to 6")
        elif self.heading_level is not None:
            raise ValueError("paragraph blocks cannot have a heading level")


@dataclass(frozen=True, slots=True)
class Section:
    blocks: tuple[Block, ...]


@dataclass(frozen=True, slots=True)
class Book:
    title: str
    author: str | None
    sections: tuple[Section, ...]

    def __post_init__(self) -> None:
        if not self.title:
            raise ValueError("book title must not be empty")


@dataclass(frozen=True, slots=True)
class Document:
    book: Book

    @property
    def blocks(self) -> tuple[Block, ...]:
        return tuple(block for section in self.book.sections for block in section.blocks)

    def count_blocks(self, kind: BlockKind) -> int:
        return sum(block.kind is kind for block in self.blocks)


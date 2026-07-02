from __future__ import annotations

from dataclasses import dataclass

from bookfactory.core.document import Block, Document

DEFAULT_TARGET_WORD_COUNT = 900


@dataclass(frozen=True, slots=True)
class TranslationUnit:
    block_ids: tuple[str, ...]
    estimated_word_count: int

    def __post_init__(self) -> None:
        if not self.block_ids:
            raise ValueError("a translation unit must contain at least one block")
        if self.estimated_word_count < 1:
            raise ValueError("estimated_word_count must be positive")


def count_words(text: str) -> int:
    return len(text.split())


def _create_unit(blocks: list[Block], estimated_word_count: int) -> TranslationUnit:
    return TranslationUnit(
        block_ids=tuple(block.block_id for block in blocks),
        estimated_word_count=estimated_word_count,
    )


def generate_translation_units(
    document: Document,
    target_word_count: int = DEFAULT_TARGET_WORD_COUNT,
) -> tuple[TranslationUnit, ...]:
    if target_word_count < 1:
        raise ValueError("target_word_count must be positive")

    units: list[TranslationUnit] = []
    pending: list[Block] = []
    pending_word_count = 0

    for block in document.blocks:
        block_word_count = count_words(block.text)
        combined_word_count = pending_word_count + block_word_count
        if pending and _should_close_before(combined_word_count, pending_word_count, target_word_count):
            units.append(_create_unit(pending, pending_word_count))
            pending = []
            pending_word_count = 0

        pending.append(block)
        pending_word_count += block_word_count
        if pending_word_count >= target_word_count:
            units.append(_create_unit(pending, pending_word_count))
            pending = []
            pending_word_count = 0

    if pending:
        units.append(_create_unit(pending, pending_word_count))
    return tuple(units)


def _should_close_before(combined: int, current: int, target: int) -> bool:
    if combined <= target:
        return False
    distance_before = target - current
    distance_after = combined - target
    return distance_before <= distance_after


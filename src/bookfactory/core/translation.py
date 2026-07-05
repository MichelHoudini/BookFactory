from __future__ import annotations

import re
from dataclasses import dataclass, replace

from bookfactory.core.document import Document
from bookfactory.core.llm_client import LLMClient
from bookfactory.core.translation_unit import (
    TranslationUnit,
    build_block_marker,
    build_translation_unit_text,
)

BLOCK_MARKER_PATTERN = re.compile(
    r"^(?P<marker>\[\[BLOCK_\d{4}\]\])\r?$", re.MULTILINE
)


@dataclass(frozen=True, slots=True)
class TranslationResult:
    translation_unit: TranslationUnit
    translated_text: str


class ReconstructionError(ValueError):
    """Raised when translated units cannot be mapped exactly to source blocks."""


def translate_document(
    document: Document,
    units: tuple[TranslationUnit, ...],
    instructions: str,
    client: LLMClient,
) -> tuple[TranslationResult, ...]:
    results: list[TranslationResult] = []
    for unit in units:
        user_input = build_translation_unit_text(document, unit)
        translated_text = client.generate(instructions, user_input)
        results.append(TranslationResult(unit, translated_text))
    return tuple(results)


def reconstruct_translated_document(
    document: Document,
    results: tuple[TranslationResult, ...],
) -> Document:
    source_block_ids = tuple(block.block_id for block in document.blocks)
    translated_by_id: dict[str, str] = {}
    result_block_ids: list[str] = []

    for result in results:
        block_ids = result.translation_unit.block_ids
        translated_blocks = _parse_translated_blocks(
            result.translated_text, len(block_ids)
        )
        result_block_ids.extend(block_ids)
        translated_by_id.update(zip(block_ids, translated_blocks, strict=True))

    if tuple(result_block_ids) != source_block_ids:
        raise ReconstructionError(
            "translation results do not cover the document blocks exactly in order"
        )

    sections = tuple(
        replace(
            section,
            blocks=tuple(
                replace(block, text=translated_by_id[block.block_id])
                for block in section.blocks
            ),
        )
        for section in document.book.sections
    )
    return replace(document, book=replace(document.book, sections=sections))


def _parse_translated_blocks(text: str, expected_count: int) -> tuple[str, ...]:
    expected_markers = tuple(
        build_block_marker(index) for index in range(1, expected_count + 1)
    )
    matches = tuple(BLOCK_MARKER_PATTERN.finditer(text))
    markers = tuple(match.group("marker") for match in matches)
    _validate_markers(markers, expected_markers)

    if matches[0].start() != 0:
        raise ReconstructionError("translated text contains content before first marker")

    translated_blocks: list[str] = []
    for index, match in enumerate(matches):
        next_marker_start = (
            matches[index + 1].start() if index + 1 < len(matches) else None
        )
        block_text = text[match.end() : next_marker_start].strip("\r\n")
        if not block_text:
            raise ReconstructionError(
                f"translated block {markers[index]} must not be empty"
            )
        translated_blocks.append(block_text)
    return tuple(translated_blocks)


def _validate_markers(
    markers: tuple[str, ...], expected_markers: tuple[str, ...]
) -> None:
    unknown = tuple(marker for marker in markers if marker not in expected_markers)
    if unknown:
        raise ReconstructionError(f"unknown block marker: {unknown[0]}")

    seen: set[str] = set()
    duplicated: str | None = None
    for marker in markers:
        if marker in seen:
            duplicated = marker
            break
        seen.add(marker)
    if duplicated is not None:
        raise ReconstructionError(f"duplicated block marker: {duplicated}")

    missing = tuple(marker for marker in expected_markers if marker not in markers)
    if missing:
        raise ReconstructionError(f"missing block marker: {missing[0]}")

    if markers != expected_markers:
        raise ReconstructionError("block markers are reordered")

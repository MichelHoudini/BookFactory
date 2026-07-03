from __future__ import annotations

from dataclasses import dataclass

from bookfactory.core.document import Document
from bookfactory.core.llm_client import LLMClient
from bookfactory.core.translation_unit import (
    TranslationUnit,
    build_translation_unit_text,
)


@dataclass(frozen=True, slots=True)
class TranslationResult:
    translation_unit: TranslationUnit
    translated_text: str


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


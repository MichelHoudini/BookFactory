# Book Factory

## Philosophy

Book Factory is not a translator.

Book Factory is a document automation engine.

Every module must have only one responsibility.

The codebase must remain simple, modular and highly maintainable.

Never hardcode prompts.

Never mix UI and business logic.

Everything should be replaceable.

The translation provider must be swappable.

The software should be able to use OpenAI today and another provider tomorrow without changing the architecture.

## Goals

Input

- HTML

Future

- EPUB
- PDF
- DOCX

Output

- HTML
- EPUB

## Architecture

Input file

↓

Source / Ingest

↓

Document

↓

Pipeline stages

↓

Document

↓

Export

↓

Output artifact(s)

Transform orchestration checks the cache before calling a provider and stores results only after successful validation. Cache is not a pipeline stage.

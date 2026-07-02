# Book Factory — Architecture

This document is the single source of truth for how Book Factory is built and why it is built that way. If code and this document disagree, the code is wrong until an intentional architecture decision updates this file.

---

# Vision

## What Book Factory is

Book Factory is a **document automation engine**. It ingests structured documents, runs them through configurable **pipelines** made of replaceable **stages**, and produces **artifacts** (HTML, EPUB, JSON, and others over time).

The engine operates on a canonical internal representation of a book — the **Document** — not on raw files. Every capability (translation, summarization, glossary extraction, consistency checking, and others) is expressed as a pipeline that reads, transforms, validates, and exports Documents.

## What Book Factory is not

Book Factory is **not a translator**. Translation is the first pipeline we ship, not the product definition.

It is also not:

- A single script that calls an LLM and writes files
- An OpenAI wrapper with HTML helpers
- A desktop app or web UI (the CLI is a thin shell; business logic lives elsewhere)
- A batch file converter with AI sprinkled on top

If a feature can only be described as "call OpenAI on HTML," it does not belong in core. It belongs in a pipeline definition, a stage, or an adapter.

## Long-term philosophy

We optimize for **maintainability over speed** and **clarity over cleverness**. The codebase should still be understandable ten years from now by someone who was not in the room when decisions were made.

Every external dependency — LLM providers, parsers, filesystems, TTS engines — sits behind a **port** with a swappable **adapter**. The core domain never imports provider SDKs.

New capabilities arrive as **new pipeline definitions**, **new prompts**, and occasionally **new adapters**. They do not require rewriting the engine, the Document model, or the orchestration layer.

---

# Design Principles

These principles govern every engineering decision. When in doubt, choose the option that best preserves them.

**Simplicity.** Prefer fewer layers with clear names. Do not introduce an abstraction until two concrete use cases need it. A pipeline engine with stage kinds is enough; we do not unify ingest, export, and validation into a single "Transform" shape.

**Modularity.** One responsibility per module. Files stay under 250 lines; functions under 40. If a module grows beyond that, split it.

**Provider independence.** The core and pipeline layers never import `openai`, `anthropic`, or any other vendor SDK. Providers are selected at startup through configuration and wired in the composition root (CLI).

**Low coupling, high cohesion.** Modules communicate through port interfaces and domain types. Adapters depend on core; core never depends on adapters. Stages do not call each other directly — the engine orchestrates them.

**Maintainability.** Typed Python, structured logging, meaningful exceptions, and tests for real behavior — not ceremony. Every bug fix gets a regression test.

**Replaceability.** Readers, parsers, chunkers, transform adapters, validators, exporters, cache backends, and prompt loaders are all interchangeable without changing orchestration logic.

**Reproducibility.** Every pipeline run records a config snapshot and prompt versions. Given the same input and manifest, behavior should be explainable even when LLM output varies.

**Structure preservation.** Document hierarchy, block identity, and inline formatting survive every stage. A broken book is worse than an untranslated one.

**Contracts before code.** Define the interface first. Implement second. See `.cursor/rules/build_contract_first.mdc`.

---

# Core Domain

## Document is the center

The **Document** (canonical document model, CDM) is the central domain object. Internally it is modeled as a `Book` containing `Section`s and `Block`s, with `InlineSpan`s carrying formatting inside blocks. Every block has a stable `block_id` assigned at ingest and never changed during a run.

All meaningful processing happens on the Document:

```
Input file  →  ingest  →  Document  →  pipeline stages  →  Document  →  export  →  Output file(s)
```

**Everything starts and ends with a Document.** Ingest converts external formats into a Document. Export converts a Document into external formats. Stages in between mutate or inspect the Document — they never operate on raw HTML strings passed down a chain.

## Why not files, Assets, or translation jobs?

**Files** are I/O boundaries. A minimal **Asset** descriptor (path, media type, checksum) tracks inputs and outputs but is not the processing center. Starting from files would optimize for storage, not for document automation.

**TranslationJob** was rejected as a core concept. Jobs are **PipelineJob** instances — they schedule and track any pipeline, not only translation.

**Knowledge** (glossaries, translation memory, entity registries) is deferred. Extracted information attaches to the Document as **Annotations** in early versions and may later persist in a dedicated store when cross-run reuse is proven necessary.

## Invariants

- `block_id` is immutable for the lifetime of a pipeline job.
- Blocks are the source of truth for reassembly; chunks are disposable views created for processing.
- Annotations are additive unless a stage explicitly declares replace semantics.

---

# High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│  CLI (composition root — wires adapters, parses args, prints progress)  │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
┌─────────────────────────────────▼───────────────────────────────────────┐
│                         Pipeline Engine                                   │
│   Loads pipeline definition · Executes stages · Manages PipelineJob     │
│   Coordinates cache · Persists job state · Emits run report               │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
         ┌────────────────────────┼────────────────────────┐
         │                        │                        │
         ▼                        ▼                        ▼
┌─────────────────┐    ┌─────────────────────┐    ┌─────────────────┐
│ Pipeline        │    │      Stages         │    │  Cross-cutting  │
│ Definitions     │    │  Source             │    │  Prompt Registry│
│ (translation,   │    │  Transform          │    │  Cache          │
│  summarize, …)   │    │  Validate           │    │  Configuration  │
└─────────────────┘    │  Export             │    │  Logging        │
                       └──────────┬──────────┘    └─────────────────┘
                                  │
                       ┌──────────▼──────────┐
                       │   Port interfaces   │
                       │   (in core)         │
                       └──────────┬──────────┘
                                  │
         ┌────────────────────────┼────────────────────────┐
         ▼                        ▼                        ▼
┌─────────────────┐    ┌─────────────────────┐    ┌─────────────────┐
│ Ingest adapters │    │ Transform adapters  │    │ Export adapters │
│ HTML (v1.0)     │    │ OpenAI, Claude,     │    │ HTML, EPUB      │
│ EPUB, PDF (later)│   │ Gemini, GLM, Ollama │    │ JSON, MD (later)│
└─────────────────┘    └─────────────────────┘    └─────────────────┘

                       ┌─────────────────────┐
                       │  Document (CDM)     │  ← working state at the center
                       └─────────────────────┘

                       ┌─────────────────────┐
                       │  Assets (I/O only)  │  ← input/output descriptors
                       └─────────────────────┘
```

**Dependency rule:** dependencies point inward. `bookfactory.core` imports nothing from adapters, CLI, or provider SDKs. Only the CLI imports concrete adapters and registers them.

---

# Pipeline System

## How pipelines work

A **pipeline** is a named, ordered list of **stages** defined in configuration (e.g. `pipelines/translation.yaml`). A **PipelineJob** is one execution of that pipeline on one input.

The engine:

1. Loads configuration and creates a run manifest (config + prompt versions + input checksum).
2. Executes each stage in order, passing a **StageContext** that carries the working Document, job state, and port references.
3. For transform work, loops over chunks: cache lookup → transform on miss → validate → cache store → update block state.
4. Persists job state so interrupted runs can resume.
5. Writes a run report (JSON) with statistics, errors, and output paths.

## Stage kinds

Stages share one interface (`execute(context) → result`) but fall into distinct kinds. **Not every stage is a Transform.**

| Kind | Role | Examples |
|------|------|----------|
| **Source** | Produce the initial Document from external input | Read file, parse HTML |
| **Transform** | Mutate or enrich the Document | Translate, summarize, extract entities |
| **Validate** | Inspect output; return pass/fail | Structural checks, optional LLM quality gate |
| **Export** | Write output artifacts from the Document | HTML file, EPUB file, JSON |

Ingest is Source, not Transform. Export is Export, not Transform. Validation often does not mutate the Document at all.

## Translation is one pipeline

Translation is implemented as pipeline `translation` — a Source stage, chunking, a Transform stage calling the transform provider with `operation=translate`, validation, and export. It has no special status in the engine.

Future pipelines reuse the same engine and stage kinds:

| Pipeline | Differs from translation by… |
|----------|------------------------------|
| Summarization | Prompts, operation, export targets |
| Character extraction | Prompts, annotations on Document, JSON export |
| Glossary generation | Multi-pass transforms, annotation export |
| Consistency checking | Validate-heavy, may not transform content |
| Audiobook (future) | Additional media synthesis adapter, not a core change |

Adding a pipeline means: new definition file, new prompts, and optionally a new adapter. **No changes to the engine, Document model, or orchestration logic.**

---

# Providers

## TransformProvider

All LLM-backed text operations — translation, summarization, extraction, semantic validation — go through a single port: **TransformProvider**.

The orchestrator builds a **TransformRequest** containing:

- `operation` (e.g. `translate`, `summarize`, `extract_characters`)
- Rendered prompts from the prompt registry
- Input payload (chunk text or structured data)
- Provider descriptor (provider id, model, parameters)

The adapter returns a **TransformResult** with output text, token usage, and provider metadata. The core never sees HTTP, API keys, or vendor-specific message formats.

Translation is not a separate provider type. It is an **operation** on TransformProvider.

## Other ports (not lumped into "Provider")

Format handling and future media work use their own narrow ports:

- **Ingest** — read bytes, parse into Document
- **Export** — serialize Document to files
- **CacheProvider** — get/put by cache key
- **JobStore** — persist PipelineJob and block state
- **MediaSynthesisProvider** (future) — TTS for audiobook pipelines

Do not create one god "Provider" interface.

## Provider independence

The core must **never depend on OpenAI** or any other vendor. Concretely:

- No `import openai` outside `bookfactory.adapters.*`
- No provider-specific branching in `bookfactory.core` or `bookfactory.pipeline`
- API keys only via environment variables, loaded in the composition root
- Each adapter declares capability flags (system message support, JSON mode, context limits) so the engine can adapt behavior without knowing vendor details

Supported providers are wired through configuration (`transform.provider = openai | anthropic | google | glm | openrouter | ollama`). Adding a provider is a new adapter class and a registry entry — nothing else.

---

# Prompt System

## Philosophy

Prompts are **behavioral code**. They change more often than Python modules and must be versioned, reviewed, and tested independently.

**Prompts never belong inside application code.** No f-strings, no triple-quoted system messages in `.py` files (test fixtures excepted).

## Storage and loading

Prompts live under `prompts/` at the project or workspace level:

```
prompts/
├── manifest.yaml       # id, version, operation, file paths, status
├── translation/
│   ├── system_v1.txt
│   └── user_v1.txt
└── validation/
    └── semantic_v1.txt
```

The **PromptLoader** reads the manifest, loads templates, and renders them with declared variables (Jinja2). Pipeline config references a prompt by id and optional version pin.

## Versioning

- Never edit a published prompt version in place. Create `v2`, mark `v1` deprecated.
- Prompt content hash is part of the cache key — new version automatically misses stale cache entries.
- The run manifest records exact prompt versions for every job.

## Testing

Rendered prompts are tested with snapshot/golden files. Variable completeness is asserted at render time. LLM quality evaluation stays out of the production path.

---

# Configuration

## Layered resolution

Configuration merges from lowest to highest priority:

```
1. Built-in defaults (minimal, in code)
2. config/defaults.toml
3. config/config.toml  (user overrides; may be gitignored locally)
4. Environment variables  (BOOKFACTORY_*)
5. CLI flags
```

The resolved configuration is frozen into the run manifest at job start.

## Secrets

API keys and tokens **only** through environment variables (e.g. `BOOKFACTORY_OPENAI_API_KEY`). Never in TOML files committed to git.

## Workspace paths

All runtime paths resolve relative to a **workspace root** (`--workspace` or `BOOKFACTORY_WORKSPACE`). Default subpaths:

| Path | Contents |
|------|----------|
| `{workspace}/input/` | Source files |
| `{workspace}/output/` | Generated artifacts |
| `{workspace}/.bookfactory/cache/` | Transform cache |
| `{workspace}/.bookfactory/logs/` | JSONL log files |
| `{workspace}/.bookfactory/jobs.db` | Job state for resume |

Runtime data does not live inside `src/` or the git repository root.

## Pipeline-specific settings

Settings that apply only to one pipeline — such as source/target language for translation — belong in pipeline config sections, not in global document settings. The core Document model does not encode "this book is being translated."

## Provider selection

```toml
[transform]
provider = "openai"       # or anthropic, google, glm, openrouter, ollama
model = "gpt-4o"
operation = "translate"
temperature = 0.3
concurrency = 4

[transform.retry]
max_attempts = 3
backoff_base_seconds = 2.0
```

---

# Cache

## Philosophy

The cache exists for three reasons:

1. **Cost reduction** — never pay twice for an identical transform
2. **Speed** — re-export and prompt experiments on unchanged chunks are instant
3. **Resumability** — after a crash, cached chunks skip API calls on restart

Cache is **not a pipeline stage** that runs after translation. The orchestrator consults the cache **before** calling TransformProvider and writes to cache **after** successful validation.

## Cache keys

Keys are derived deterministically from:

```
operation
source text (normalized)
source language / target language (when applicable)
prompt content hash
provider id + model id
transform parameters that affect output
chunking policy fingerprint
```

`run_id` and file paths are excluded — same content must hit the same cache regardless of where the file lives.

## Backends

v1.0 uses a filesystem or SQLite backend behind the **CacheProvider** port. The core never reads cache files directly.

## Job store vs cache

| | Cache | Job store |
|--|-------|-----------|
| Purpose | Dedup identical transforms across runs | Track this job's progress |
| Key | Content-addressable hash | `run_id` + `block_id` |
| Shared across jobs | Yes | No |

On resume, the engine walks pending blocks, checks cache by key, and skips transform on hit.

---

# Validation

## Philosophy

Every pipeline is responsible for validating its own outputs before export. Validation is a **stage kind**, not an optional afterthought.

Two tiers:

**Structural validation (default, always on).** Deterministic checks: blocks non-empty, `block_id` mapping intact, inline spans well-formed, no orphaned content. Fast, free, non-negotiable.

**Semantic validation (optional, off in v1.0).** LLM-backed quality checks. Doubles cost and latency. Enable only when the quality gain justifies it.

Failed validation on a block triggers retry (if configured) or marks the block failed. The job continues or aborts based on `fail_fast` config.

Validation does not belong inside the transform adapter. The validator stage inspects results and returns a **ValidationResult**; the orchestrator decides what to do.

---

# Logging

## Philosophy

Logging is a production requirement, not a debug convenience.

- Use the `logging` module. No `print()` except CLI user output.
- Structured fields on every line: `run_id`, `pipeline`, `stage`, `block_id`, `chunk_index`, `provider`, `model`, `cache_hit`, `duration_ms`, token counts.
- Console handler: human-readable during development.
- File handler: JSON lines at `{workspace}/.bookfactory/logs/{run_id}.jsonl`.
- Never log API keys, secrets, or full book text at INFO level.
- End of run: emit statistics (chunks processed, cache hit rate, estimated cost, failures) to log and run report.

The CLI progress bar is driven by orchestrator events, not ad-hoc prints inside stages.

---

# Testing

## Philosophy

Tests prove behavior, not implementation details. No test should require a live API key in default CI.

## Layers

| Layer | What | Network |
|-------|------|---------|
| **Unit** | Cache key derivation, chunking, config merge, prompt rendering, domain invariants | No |
| **Golden** | HTML ingest → Document → HTML export preserves structure | No |
| **Integration** | Full pipeline with **FakeTransformProvider** (deterministic output from input hash) | No |
| **Contract** | Real adapters against recorded HTTP fixtures (VCR-style) | Mocked |
| **Provider smoke** | Live API calls | Yes — nightly or manual only |

Every bug fix includes a regression test. FakeTransformProvider is mandatory infrastructure — not an afterthought.

CI runs: linter, type checker (`mypy`), `pytest -m "not provider"`.

---

# Development Rules

Summary of non-negotiable engineering rules. Full detail lives in `.cursor/rules/`.

**Architecture**

- Never sacrifice architecture for speed
- Single responsibility per module; no god classes
- Composition over inheritance
- Business logic never depends on UI/CLI
- Prefer explicit code over magic
- When unsure, read this document before writing code

**Code quality**

- Python 3.14 target; use `pathlib`
- Type hints everywhere; dataclasses for domain objects
- Max ~40 lines per function, ~250 lines per file
- No duplicated code; no unexplained TODOs
- No global mutable state

**Boundaries**

- Design the interface before the implementation
- Core never imports adapters or provider SDKs
- Never hardcode prompts
- Never embed API keys
- Separate pure functions from I/O
- Never mix parsing, transformation, and file writing in one module

**Before marking work complete, verify:** readability, modularity, error handling, logging, documentation, typing, and future extensibility.

**Skepticism.** Do not assume the current code is correct. Propose alternatives when warranted. Mention trade-offs.

---

# Roadmap

Implementation proceeds in small milestones. Each milestone produces a working, runnable application. Do not skip ahead.

| # | Milestone | Delivers |
|---|-----------|----------|
| M1 | Project scaffold | `pyproject.toml`, package layout, `bookfactory --version`, `.gitignore` |
| M2 | Configuration | Layered config load; `bookfactory config show` |
| M3 | Core domain models | Document (CDM) entities, invariants, unit tests |
| M4 | Port definitions | All Protocol interfaces in core |
| M5 | Prompt registry | Manifest load, template render; `bookfactory prompts list` |
| M6 | HTML ingest | Parse fixture HTML → Document; `bookfactory ingest` |
| M7 | HTML export | Document → HTML; golden round-trip test |
| M8 | Chunking | Split Document into chunks; unit tests |
| M9 | Cache | Key derivation, filesystem backend, unit tests |
| M10 | Fake transform adapter | Deterministic output for tests |
| M11 | Job store | SQLite persistence of block state |
| M12 | Pipeline engine | Ingest → chunk → fake transform → export (no LLM) |
| M13 | Structural validator | Integrated in pipeline |
| M14 | Logging + run report | JSONL logs, summary JSON |
| M15 | OpenAI adapter | Real translation of a fixture chapter |
| M16 | Cache integration | Second run hits cache; verified in logs |
| M17 | Resume | Interrupted job resumes; cached blocks skipped |
| M18 | EPUB export | `bookfactory run` outputs HTML + EPUB |
| M19 | Concurrency | Parallel chunk transforms with bounded pool |
| M20 | Pipeline definitions | YAML-driven stage lists |
| M21 | Summarization pipeline | Proves engine is not translation-specific |
| M22 | JSON export | Annotation and metadata export |
| M23 | Second LLM adapter | Provider swap via config only |
| M24 | CLI polish | Progress bar, cost estimate, `--fail-fast`, `--force` |

**v1.0 ships at M18.** Milestones M19–M24 prove extensibility.

**Explicitly deferred past v1.0:**

- Full Workspace entity and `workspace.toml` manifest (v1.1)
- Persistent Knowledge store — glossaries, translation memory (v1.2+, one kind at a time)
- EPUB/PDF/DOCX ingest (when HTML path is stable)
- Audiobook pipeline and MediaSynthesisProvider
- OCR pipeline

---

*Last updated: architecture exploration phase, July 2026.*

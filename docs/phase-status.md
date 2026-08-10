# Implementation Status

This file records what has actually been executed and verified. It intentionally distinguishes implemented behavior from planned work.

## Phase 0 — Read-only reference review and independent design

Status: **complete**

Verified:

- Prior classroom material was inspected read-only and never modified.
- This repository was initialized as a separate greenfield Git repository.
- Product scope, architecture, data-source policy, evaluation plan, clean-room boundary, and ERD were written independently.
- No classroom branding, team names, code, prompts, SQL, assets, PDFs, data files, or Git history were copied.

Remaining limitation:

- Clean-room compliance is process-based; there is no automated semantic code-similarity proof. Public pre-push scans check for known names/paths, secrets, PDFs, and large artifacts.

## Phase 1 — Reproducible foundation

Status: **complete**

Verified on 2026-08-23:

- Product/repository name safely corrected to **AI × MOT Research Lab** / `ai-mot-research-lab`.
- PostgreSQL 18 + pgvector 0.8.6 container starts with the PostgreSQL 18 volume layout.
- Alembic revision `0001` applies successfully.
- pgvector extension version: `0.8.6`.
- Backend health/unit tests pass.
- Ruff and mypy pass.
- Frontend Vitest, TypeScript, ESLint, and production Next.js build pass.
- Database was backed up before local rename and restored under the new runtime name with the same corpus count.

Environment caveat:

- The installed Docker CLI currently lacks the `docker compose` plugin, so Compose configuration is committed and validated structurally while database integration was executed with the same pgvector image using direct `docker run` commands.

## Phase 2 — Small real corpus and provenance-aware ingestion

Status: **complete for OpenAlex-first seed ingestion; enrichment adapters are staged/optional**

Actual local corpus after ingestion:

- Canonical papers: **529**
- Paper embeddings: **529**
- Source-version records: **637**
- Citation/OA snapshots: **933**
- OA records: **401 / 529**
- Publication-year range: **2018–2025**

Research-axis assignments are non-exclusive because a paper can legitimately belong to multiple axes:

- AI adoption and business value: 132
- Technology and innovation management: 132
- AI-enabled organizational change: 132
- Industrial AI and smart operations: 132
- AI governance and responsible deployment: 91
- Agentic systems and enterprise workflows: 18

Idempotency verification:

- A completed six-axis refresh fetched 113 candidate records and accepted 65.
- It inserted **0** new canonical papers and updated 65 existing records.
- Corpus count remained **529**.
- Provider response versions and citation/OA snapshots are preserved rather than replacing historical state.

Robustness verified during real ingestion:

- 429 retry logic honors `Retry-After`.
- Deterministic 4xx errors are not retried.
- Duplicate author/institution relationships in one provider payload are collapsed safely.
- Repeated author entries in a single paper are merged without violating the paper-author key.
- Multiple OpenAlex work records sharing a DOI are merged under the DOI-canonical paper while all source record IDs remain in provenance/version history.
- Failed ingestion runs are recorded and a later run can resume safely without duplicating canonical papers.

Provider status:

- OpenAlex: implemented and exercised with real metadata.
- Crossref: adapter implemented; enrichment is non-blocking and not required for the seed run.
- Semantic Scholar: adapter implemented but disabled by default unless the owner supplies a key after accepting current terms.
- arXiv: pacing-aware adapter implemented; full freshness enrichment is not yet wired into the canonical ingestion service.

Important limitation:

- The no-key `local_hash` embedding is a deterministic engineering baseline so pgvector/hybrid retrieval can be tested without paid credentials. It is **not** presented as a research-quality neural semantic embedding model.

## Phase 3 — Retrieval and Paper Library

Status: **complete for the MVP retrieval/library baseline**

Verified on 2026-08-23:

- PostgreSQL weighted full-text retrieval works on title + abstract.
- pgvector semantic retrieval works against all 529 seed-paper embeddings.
- Hybrid retrieval uses reciprocal rank fusion while preserving lexical and vector rank provenance in the response.
- Search filters support year, research axis, work type, venue, author, methodology label, and OA status.
- The Paper Library UI is connected to the live API and exposes retrieval mode plus lexical/vector rank contributions.
- Paper detail, reading status, personal notes, tags, and saved-search API foundations are implemented.
- Methodology labels were backfilled for all 529 current papers using transparent keyword rules.
- Backend unit tests, Ruff, mypy, frontend Vitest, TypeScript, ESLint, production build, and Playwright Chromium smoke test pass.
- Live API checks returned health OK, 529 landscape papers across six axes, and real hybrid results.
- Server-rendered `/library` output was verified to contain a live corpus result.

Retrieval evaluation on the committed 20-query small manually curated set:

- lexical Mean Recall@5: **0.3750**, Mean nDCG@10: **0.4638**;
- vector Mean Recall@5: **0.3833**, Mean nDCG@10: **0.3901**;
- hybrid Mean Recall@5: **0.7250**, Mean nDCG@10: **0.6652**.

See `docs/evaluation-results.md` for interpretation and limitations.

## Phase 4 onward

Status: **in progress**

Next milestone is evidence-linked paper comparison and a Research Question / Gap Canvas that refuses to convert unsupported generated fields into asserted findings.


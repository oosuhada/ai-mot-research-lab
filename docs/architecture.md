# Architecture

## Design principles

1. **Provenance is part of the domain model.** Source, source record ID, retrieval time, license information, and source-specific metadata are stored alongside normalized records.
2. **Relational facts stay relational.** Core entities and relationships are explicit tables. JSON is reserved for source payload fragments, evaluation details, and extensible generated artifacts.
3. **Retrieval is hybrid by default.** Lexical and semantic candidates are independently inspectable and merged by rank fusion. Filters are applied consistently to both paths.
4. **Metadata retrieval and full-text retrieval are separate.** Paper-level abstract search and chunk-level evidence search use different indexes and response types.
5. **Citation navigation is local and explicit.** OpenAlex external reference IDs are resolved to `papers.id` only when the cited work already exists in the canonical corpus. Backward/forward snowballing therefore exposes corpus-local discovery paths without implying support or contradiction.
6. **Embedding providers coexist.** `local_hash` is the zero-download deterministic baseline; optional FastEmbed MiniLM vectors are stored as separate `paper_embeddings` rows and can be compared without overwriting the baseline. Neural retrieval uses the provider's separate query and passage/document embedding paths.
7. **Reranking must earn its complexity.** The optional local MS MARCO cross-encoder only reorders an already retrieved candidate set. It is disabled by default because it reduced Recall, nDCG, and MRR on the current manually curated evaluation.
8. **Filtered HNSW search must scan iteratively.** Multiple embedding providers share the paper-embedding HNSW index, so vector queries enable pgvector `hnsw.iterative_scan = strict_order` before applying provider/model and research filters. This avoids provider rows being filtered out after too-shallow approximate scans.
9. **Generation never erases uncertainty.** Every generated evidence claim has a support status and links to papers/chunks when available.
10. **Providers are adapters.** OpenAlex, Crossref, Semantic Scholar, arXiv, embeddings, and text generation sit behind narrow interfaces so one provider is never the domain model.
11. **The no-key path remains useful.** Local mock embeddings and deterministic comparison/gap helpers let the UI, tests, and core workflows operate without commercial AI credentials.
12. **Expensive local models are process resources.** Embedding and reranker factories cache provider instances by model so repeated API requests reuse lazy-loaded ONNX sessions rather than recreating model wrappers.
13. **Automatic semantic selection is coverage-gated.** `semantic_provider=auto` chooses FastEmbed only when the exact configured model has one embedding row for every canonical paper and the dependency is installed. Partial backfills fall back to `local_hash` rather than silently searching an incomplete vector index.

## Monorepo layout

```text
apps/
  api/                 FastAPI, SQLAlchemy, Alembic, ingestion, retrieval, evaluation
  web/                 Next.js App Router UI
docs/                  Product, architecture, sources, ERD, evaluation, limitations
artifacts/              Locally generated ingestion/evaluation reports (ignored except placeholders)
data/                   Local-only private/raw/full-text storage (ignored)
docker-compose.yml      PostgreSQL 18 + pgvector 0.8.6
Makefile                One-command local workflows
```

## Runtime topology

```text
Browser / Next.js
      |
      | HTTP JSON
      v
FastAPI application
      |
      +--> Research services
      |      +--> hybrid retrieval
      |      +--> comparison / gap canvas
      |      +--> reading workflow
      |
      +--> Ingestion adapters
      |      +--> OpenAlex (primary metadata)
      |      +--> Crossref (DOI/publication enrichment)
      |      +--> Semantic Scholar (optional terms-gated enrichment)
      |      +--> arXiv (preprint freshness)
      |
      +--> Embedding / generation adapters
             +--> deterministic local mock (default)
             +--> optional hosted provider
      |
      v
PostgreSQL 18 + pgvector
```

## Retrieval architecture

### Paper-level lexical retrieval

PostgreSQL `tsvector` indexes title + abstract. `websearch_to_tsquery` provides user-friendly query parsing. Filters include publication year, research axis, work type, venue, author, methodology label, and OA state.

### Paper-level semantic retrieval

The paper embedding is stored separately from text metadata. The MVP ships a deterministic hash-based embedding provider for tests and offline demos. Its vectors are **not** claimed to have research-quality semantic performance; they exist so the retrieval contract and rank fusion can be exercised without an API key. A production embedding adapter can replace it without schema changes.

### Chunk-level retrieval

`paper_chunks` stores page/section/character offsets, source locator, SHA-256 text hash, and an embedding. Only legitimately acquired full text is chunked. Metadata-only papers can still participate in paper-level retrieval and comparison with an explicit evidence limitation.

The v0.2 retrieval API exposes `metadata`, `abstract`, `full_text`, and `all` scopes. Full-text lexical/vector candidates carry the matched chunk locator into the RRF result; paper-level candidates retain their own source explanation. Reading-state/tag filters and relevance/newest/citation/priority sorts operate above the same canonical paper IDs.

User imports create explicit ingestion runs and source versions. DOI is the strongest canonical merge key; BibTeX/RIS/CSV records without a resolvable DOI can create user-import records. User PDFs are stored only under the configured private-data root, hashed, parsed page by page with `pypdf`, and never treated as redistributable by possession alone. OCR is not automatic.

`research_questions` is the v0.2 workflow center. Link tables connect a question to papers, saved searches, and comparison sets; gap analyses already point to the question directly. Question notes and explicit importance/evidence/uncertainty fields keep user judgment separate from system inference.

### Hybrid merge

Lexical and vector result lists are merged using Reciprocal Rank Fusion (RRF). This avoids pretending score scales are directly comparable. The API exposes lexical rank, semantic rank, and fused score for evaluation and debugging.

Reranking remains optional and experimental. The current `Xenova/ms-marco-MiniLM-L-6-v2` cross-encoder degraded the
20-query evaluation when compared with the exact same RRF candidate pools, so `rerank=none` remains the recommended
default rather than promoting a more complex model on assumption alone.

## Ingestion architecture

Each ingestion run is an explicit durable record:

1. Create `ingestion_runs` row with source, query/taxonomy version, and configuration.
2. Fetch a page with bounded timeout and provider-specific pacing.
3. Normalize identifiers (`doi`, `openalex_id`, `s2_id`, `arxiv_id`).
4. Apply deterministic inclusion/exclusion rules.
5. Upsert canonical paper using strongest available identifier.
6. Upsert source provenance and relationships.
7. Snapshot volatile counts/status fields such as citation count and OA status.
8. Advance checkpoint only after the transaction commits.
9. Retry retryable network/429/5xx errors with exponential backoff and jitter.
10. Finish the run with counts and a locally generated manifest/provenance report.

Provider enrichment failures do not roll back the primary OpenAlex record.

## Canonical identity and deduplication

Priority order:

1. normalized DOI
2. OpenAlex work ID
3. Semantic Scholar Paper ID
4. arXiv ID
5. conservative normalized-title + year fallback, used only when no stronger identifier exists

Identifier collisions are rejected rather than silently merged. The merge code records why two records were considered equivalent.

## Evidence model

`evidence_claims` stores a generated or user-authored claim separately from its evidence links. Each claim has:

- claim kind: fact, paper_claim, system_inference, user_note
- support status: supported, mixed, contradicted, insufficient_evidence
- generated text and optional structured field path
- links to one or more papers/chunks with relation `supports`, `contradicts`, or `context`

The UI must not display a generated comparison field or gap statement as established evidence when the support status is `insufficient_evidence`.

## Deletion and provenance policy

- Deleting a personal note/tag/queue item is allowed and cascades only through user-owned join rows.
- Canonical scholarly records use restrictive foreign keys where deletion would destroy provenance or evidence history.
- Source provenance and ingestion-run records are retained even if a paper is later retracted or superseded.
- Retraction/correction changes update current state while preserving version/snapshot history.

## Security and secrets

- Secrets live only in `.env`, never in source control.
- `.env.example` contains names and explanations but no real values.
- API responses do not echo provider credentials.
- PDF/raw ingestion directories are git-ignored.
- The public repository contains code, small hand-curated evaluation judgments, and source-safe metadata examples only.

## Local infrastructure

The canonical local database is PostgreSQL 18 with pgvector 0.8.6. Docker Compose is the documented route. Tests that do not require PostgreSQL run directly on the host; database integration tests are marked separately so the repository remains diagnosable when Docker is unavailable.


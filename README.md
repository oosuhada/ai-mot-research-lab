# AI × MOT (Management of Technology, 기술경영) Research Lab

제품명은 **AI × MOT Research Lab**이며, AI와 기술경영 연구의 교차 영역을 위한 개인 연구 인텔리전스 시스템입니다.

**AI & Management of Technology Research Intelligence**

**AI와 기술경영 연구를 위한 근거 기반 논문 인텔리전스**

> A greenfield personal research tool for building an evidence-traceable literature corpus around AI and Management of Technology—not a general-purpose paper chatbot.

## 왜 만들었나 / Why I built this

대학원 진학을 준비하면서 AI와 기술경영의 교차 영역에서 어떤 연구가 이루어지고 있는지 꾸준히 축적할 필요가 생겼습니다. 검색할 때마다 같은 논문을 다시 찾고, 읽기 상태·메모·비교표·연구 질문을 서로 다른 도구에 흩어 놓는 대신 **관심 연구 분야 자체를 DB로 만들고, 주장과 근거를 따라 탐색할 수 있는 개인 연구 시스템**을 만들기로 했습니다.

While preparing for graduate study, I wanted a durable way to understand how AI changes organizations, industries, innovation, operations, and managerial decision-making. Instead of repeatedly rediscovering papers and scattering notes and comparison tables across tools, I am building the research domain itself as a provenance-aware database that can be searched, compared, and questioned with evidence attached.

The product question is:

> **How is AI changing organizations, industries, innovation activity, and decision-making; what has existing research explained, and what questions are worth testing next?**

## What is implemented

The current MVP is intentionally narrow. It covers six research axes:

1. **AI adoption and business value** — adoption, productivity, performance, ROI, capabilities, complementarities
2. **Technology and innovation management** — technology strategy, R&D management, innovation diffusion, absorptive capacity, dynamic capabilities
3. **AI-enabled organizational change** — job redesign, human–AI collaboration, decision-making, organizational structure, knowledge work
4. **Industrial AI and smart operations** — manufacturing AI, smart factories, quality/yield, predictive maintenance, digital twins
5. **AI governance and responsible deployment** — trust, accountability, human oversight, risk, regulation, governance
6. **Agentic systems and enterprise workflows** — AI agents, multi-agent systems, workflow automation, stateful coordination, human-in-the-loop work

### Research Landscape

- corpus size and year distribution;
- paper counts by the six research axes;
- leading authors, institutions, and venues;
- OA coverage;
- a landscape-first UI before chat or synthesis.

### Paper Library

- PostgreSQL weighted full-text search;
- pgvector semantic retrieval;
- reciprocal-rank-fused **hybrid retrieval**;
- filters for year, research axis, work type, venue, author, methodology label, and OA status;
- visible lexical rank + semantic rank provenance;
- paper detail, reading queue, personal tags, notes, and saved searches;
- DOI/source links kept close to every result.

### Compare Papers

Saved comparison sets use the requested research-design fields:

- research question;
- theoretical lens;
- unit of analysis;
- context / industry / country;
- dataset and sample;
- methodology;
- variables or constructs;
- findings;
- limitations;
- claimed contribution;
- future research.

The MVP only marks a field `supported` when the available abstract/metadata contains traceable evidence. If the field cannot be established, it remains **`insufficient_evidence`** rather than being filled with an LLM guess.

### Research Question & Gap Canvas

- hybrid retrieval strategy plus explicit inclusion/exclusion criteria;
- research-axis coverage clusters;
- editable agreements/conflicts/context notes;
- candidate gaps with a falsifiability checklist;
- follow-up questions;
- candidate theoretical lenses and methods;
- user edits stored distinctly as `user_note` claims.

Sparse retrieval is treated as a **candidate coverage signal**, not proof that a research gap exists.

### Evidence-grounded Chat

Chat can be scoped to:

- the whole corpus;
- explicit paper IDs;
- one saved comparison set.

The no-key MVP uses a deterministic evidence provider behind a provider interface. It does **not** pretend to be a full scholarly LLM: it retrieves papers, selects traceable abstract evidence, and attaches paragraph-level citation indexes. When evidence is not sufficient, it says so.

## Current corpus

The current local seed corpus was built from real OpenAlex metadata and is deliberately small enough to inspect:

| Asset | Current local count |
| --- | ---: |
| Canonical papers | **529** |
| Paper embeddings | **529** |
| Provider/source versions | **637** |
| Citation / OA snapshots | **933** |
| Open-access records | **401 / 529** |
| Publication range | **2018–2025** |

Research-axis assignments are non-exclusive, so totals across axes are larger than the corpus.

The database dump and raw provider payload artifacts are **not committed to Git**. A fresh installation can build its own seed corpus through the ingestion command.

## Retrieval & grounding evaluation

The repository includes **20 manually curated AI × MOT golden queries** in `evaluation/golden_queries.json`. This is a **small manually curated evaluation set**, not a benchmark large enough to support broad performance claims.

Results from the current 529-paper local corpus:

| Retrieval mode | Mean Recall@5 | Mean nDCG@10 | MRR@10 |
| --- | ---: | ---: | ---: |
| Lexical | 0.3750 | 0.4638 | 0.4110 |
| Vector (`local_hash`) | 0.3833 | 0.3901 | 0.4336 |
| Hybrid (RRF) | **0.7250** | **0.6652** | **0.6875** |

Structural grounding checks across the same 20 queries:

| Metric | Result |
| --- | ---: |
| Claim-to-evidence structural coverage | **1.0000** |
| Structural unsupported-claim rate | **0.0000** |
| Invalid citation indexes | **0** |
| Semantic citation precision | **Not yet human-scored** |

The distinction matters: structural checks prove that assertive paragraphs point to citation objects. They do **not** prove semantic entailment. Human claim-to-source review is still required before reporting citation precision.

See [`docs/evaluation-results.md`](docs/evaluation-results.md) and [`docs/evaluation-plan.md`](docs/evaluation-plan.md).

## Architecture

```text
Next.js 16 / TypeScript
        │
        ▼
FastAPI / Pydantic
        │
        ├── provenance-aware ingestion
        ├── lexical / vector / hybrid retrieval
        ├── comparison + gap evidence services
        └── grounded answer provider interface
        │
        ▼
PostgreSQL 18 + pgvector 0.8.6
        │
        ├── normalized scholarly entities
        ├── source versions + snapshots
        ├── paper/chunk embeddings
        └── evidence claims + evidence links
```

Key technology choices:

- **Frontend:** Next.js 16, React 19, TypeScript
- **Backend:** FastAPI, Python, Pydantic
- **Database:** PostgreSQL 18 + pgvector
- **ORM / migrations:** SQLAlchemy 2 + Alembic
- **Testing:** pytest, Vitest, Playwright
- **Quality:** Ruff, mypy, ESLint, TypeScript
- **Local infrastructure:** Docker Compose configuration

The implementation deliberately avoids wrapping simple pipelines in a large orchestration framework. LLM/embedding behavior sits behind interfaces so a production provider can be added later without coupling evidence storage to one vendor.

## Core data model

The schema is normalized rather than storing the research system in one JSON blob. Core tables include:

`papers`, `authors`, `institutions`, `venues`, `paper_authors`, `paper_topics`, `citations`, `citation_snapshots`, `paper_versions`, `paper_chunks`, `paper_embeddings`, `ingestion_runs`, `saved_searches`, `reading_queue`, `paper_notes`, `tags`, `research_questions`, `comparison_sets`, `comparison_cells`, `gap_analyses`, `evidence_claims`, and `evidence_links`.

See [`docs/erd.md`](docs/erd.md) for constraints and delete/provenance policies.

## Data-source policy

Primary and optional sources are intentionally separated:

| Source | Role | Project policy |
| --- | --- | --- |
| **OpenAlex** | primary scholarly metadata, authors/institutions/topics/citation counts | first-write source for the seed corpus; preserve work ID, retrieval time, provenance and snapshots |
| **Crossref** | DOI/publication/license/update enrichment | conservative polite-pool access; respect live rate/concurrency headers |
| **Semantic Scholar Academic Graph** | optional citation/context enrichment | disabled by default; only enable locally after reviewing the current license/attribution terms |
| **arXiv** | preprint freshness, especially agentic systems | metadata-first; legacy API pacing; no PDF redistribution without permission |
| **User imports** | DOI/BibTeX/RIS/CSV and legally held PDFs | private source provenance; PDFs stay local and out of Git |

Collection rules include:

- no Google Scholar scraping;
- no unauthorized crawling of DBpia, RISS, Scopus, Web of Science, publisher sites, or other access-controlled services;
- a discoverable PDF URL is **not** treated as redistribution permission;
- full text is processed only when OA/license status permits it or the user supplies the file;
- source ID, retrieval time, license/provenance and changing citation/OA snapshots are preserved.

Provider terms and official documentation reviewed for this build are recorded in [`docs/data-sources.md`](docs/data-sources.md).

## Getting started

### Prerequisites

- Docker with Docker Compose plugin (or `docker-compose`)
- Python 3.12–3.14 for host-side development
- Node.js 24

### 1. Clone and configure

```bash
git clone https://github.com/oosuhada/ai-mot-research-lab.git
cd ai-mot-research-lab
cp .env.example .env
```

For a small local demo, API keys are not required. Add your own keys only in `.env` when you intentionally enable/expand a provider.

### 2. Start the full local stack

```bash
make dev
```

This is the root development command. It starts PostgreSQL/pgvector, applies Alembic migrations in the API container, and starts FastAPI + Next.js.

- Web: `http://localhost:3000`
- API: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`
- PostgreSQL: `localhost:55432`

Stop the stack with:

```bash
make down
```

If your Docker installation does not include either the Compose plugin or the legacy `docker-compose` binary, `scripts/compose.sh` exits with an explicit installation message rather than silently falling back to a different runtime.

### 3. Build a seed corpus

After the stack is running:

```bash
make seed
```

The default command targets a small ~600-paper design corpus rather than bulk-loading millions of records. The canonical count can be lower because identifiers/DOIs are merged and inclusion rules reject out-of-scope records.

### 4. Evaluate retrieval

```bash
make evaluate
```

Raw runtime reports are written under `artifacts/evaluation/` and ignored by Git.

## Host-side development commands

```bash
make install
make test
make lint
make typecheck
```

Backend migration from the host requires `DATABASE_URL` to point at a running PostgreSQL/pgvector instance:

```bash
make migrate
```

The GitHub Actions workflow runs backend tests/lint/type checking plus frontend unit tests, type checking, linting, production build, and a Chromium Playwright smoke test.

## Evidence rules

The product is built around a few non-negotiable rules:

1. Important claims must have paper/chunk evidence links.
2. A citation object must actually refer to the paper used for the claim.
3. `fact`, `paper_claim`, `system_inference`, and `user_note` are stored distinctly.
4. If the available corpus cannot support a conclusion, the output must say **`insufficient_evidence`**.
5. A research gap is a **candidate hypothesis to validate/falsify**, not an automatically discovered fact.
6. Korean summaries may be added later, but key English terminology and original evidence must remain inspectable.

## Tests and verified local state

Verified on 2026-08-23:

- backend: **20 pytest tests passed**;
- Ruff: passed;
- mypy: passed;
- frontend Vitest: passed;
- TypeScript: passed;
- ESLint: passed;
- Next.js production build: passed;
- Playwright Chromium smoke: passed;
- Alembic `0001`: applied successfully on PostgreSQL 18;
- pgvector: `0.8.6`;
- ingestion refresh: **0 duplicate canonical inserts** on the idempotency verification run;
- live hybrid search, comparison, Gap Canvas and grounded chat endpoints: verified against the local 529-paper corpus.

Detailed execution status is in [`docs/phase-status.md`](docs/phase-status.md).

## Repository safety and privacy

This repository intentionally does **not** contain:

- raw article PDFs;
- PostgreSQL dumps or the 529-paper local database;
- API keys or `.env`;
- private imported research files;
- classroom-project source code, branding, assets, data, prompts, or Git history.

Before a public release, `scripts/public-release-check.sh` scans tracked files for common secret patterns, PDFs/database artifacts, files over 10 MiB, obsolete/private project references, and unexpected environment files.

## Current limitations

- The seed corpus is small and intentionally scoped; it is not a comprehensive systematic-review database.
- Most current evidence is metadata/abstract-level. Exact page/section locators need legally available or user-supplied full text.
- `local_hash` is a deterministic engineering embedding baseline, not a research-quality semantic model.
- The no-key chat provider is an evidence-surfacing baseline, not a substitute for scholarly synthesis.
- Semantic citation precision has not yet been human-scored.
- Crossref, Semantic Scholar and arXiv adapters exist, but OpenAlex is the only provider exercised end-to-end for the current seed corpus.
- Import UI/parsers for BibTeX/RIS/CSV/PDF are still roadmap work even though their schema/provenance policy is defined.

## Roadmap

- legally licensed/user-supplied PDF parsing with page/section locators;
- DOI, BibTeX, RIS and CSV import UI;
- production embedding adapter + reranking evaluation;
- optional LLM synthesis adapter with citation entailment checks;
- human-scored semantic citation precision and larger relevance judgments;
- Crossref/arXiv enrichment wired into scheduled canonical refreshes;
- richer citation/topic network visualization;
- Korean synthesis while preserving English source terminology;
- naming may be revisited later (for example, **AI × MOT Evidence Lab**), but the repository will remain `ai-mot-research-lab` for this release.

## Design & implementation docs

- [`docs/product-brief.md`](docs/product-brief.md)
- [`docs/architecture.md`](docs/architecture.md)
- [`docs/erd.md`](docs/erd.md)
- [`docs/data-sources.md`](docs/data-sources.md)
- [`docs/evaluation-plan.md`](docs/evaluation-plan.md)
- [`docs/evaluation-results.md`](docs/evaluation-results.md)
- [`docs/clean-room-notes.md`](docs/clean-room-notes.md)
- [`docs/phase-status.md`](docs/phase-status.md)

---

**AI × MOT Research Lab** is being built as a personal research instrument first: the goal is not to make research conclusions sound confident, but to make it easier to see **what the evidence is, where it came from, what is still uncertain, and what question is worth testing next**.

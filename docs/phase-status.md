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
- OpenAlex bulk bootstrap: the API-key path inherits the existing per-axis/year page checkpoints, processes them in
  larger bounded batches, and falls through to cursor-paged title/abstract candidate download only where necessary for
  the 100k target. Raw pages are retained as gzip runtime artifacts and imported through the same canonical
  identity/provenance logic. The old page-number worker remains the no-key fallback.
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

## Phase 4 — Evidence-linked comparison and Gap Canvas

Status: **complete for an abstract-grounded MVP baseline**

Verified on 2026-08-23:

- Comparison sets persist selected papers and all 11 requested comparison fields.
- A comparison field is marked `supported` only when a traceable abstract sentence or explicit abstract keyword supports it.
- Supported comparison cells create an `evidence_claim` and `evidence_link` with `source_locator=abstract`.
- Fields that cannot be established from available abstract/metadata remain `insufficient_evidence`; the system does not invent limitations, future research, samples, or theory labels.
- A real two-paper integration run produced 22 cells: 11 abstract-supported cells with evidence links and 11 explicit insufficient-evidence cells without evidence links.
- Gap Canvas persists the research question, retrieval strategy, inclusion/exclusion criteria, clusters, candidate coverage signals, falsifiability notes, follow-up questions, theory candidates, and method candidates.
- Sparse retrieval is labeled as a **candidate coverage signal**, never as proof that a research gap exists.
- A supported Gap Canvas corpus-coverage claim carries paper evidence links; the generated gap candidate remains `insufficient_evidence` until further validation.
- User edits are persisted and recorded as `user_note` evidence claims rather than being silently mixed with system output.
- The Compare and Gap Canvas web routes create/load saved records through Server Actions and render evidence status in the UI.
- HTTP integration checks verified comparison create (`201`), gap create (`201`), and gap edit (`200`); integration records were deleted immediately after verification.

Current limitation:

- The seed corpus is metadata/abstract-first. Full comparison depth for limitations, contribution, future research, exact constructs, and page-level locators requires legally available or user-supplied full text.

## Phase 5 — Evidence-grounded Chat

Status: **complete for the no-key grounding baseline**

Verified on 2026-08-23:

- Chat requests can target the whole corpus, explicit paper IDs/current-result IDs, or one saved comparison set.
- The answer-provider interface is isolated behind `GroundedAnswerProvider`; the default is a deterministic no-key provider, not a fake LLM.
- The provider only reports traceable abstract-level evidence and citation indexes; it does not invent a synthetic literature consensus.
- Every assertive paragraph is required by the provider/evaluator contract to reference evidence.
- Contradiction/opposing-evidence requests return a cautious lexical signal when present; otherwise the response explicitly says `insufficient_evidence` rather than fabricating opposition.
- The Chat UI exposes scope, provider, support status, claim kind, paragraph-level citation markers, and an evidence drawer with source links and abstract locators.
- Live `/chat` API verification returned four cited supported paragraphs with structural unsupported-claim rate `0.0` for an AI-capability/performance question.
- A live opposing-evidence query produced cited retrieved evidence plus an `insufficient_evidence` contradiction paragraph when no clear contradiction signal was available.
- Server-rendered `/chat` HTML was verified to contain the grounded response, provider label, evidence drawer, and a real corpus paper.

20-query structural grounding evaluation:

- structural claim-to-evidence coverage: **1.0000**;
- structural unsupported-claim rate: **0.0000**;
- invalid citation indexes: **0**;
- semantic citation precision: **not yet human-scored**.

The last point is important: citation structure can be automatically verified, but semantic entailment cannot be claimed from these engineering checks alone.

## Phase 6 — Public documentation and repository preparation

Status: **complete**

Verified on 2026-08-23:

- Bilingual README published with the product identity **AI × MOT Research Lab** and first-use expansion of MOT (Management of Technology, 기술경영).
- README separates implemented behavior, measured evaluation results, current limitations, and roadmap work.
- Current official provider documentation was rechecked before release; OpenAlex and Crossref allowance/rate-limit wording was updated accordingly.
- GitHub Actions CI covers repository safety scanning, backend tests/lint/type checking, frontend unit/type/lint/build checks, and a Chromium Playwright smoke test.
- `scripts/public-release-check.sh` passed against the tracked repository: no common secret patterns, PDFs/database dumps, files larger than 10 MiB, obsolete/private project references, or unexpected `.env` files were found.
- The browser smoke test also passed with the API intentionally stopped, matching the fallback condition expected in a clean CI runner.
- Public GitHub repository created exactly once at `https://github.com/oosuhada/ai-mot-research-lab`.
- Repository visibility verified as `PUBLIC`, default branch verified as `main`, and local/remote commit hashes matched after the first push.

Release caveat:

- The 529-paper local database and runtime evaluation JSON are intentionally excluded from Git. The repository contains ingestion/evaluation code and the manually curated golden-query judgments, not a distributable research database dump.

## v0.3 — Local semantic retrieval and citation snowballing

Status: **implemented and locally verified**

Verified on 2026-08-23:

- Added optional FastEmbed `0.8.0` provider using `sentence-transformers/all-MiniLM-L6-v2`; the baseline remains `local_hash` and both providers coexist in `paper_embeddings`.
- Backfilled 529 FastEmbed/MiniLM rows without replacing the 529 existing deterministic embeddings.
- Extended the committed 20-query evaluator to report embedding-provider comparisons.
- FastEmbed vector retrieval reached Recall@5 `0.6083`, Recall@10 `0.7500`, nDCG@10 `0.5978`, MRR@10 `0.6573`.
- FastEmbed hybrid retrieval reached Recall@5 `0.8083`, Recall@10 `0.9583`, nDCG@10 `0.8120`, MRR@10 `0.8196` after separating query/document embedding paths and enabling filtered HNSW iterative scans.
- Resolved 1,382 existing OpenAlex citation edges to canonical local papers; 346 papers have local backward-reference paths and 363 papers are local forward-citation targets.
- Paper Detail now exposes corpus-local backward/forward snowballing with an explicit warning that citation is a discovery relation, not claim support.
- Research Question recommendations combine hybrid query matching with backward/forward snowball reasons while excluding already linked papers.
- Research Question recommendations now expose decomposed score components, prefer the locally available FastEmbed index with safe fallback, exclude `read`/`archived` papers from next-reading suggestions, and reward distinct multi-seed citation bridges without using citation count as a quality proxy.
- A live two-seed recommendation check produced a FastEmbed query-rank-1 candidate with two backward seed paths and score `1.61` (`query 1.00 + backward 0.36 + bridge 0.15 + unread novelty 0.10`); marking the candidate `read` removed it from the next recommendation call, and the temporary state was restored afterward.
- Live integration verification returned neural-search results, backward and forward citation neighbors, and recommendations with combined `query_match` + `forward_snowball` reasons; the temporary Research Question was deleted afterward.
- The retrieval candidate depth is fixed at 100 for supported API result limits so changing pagination/result depth does not silently change the RRF candidate universe.
- Library now separates ranked **Search Results** from **Browse All Papers**. Search keeps the fixed 100-candidate RRF
  universe, while Browse traverses the entire filtered corpus with a deterministic `created_at + paper_id` keyset
  cursor, exact total/range reporting, and no search-cap wording.
- pgvector `hnsw.iterative_scan = strict_order` is enabled for vector retrieval because provider/model filters otherwise operate after the approximate index scan; two consecutive provider evaluations produced identical metrics, and a subsequent full evaluator reproduced them.
- User-import embeddings now use the same configured provider as ingestion, private PDF evidence, and retrieval rather than always writing `local_hash` vectors.
- An experimental FastEmbed MS MARCO cross-encoder was measured on the top-30 neural-hybrid candidate pool. The stable 100-candidate RRF baseline scored Recall@5 `0.8083`, Recall@10 `0.9583`, nDCG@10 `0.8120`, MRR@10 `0.8196`; reranking reduced those to `0.7417`, `0.8833`, `0.7181`, `0.7642`. It remains disabled by default.
- Added a local human semantic-grounding review workflow: the current 20-query export contains 99 claim/evidence pairs, every `human_label` starts blank, and semantic citation precision remains `null` with status `awaiting_human_review` until a person explicitly labels pairs.
- FastEmbed embedding and cross-encoder provider instances are now process-cached by model; lazy model loading remains intact and no model is loaded by the retrieval-health endpoint.
- Added `/api/v1/retrieval/health` to expose stored provider/model embedding counts, FastEmbed dependency presence, the database HNSW default, and the application-level `strict_order_per_vector_query` policy separately.
- Warm local hybrid-search benchmark on this development machine: `local_hash` median `11.6 ms`, p95 `14.7 ms`; FastEmbed MiniLM median `32.5 ms`, p95 `37.2 ms` over 15 timed samples each. These are local observations, not deployment guarantees.
- Library/API semantic search now defaults to `auto`: the current 529-paper DB selects FastEmbed because the exact configured MiniLM model has 529/529 rows; fresh/partial neural backfills fall back to `local_hash`. Search responses expose both the requested provider and the actual provider/reason.

## v0.2 — Daily research workbench

Status: **implemented and locally verified on 2026-08-23**

Implemented:

- Paper Detail now supports reading state/priority, tags, notes with source locators, citation snapshot, retraction/correction status, research axes, clearly labeled methodology heuristics, and inspectable provenance.
- DOI, BibTeX, RIS, and CSV user imports create ingestion runs/source versions; DOI re-import merges into the existing canonical paper rather than duplicating it.
- User-supplied permitted PDFs are private-by-default, SHA-256 addressed, extracted page by page with `pypdf`, chunked with page/section locators, and embedded for full-text retrieval. OCR is not automatic.
- Retrieval exposes metadata/abstract/full-text/all scopes, reading/tag filters, relevance/newest/citation/priority sorts, and the matched evidence source/locator alongside lexical/vector/RRF ranks.
- Research Questions are persistent workspaces linking papers, saved searches, comparisons, gap analyses, and notes, with explicit importance/evidence/uncertainty fields.
- Compare supports 2–6 papers, prefers private full-text evidence when available, records cell origin (`paper_evidence`, `system_inference`, `user_note`), supports grounded manual edits, and exports structured Markdown/CSV.
- Gap Canvas reuses an existing Research Question, reports evidence-linked year/methodology coverage, and exposes a structured candidate hypothesis that remains `insufficient_evidence` until falsified/validated.
- Evidence Chat supports corpus, selected papers, comparison set, saved search, and Research Question scopes; private full-text chunks take precedence over abstract fallback and expose page/section locators.
- Research Landscape now includes OA ratio, methodology heuristic distribution, top authors/venues, year coverage, and last completed ingestion time. Sparse coverage is explicitly described as local-corpus coverage rather than a field gap.
- Writable Playwright coverage now uses a disposable `_e2e` PostgreSQL database with Alembic migrations, deterministic
  125-paper fixtures, writable API/UI processes, a second read-only API/UI pass, and guaranteed database cleanup. Core
  question creation, metadata import, reading state, tag/note CRUD, Compare feedback, Gap Canvas feedback, and public
  403/UI hiding are exercised without mutating production data.
- Production API policy is explicitly internal-only: Next.js uses `INTERNAL_API_BASE_URL`, the Cloudflare Tunnel exposes
  only the web service, `PUBLIC_API_HOSTS` is optional/blank by default, and the unused `aimot.oosu.dev` hostname is not
  treated as a required health endpoint.

Database migration:

- `0002_research_workspace` was applied to the live PostgreSQL 18 database after a same-major `pg_dump` safety backup.
- Canonical paper count remained **529** after migration.
- New question/link/note tables started empty; no user research-question data was fabricated during migration.

Operational user-journey checks (temporary verification records were deleted afterward):

- Journey A: search → detail → reading `reading/77` → tag → note with `abstract` locator → readback succeeded.
- Journey B: the same existing DOI was imported twice; canonical paper count stayed **529**, while source-version history increased as expected.
- Journey C: a temporary permitted PDF fixture produced `p. 1 · Methods` / `p. 1 · Results` chunk locators; full-text hybrid search and Chat both surfaced page-level evidence; fixture data/files were removed.
- Journey D: a three-paper comparison produced both supported and insufficient-evidence cells, evidence links, and working Markdown/CSV exports.
- Journey E: an existing Research Question was reused by Gap Canvas; the candidate remained `insufficient_evidence`, and a user edit persisted as user-authored material.
- Journey F: Research-Question-scoped chat had structural unsupported-claim rate **0.0**, invalid citation indexes **0**, and contradiction follow-up returned mixed/insufficient evidence rather than inventing opposition.

v0.2 evaluation (same 20-query manually curated set):

- lexical Recall@5 **0.3750**, Recall@10 **0.7750**, nDCG@10 **0.4638**, MRR@10 **0.4110**;
- vector Recall@5 **0.3833**, Recall@10 **0.5083**, nDCG@10 **0.3901**, MRR@10 **0.4336**;
- hybrid Recall@5 **0.7250**, Recall@10 **0.8083**, nDCG@10 **0.6652**, MRR@10 **0.6875**;
- structural claim-to-evidence coverage **1.0000**, unsupported rate **0.0000**, invalid citation indexes **0**;
- semantic citation precision remains **human review required**.

Known v0.2 limitations:

- The committed seed corpus remains metadata/abstract-first; private full text exists only on the local machine when the user adds it.
- `local_hash` remains a deterministic engineering baseline, not a production-quality semantic model.
- OCR, human-scored semantic citation precision, production embedding/reranking, and broader provider enrichment remain future work.


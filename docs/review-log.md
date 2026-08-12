# Objective Review Log

This file records iterative product and engineering self-reviews. Scores are intentionally conservative and tied to measurable evidence rather than feature count.

## 2026-08-23 14:00 KST — v0.3 quality review

### Review perspectives

- Senior backend/platform engineer
- Search / ML engineer
- Research-tool product manager
- Research-methods reviewer

### Scores before this review

| Dimension | Score / 10 | Evidence |
| --- | ---: | --- |
| Engineering correctness | 8.3 | CI green, typed API, migrations, provenance-aware schema |
| Retrieval quality | 7.8 | FastEmbed hybrid materially outperforms `local_hash` on 20 curated queries |
| Research integrity | 8.8 | explicit `insufficient_evidence`, claim-kind separation, provenance links |
| Workflow usefulness | 8.1 | search → detail → compare → gap → chat + question workspace |
| Operational maturity | 7.6 | public-release checks and CI exist; local model lifecycle is still manual |

Overall: **8.1 / 10**

### Problems found

1. User-import embeddings ignored the configured embedding provider and always wrote `local_hash` vectors.
2. RRF candidate depth changed with the requested result count, making top results sensitive to pagination depth.
3. The optional cross-encoder reranker had no committed evidence that it improved this corpus.
4. Strict mypy under Python 3.14 exposed an `Any` leak in retry-delay arithmetic.

### Improvements made

- User imports now use the same configured embedding-provider factory as ingestion, PDF evidence, and retrieval.
- Query and document embedding paths are explicit (`embed_query` vs. `embed_document`).
- Hybrid retrieval now uses a stable 100-candidate lexical/vector pool for API result limits up to 100.
- Evaluation now records cross-encoder reranker metrics separately from embedding-provider metrics.
- UI labels the cross-encoder as experimental and keeps `none` as the recommended setting.
- Retry-delay arithmetic now has an explicit `float` contract under strict mypy.

### Measured result after improvement

FastEmbed MiniLM hybrid on the 20-query curated set:

- Recall@5: **0.8083**
- Recall@10: **0.9333**
- nDCG@10: **0.8034**
- MRR@10: **0.8196**

Cross-encoder reranking degraded those metrics to 0.7417 / 0.8833 / 0.7181 / 0.7642 respectively, so it is not promoted to the default.

### Scores after this review

| Dimension | Score / 10 | Change |
| --- | ---: | ---: |
| Engineering correctness | 8.6 | +0.3 |
| Retrieval quality | 8.2 | +0.4 |
| Research integrity | 8.8 | 0.0 |
| Workflow usefulness | 8.1 | 0.0 |
| Operational maturity | 7.9 | +0.3 |

Overall: **8.3 / 10**

### Next review priority

Improve Research Question recommendations by combining semantic relevance, local citation-neighbor evidence, reading state, and novelty without treating citation count as a quality proxy. Add a human-reviewable semantic citation-entailment sample so grounding quality is not measured structurally only.

## Iteration 2 — Research Question recommendation quality

### Problems found

1. Recommendation score was effectively `1/rank + fixed citation-edge bonus`, which hid why one paper beat another.
2. Papers already marked `read` or `archived` could still appear in “What to read next”.
3. Citation-neighbor evidence did not distinguish one seed connection from a multi-seed bridge.
4. Recommendation retrieval inherited the default embedding setting even when a fully backfilled neural index was locally available.

### Improvements made

- Recommendation score is decomposed into query relevance, backward snowball, forward snowball, multi-seed bridge, and unread novelty components.
- `read` and `archived` papers are excluded from next-reading recommendations by default.
- Snowball contribution is based on distinct linked seed papers, not global citation count.
- A multi-seed bridge receives a bounded explicit bonus; raw citation popularity is not used as a quality score.
- Recommendations prefer the matching local FastEmbed index when it is present, with an explicit `local_hash` fallback.
- The UI exposes score components, query rank, seed-path counts, reading state, and provider, and supports one-click linking to the Research Question.

### Operational verification

With two corpus-local seed papers, the temporary integration question produced a FastEmbed recommendation with query rank **1**, two backward seed paths, and score **1.61**. The score decomposed into query 1.00 + backward 0.36 + bridge 0.15 + unread novelty 0.10.

After temporarily marking that paper `read`, it disappeared from the next recommendation call. The temporary question and reading-state change were then removed/restored.

### Scores after iteration 2

| Dimension | Score / 10 | Change from prior review |
| --- | ---: | ---: |
| Engineering correctness | 8.7 | +0.1 |
| Retrieval quality | 8.2 | 0.0 |
| Research integrity | 9.0 | +0.2 |
| Workflow usefulness | 8.6 | +0.5 |
| Operational maturity | 8.0 | +0.1 |

Overall: **8.5 / 10**

### Next review priority

Move grounding evaluation beyond structural citation attachment by creating a small human-reviewable claim-to-source entailment set. The goal is to measure whether cited evidence actually supports, contradicts, or fails to support the generated claim, without inventing an automated semantic-precision score.

## Iteration 3 — Multi-provider vector-index correctness

### Problem found

`paper_embeddings` stores both `local_hash` and FastEmbed vectors in the same HNSW index. PostgreSQL/pgvector applies provider/model filters after approximate candidate retrieval, so a shallow HNSW scan can discard candidates from the wrong provider and reduce filtered recall. This made neural-hybrid top-10 results sensitive to the approximate scan rather than only the retrieval logic.

### Improvement made

- Every vector-search leg enables `SET LOCAL hnsw.iterative_scan = 'strict_order'` before filtered HNSW retrieval.
- A regression test asserts that filtered vector search enables iterative scanning.
- Evaluation is run with both embedding providers present, so this multi-provider index condition is part of the measured baseline rather than an untested deployment detail.

### Reproducibility check

Two consecutive provider evaluations produced identical results. FastEmbed MiniLM hybrid measured:

- Recall@5: **0.8083**
- Recall@10: **0.9583**
- nDCG@10: **0.8120**
- MRR@10: **0.8196**

The full evaluator reproduced the same RRF baseline and again showed that the experimental cross-encoder degraded quality to 0.7417 / 0.8833 / 0.7181 / 0.7642.

### Scores after iteration 3

| Dimension | Score / 10 | Change from prior iteration |
| --- | ---: | ---: |
| Engineering correctness | 9.0 | +0.3 |
| Retrieval quality | 8.6 | +0.4 |
| Research integrity | 9.0 | 0.0 |
| Workflow usefulness | 8.6 | 0.0 |
| Operational maturity | 8.2 | +0.2 |

Overall: **8.7 / 10**

### Next review priority

Create a small, explicitly human-reviewable semantic grounding set that labels claim/evidence pairs as support, contradict, or insufficient. Use it to review deterministic chat and future LLM adapters without pretending that an automatic similarity score is semantic citation precision.

## Iteration 4 — Human semantic-grounding review path

### Problem found

The system had strong structural grounding checks, but there was no standard workflow for a person to inspect the exact
claim↔citation pairs and record whether the evidence semantically supports the claim. Without that workflow,
`semantic_citation_precision = null` was honest but not actionable.

### Improvements made

- Added `grounding-review-export`, which creates a local-only CSV from the committed golden queries.
- The CSV includes the claim, citation metadata, source locator, and runtime evidence excerpt, but every `human_label`
  starts blank.
- Added `grounding-review-score`, which accepts only `supported`, `contradicted`, or `insufficient_evidence` and ignores
  blank rows.
- `make evaluate` now reads the review file when present, but still reports semantic precision as `null` when no human
  labels exist.
- The runtime CSV stays under ignored `artifacts/evaluation/`, so evidence excerpts are not added to the public repo.

### Operational verification

The current 20-query export produced **99** claim/evidence pairs. All **99** human labels were blank. The scorer reported
0 reviewed pairs, 0.0 review coverage, semantic support precision `null`, and status `awaiting_human_review`.

### Scores after iteration 4

| Dimension | Score / 10 | Change from prior iteration |
| --- | ---: | ---: |
| Engineering correctness | 9.0 | 0.0 |
| Retrieval quality | 8.6 | 0.0 |
| Research integrity | 9.4 | +0.4 |
| Workflow usefulness | 8.7 | +0.1 |
| Operational maturity | 8.5 | +0.3 |

Overall: **8.9 / 10**

### Next review priority

Reduce repeated local-model initialization and improve service observability: cache expensive embedding/reranker model
instances per process, expose retrieval/provider health, and measure query latency without weakening the no-key path.

## Iteration 5 — Model lifecycle and retrieval observability

### Problems found

1. Provider factories created new FastEmbed/reranker wrapper instances per request, so each wrapper could lazily create
   its own ONNX backend instead of reusing one process-level model session.
2. Retrieval readiness required manual DB inspection; there was no API view of which provider/model vectors actually
   existed.
3. The HNSW database default and the application's per-query `strict_order` policy could be confused if surfaced as a
   single setting.
4. Retrieval quality was measured, but interactive latency had no repeatable local engineering baseline.

### Improvements made

- Embedding and cross-encoder factories now cache instances by model for the life of the API process.
- Lazy loading is preserved: health checks and imports do not load model weights merely by constructing the app.
- Added `/api/v1/retrieval/health` with stored provider/model embedding counts and separate database-default vs.
  application vector-query HNSW policy.
- Added `benchmark-retrieval`, `make benchmark-local`, and `make benchmark-fastembed`.

### Measured local latency

Warm hybrid retrieval over five representative queries, repeated three times (15 timed samples):

| Provider | Median | p95 | Min | Max |
| --- | ---: | ---: | ---: | ---: |
| `local_hash` | 11.6 ms | 14.7 ms | 7.6 ms | 14.7 ms |
| FastEmbed MiniLM | 32.5 ms | 37.2 ms | 30.8 ms | 37.2 ms |

FastEmbed is roughly three times slower on this laptop, but its measured relevance advantage remains substantial and
the observed warm latency is still interactive for a personal research workbench. The numbers are machine-specific
and are not published as deployment guarantees.

### Scores after iteration 5

| Dimension | Score / 10 | Change from prior iteration |
| --- | ---: | ---: |
| Engineering correctness | 9.2 | +0.2 |
| Retrieval quality | 8.6 | 0.0 |
| Research integrity | 9.4 | 0.0 |
| Workflow usefulness | 8.7 | 0.0 |
| Operational maturity | 9.0 | +0.5 |

Overall: **9.0 / 10**

### Next review priority

Improve the default search experience so a user does not need to understand embedding backfill state. Add an `auto`
semantic-provider mode that selects the higher-quality neural index only when the exact configured model is installed
and fully represented in the local corpus, otherwise falling back to `local_hash` transparently.

## Iteration 6 — Coverage-gated automatic semantic provider

### Problem found

The higher-quality neural index was available and fully backfilled, but Library search still defaulted to `local_hash`.
Choosing FastEmbed required the user to understand provider installation and index state. Simply making FastEmbed the
hard default would break fresh installs or partial backfills by searching an incomplete index.

### Improvements made

- Added `semantic_provider=auto` and made it the Library/API default.
- Auto selection checks the exact configured FastEmbed model, package availability, canonical paper count, and matching
  embedding count.
- FastEmbed is selected only at complete corpus coverage; partial or empty states fall back to `local_hash`.
- Explicit user selection (`local_hash` or `fastembed`) is never overridden.
- Search responses expose requested provider, actual provider, and the selection reason.
- Retrieval health exposes the current auto-selected provider and reason.
- Research Question recommendations reuse the same centralized auto-selection rule.

### Operational verification

The current local corpus has 529 canonical papers and 529 matching FastEmbed/MiniLM embeddings. Retrieval health
reported `auto_selected_provider=fastembed` with reason `complete_fastembed_corpus_coverage`, and an HTTP hybrid search
requested with `semantic_provider=auto` returned FastEmbed as the actual provider. Unit tests also verify that 528/529
coverage falls back to `local_hash`.

### Scores after iteration 6

| Dimension | Score / 10 | Change from prior iteration |
| --- | ---: | ---: |
| Engineering correctness | 9.3 | +0.1 |
| Retrieval quality | 8.8 | +0.2 |
| Research integrity | 9.4 | 0.0 |
| Workflow usefulness | 9.1 | +0.4 |
| Operational maturity | 9.2 | +0.2 |

Overall: **9.2 / 10**

### Next review priority

Audit the highest-frequency UI journeys for “looks implemented but does not complete the action” gaps. Start with
Library → Add to Compare, Saved Search → Research Question, citation snowball → reading queue, and import → detail.

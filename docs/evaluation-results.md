# Evaluation Results

This project deliberately uses a **small manually curated evaluation set**. The current numbers are engineering baselines for this 529-paper seed corpus, not evidence that the retrieval stack will generalize to a larger academic collection.

## Retrieval set

- 20 AI × MOT research queries are committed in `evaluation/golden_queries.json`.
- Each query has one or more manually selected relevant OpenAlex work IDs based on title/abstract relevance to the intended research question.
- The labels cover all six research axes.
- Retrieval is evaluated independently as PostgreSQL lexical search, pgvector semantic search, and reciprocal-rank-fused hybrid search.

## Results — 2026-08-23

| Retrieval mode | Mean Recall@5 | Mean nDCG@10 | MRR@10 |
| --- | ---: | ---: | ---: |
| Lexical | 0.3750 | 0.4638 | 0.4110 |
| Vector | 0.3833 | 0.3901 | 0.4336 |
| Hybrid | **0.7250** | **0.6652** | **0.6875** |

These values were produced by `research-lab evaluate` against the live 529-paper local corpus. The raw run report is written to `artifacts/evaluation/retrieval-evaluation.json` and is intentionally not committed because runtime artifacts are kept outside Git.

## Interpretation

The hybrid baseline currently recovers substantially more of the small manually labeled set than either retrieval leg alone. That supports keeping lexical and semantic retrieval separate and fusing ranks rather than replacing one with the other.

It is **not** evidence that the local embedding model is production quality. The no-key embedding provider is a deterministic `local_hash` implementation used only so pgvector behavior, hybrid ranking, evaluation plumbing, and the UI can be exercised without paid API credentials.

## Remaining evaluation work

Retrieval quality is only one part of the product. Before generated research synthesis can be treated as reliable, the following must also be measured on human-reviewed outputs:

- citation precision;
- claim-to-evidence coverage;
- unsupported claim rate;
- evidence polarity correctness for supporting vs. contradicting claims;
- duplicate-paper merge accuracy on a curated duplicate set;
- ingestion idempotency and provider retry behavior.

The repository includes automated tests for ingestion idempotency foundations, retry behavior, RRF fusion, and evaluation metric calculations. Claim-level metrics are reported only after evidence-linked generated outputs exist; no placeholder scores are invented.

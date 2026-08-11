# Evaluation Results

This project deliberately uses a **small manually curated evaluation set**. The current numbers are engineering baselines for this 529-paper seed corpus, not evidence that the retrieval stack will generalize to a larger academic collection.

## Retrieval set

- 20 AI × MOT research queries are committed in `evaluation/golden_queries.json`.
- Each query has one or more manually selected relevant OpenAlex work IDs based on title/abstract relevance to the intended research question.
- The labels cover all six research axes.
- Retrieval is evaluated independently as PostgreSQL lexical search, pgvector semantic search, and reciprocal-rank-fused hybrid search.

## Results — 2026-08-23

| Retrieval mode | Mean Recall@5 | Mean Recall@10 | Mean nDCG@10 | MRR@10 |
| --- | ---: | ---: | ---: | ---: |
| Lexical | 0.3750 | 0.7750 | 0.4638 | 0.4110 |
| Vector (`local_hash`) | 0.3833 | 0.5083 | 0.3901 | 0.4336 |
| Hybrid (`local_hash` + RRF) | **0.7000** | **0.7833** | **0.6554** | **0.6875** |

These values were produced by `research-lab evaluate` against the live 529-paper local corpus. The raw run report is written to `artifacts/evaluation/retrieval-evaluation.json` and is intentionally not committed because runtime artifacts are kept outside Git.

## Interpretation

The hybrid baseline currently recovers substantially more of the small manually labeled set than either retrieval leg alone. That supports keeping lexical and semantic retrieval separate and fusing ranks rather than replacing one with the other.

`local_hash` remains a deterministic engineering baseline used to exercise the pgvector and hybrid contracts without
model downloads. v0.3 additionally evaluates the optional local neural provider
`fastembed` + `sentence-transformers/all-MiniLM-L6-v2` using the exact same relevance labels.

| Provider | Retrieval mode | Mean Recall@5 | Mean Recall@10 | Mean nDCG@10 | MRR@10 |
| --- | --- | ---: | ---: | ---: | ---: |
| `local_hash` | Vector | 0.3833 | 0.5083 | 0.3901 | 0.4336 |
| `fastembed` MiniLM | Vector | **0.6083** | **0.7500** | **0.5978** | **0.6573** |
| `local_hash` | Hybrid | 0.7000 | 0.7833 | 0.6554 | 0.6875 |
| `fastembed` MiniLM | Hybrid | **0.8083** | **0.9583** | **0.8120** | **0.8196** |

The neural provider improves every tracked metric on this 20-query set. This is useful evidence for selecting a local
semantic backend for this corpus, but the evaluation set is still too small to support a broad claim that MiniLM is
optimal for AI × MOT literature retrieval.

The multi-provider HNSW query path enables pgvector `strict_order` iterative scans before vector retrieval. This is
important because provider/model filters are applied after an approximate HNSW scan; without iterative scanning,
adding a second embedding provider can reduce or destabilize filtered recall. Two consecutive full evaluation runs
after this change produced identical metrics.

The optional FastEmbed cross-encoder reranker was also measured against the **same top-30 neural-hybrid candidate
pool** for every query. RRF order scored Recall@5 0.8083, Recall@10 0.9583, nDCG@10 0.8120, MRR@10 0.8196; the
cross-encoder reduced those to 0.7417, 0.8833, 0.7181, and 0.7642. It therefore remains an explicit experimental
option and is not recommended as the default.

## Remaining evaluation work

Retrieval quality is only one part of the product. Before generated research synthesis can be treated as reliable, the following must also be measured on human-reviewed outputs:

- citation precision;
- claim-to-evidence coverage;
- unsupported claim rate;
- evidence polarity correctness for supporting vs. contradicting claims;
- duplicate-paper merge accuracy on a curated duplicate set;
- ingestion idempotency and provider retry behavior.

The repository includes automated tests for import parsing, PDF chunk/page-locator foundations, ingestion retry behavior, RRF fusion, comparison/gap grounding policy, chat grounding, and evaluation metric calculations. Operational integration journeys additionally verify DOI re-import idempotency and a permitted temporary PDF through full-text search and Chat citation. No placeholder semantic-precision score is invented.

## Grounding structure — 2026-08-23

The same 20 golden queries were also passed through the no-key evidence-grounded chat baseline.

| Metric | Result |
| --- | ---: |
| Structural claim-to-evidence coverage | **1.0000** |
| Structural unsupported-claim rate | **0.0000** |
| Invalid citation indexes | **0** |
| Semantic citation precision | **Not yet human-scored** |

These structural metrics answer a narrow engineering question: does every assertive paragraph point to a valid citation object? They do **not** establish that a citation semantically entails the paragraph. Semantic citation precision still requires human claim-to-source review, especially after a real LLM provider is enabled.

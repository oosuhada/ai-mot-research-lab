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

# Evaluation Plan

## Evaluation philosophy

The first evaluation asset is deliberately a **small manually curated evaluation set**. It is designed to catch retrieval and grounding regressions, not to support broad claims about scholarly-search quality.

The evaluation suite separates four questions:

1. Can ingestion normalize and merge records safely?
2. Can retrieval surface manually judged relevant literature?
3. Can generated comparison/gap content point to real supporting evidence?
4. Does the system expose uncertainty instead of inventing support?

## Golden queries

The repository contains 20 domain-specific golden queries across all six research axes. Each query records:

- a stable query ID
- English query text and optional Korean framing
- research axis
- expected concepts/filters
- a manually judged set of relevant paper identifiers when available
- a judgment status when the corpus is still too small to assign stable relevance labels

The initial set covers topics such as AI adoption complementarities, productivity, human-AI decision-making, dynamic capabilities, smart manufacturing, predictive maintenance, governance, human oversight, and enterprise agents.

## Retrieval metrics

For each golden query with relevance judgments, report lexical, vector, and hybrid runs separately.

### Recall@k

The fraction of known relevant papers retrieved in the first `k` results. Initial reports use `k ∈ {5, 10, 20}` where enough judgments exist.

### nDCG@k

Normalized Discounted Cumulative Gain captures rank quality when judgments have graded relevance. Binary judgments are supported but marked as such.

### Coverage caveat

If the seed corpus does not contain a judged relevant paper, that query is reported as a corpus-coverage limitation instead of scoring retrieval as though the missing record were retrievable.

## Grounding metrics

### Citation precision

Sample substantive generated claims and manually verify whether each attached paper/chunk actually supports the claim. Report supported citations divided by inspected citations.

### Claim-to-evidence coverage

Fraction of substantive generated claims that have at least one evidence link or an explicit `insufficient_evidence` state.

### Unsupported claim rate

Fraction of substantive claims presented as supported even though no valid evidence link exists or the cited evidence does not support the claim.

The target invariant for automated tests is stricter than the human metric: **no generated evidence object may be serialized as `supported` without at least one evidence relation**.

## Data-pipeline correctness tests

- DOI normalization and duplicate merge.
- OpenAlex/S2/arXiv identifier merge precedence.
- Refusal to silently merge conflicting strong identifiers.
- Idempotent re-ingestion of the same OpenAlex page.
- Snapshot creation for mutable citation/OA fields.
- Checkpoint advances only after successful transaction.
- Retry on 429 and transient 5xx responses.
- No retry on deterministic 4xx validation failures.
- Referential integrity for evidence, paper authors/topics, and comparison records.
- Personal workflow deletion can cascade without deleting scholarly provenance.

## Evaluation execution

The API package exposes a CLI that runs retrieval evaluation against the current local database and writes a timestamped local report under `artifacts/evaluation/`. Generated metric files are ignored by Git so results cannot accidentally become stale portfolio claims.

A short committed `docs/evaluation-results.md` summarizes the most recent deliberately run evaluation, including corpus size, judgment count, provider/embedding mode, metric values, and limitations.

## Exit criteria for MVP claims

The README may say a capability is implemented only when its smoke/unit/integration tests pass. It may show numeric retrieval/grounding results only when the evaluation command has actually been run on the described corpus. Missing provider keys, missing Docker, or a small judgment set must be reported as limitations rather than replaced with invented numbers.


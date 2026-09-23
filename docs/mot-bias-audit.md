# MOT broad-expansion bias audit

Date: 2026-09-23

This audit records where the legacy AI scope is a hard requirement, where it is a default or
preset, and where it is merely descriptive. It should be updated as the broad-MOT rollout
changes additional paths.

| Path / function | Legacy behavior | Bias type | Broad-MOT treatment |
| --- | --- | --- | --- |
| `taxonomy.py::text_matches_axis` | Requires both AI terms and axis context (`has_ai and has_context`) | hard collection/classification requirement | Preserved for legacy `research_axis`; not used as the broad-MOT gate |
| `taxonomy.py::RESEARCH_AXES` | Six AI-centered axes, including AI-required technology/innovation query | legacy taxonomy | Preserved as presets/compatibility labels |
| `corpus_expansion.py` | Uses legacy axes and `text_matches_axis`; default starts at 2017 | collection policy | Preserved as `openalex_expansion`; new `openalex_mot_pilot` has independent state and foundation lane |
| `corpus_bulk_bootstrap.py` | Bulk bootstrap is driven by legacy AI axes | collection policy | Preserved for regression; not reused as the first broad-MOT collector |
| `daily_discovery.py` | Discovers recent papers by legacy AI axes | scheduled default | Still legacy; future broad-MOT discovery should be a separate profile rather than silently changing this job |
| `corpus_audit.py` | Relevance checks inherit legacy scope assumptions | audit policy | Not treated as proof of broad-MOT coverage |
| `opencitations_meta.py` | Uses legacy relevance logic for broad metadata ingestion | collection policy | Not yet converted; broad-MOT pilot uses OpenAlex first |
| `ingestion/service.py::_upsert_record` | `axis=None` previously scanned every legacy subaxis | unintended side effect | Fixed: legacy subaxis inference only runs when a legacy axis is explicitly supplied |
| `evaluation/golden_queries.json` | 20 AI-centered retrieval queries | evaluation bias | Preserved as AI regression set; separate `mot_broad_queries.json` added |
| `retrieval.py::SearchFilters` | `axis` filters only `research_axis` | search surface | Added MOT problem/context/unit/theory/AI-role topic filters while retaining `axis=` |
| paper detail topic display | Focused on legacy axes/subaxes and methodology | UI default | Adds broad-MOT dimensions plus versioned automatic evidence |
| home/sidebar/layout/config | Product named AI × MOT Research Lab | product default | Primary branding widened to MOT Research Explorer; legacy AI areas remain available |
| opportunity/gap/question wording | Some fallback text assumes AI-scoped corpus | generated-language default | Identified; not all wording is changed in v1. Counts must not be interpreted as research gaps |
| `corpus_intelligence.py::_why_it_matters` | fallback phrase says `scoped AI × MOT corpus` | descriptive fallback | Identified for follow-up; does not change ingestion eligibility |

## Current interpretation

The pre-expansion corpus cannot be interpreted as a neutral sample of the MOT field because
its principal OpenAlex collection paths explicitly required AI. Very small pre-existing
counts for non-AI topics therefore indicate corpus-policy coverage, not the prevalence of
those topics in scholarship.

The broad-MOT implementation intentionally does not replace one topical default with another
(for example, energy). Energy is a `technology_context`; adoption, R&D investment or
technology transfer are `mot_problem` values. AI is separately represented by its role.

## Remaining audit work

Before calling the broad rollout complete, scheduled discovery, citation/meta expansion,
recommendation/opportunity prompts, saved-search compatibility, and evaluation reports must
be rechecked under production data. Any low-count area should be reported as `DB coverage
low` until external search and citation-neighbor checks support a stronger claim.

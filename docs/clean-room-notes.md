# Clean-room Notes

## Reference boundary

The prior classroom project was inspected in read-only mode solely to understand problem framing and failure/success patterns. This repository was initialized as an empty Git repository at a separate path.

No prior source code, tests, prompts, SQL, documentation prose, CSS, UI layout, assets, datasets, branding, names, or Git history are copied into this project.

## Product lessons re-derived as independent requirements

The following are problem-level observations, not copied implementation details:

- A chat-first experience makes it difficult to audit how a literature conclusion was formed.
- “Research gap” generation is unsafe when supporting and contradicting evidence are not first-class data.
- Academic metadata retrieval should be separable from web search and from full-text processing.
- Domain scope matters more than adding more agent personas for a personal research workflow.
- Provider failures and rate limits must not make the canonical corpus unrecoverable.
- Evaluation needs to test retrieval, citation support, and ingestion correctness rather than only whether a chat endpoint returns text.

Those observations were independently converted into the provenance-aware schema, constrained six-axis corpus, hybrid retrieval contract, evidence-claim model, and editable gap canvas documented in this repository.

## Audit practice

- The prior project path is never written to and is not mentioned in public repository documentation.
- New repository commits start from this greenfield initialization.
- Before public push, scans check for secrets, PDFs, large database artifacts, and accidental references to classroom branding or team-member names.


# Data Sources, Terms, and Operational Rules

This document records the official-source checks used for the MVP design. It is not legal advice. Terms and limits can change, so provider adapters keep rate/policy settings explicit instead of hard-coding assumptions throughout the application.

Last reviewed: **2026-08-23**

## OpenAlex — primary metadata source

Official documentation:

- https://developers.openalex.org/
- https://developers.openalex.org/guides/authentication

Current operational facts checked on 2026-08-23:

- OpenAlex describes its complete dataset as CC0.
- API access is freemium. Current documentation gives no-key requests a $0.10/day allowance and a free API key a $1/day allowance.
- The documentation currently gives the free-key examples of up to 10,000 list/filter calls, 1,000 search calls, and 100 content-download calls per day, depending on endpoint pricing.
- A key is therefore recommended for scheduled corpus refreshes, but the MVP can perform a small seed ingestion within the no-key allowance.

Project rules:

- OpenAlex is the first-write source for the seed corpus.
- Store `source=openalex`, work ID, retrieval time, source license, and normalized source URL.
- Cache records and use cursor/page checkpoints rather than repeating queries.
- Do not treat OpenAlex OA URLs as automatic permission to redistribute a PDF; inspect the actual location/license first.

## Crossref — DOI/publication and update enrichment

Official documentation:

- https://www.crossref.org/documentation/retrieve-metadata/rest-api/
- https://www.crossref.org/documentation/retrieve-metadata/rest-api/access-and-authentication/
- https://www.crossref.org/documentation/retrieve-metadata/rest-api/text-and-data-mining/

Current operational facts checked on 2026-08-23:

- Public REST API access does not require registration.
- Crossref recommends a `mailto` parameter/User-Agent for the polite pool.
- Crossref's general pool documentation reports public/polite ceilings of 5/10 requests per second with concurrency limits of 1/3.
- Since 2025-12-01, list/query/filter requests have stricter limits: public **1 request/second** with concurrency 1; polite **3 requests/second** with concurrency 3. Single-record requests remain public 5/s and polite 10/s.
- Clients must still obey the rate-limit and concurrency headers returned by the API because operational limits can change.
- Crossref states that almost all deposited bibliographic metadata is reusable, while some abstracts can still be copyrighted.
- A full-text link in Crossref metadata does not itself guarantee access or text/data-mining permission.

Project rules:

- Use Crossref primarily for DOI normalization, publisher/venue/date/license/update enrichment.
- Default to one in-flight request and conservative pacing. For list/query enrichment, stay at or below 1 request/second unless the polite-pool response headers explicitly permit more.
- On 429, honor `Retry-After` when present and back off.
- Persist Crossref provenance independently from the OpenAlex record.

## Semantic Scholar Academic Graph — optional enrichment

Official documentation and license:

- https://api.semanticscholar.org/api-docs
- https://www.semanticscholar.org/product/api
- https://api.semanticscholar.org/license/

Current operational facts checked on 2026-08-23:

- Many endpoints are available without authentication but share a throttled unauthenticated pool.
- Semantic Scholar currently describes a typical introductory API-key limit as 1 request/second, with actual throttling subject to service conditions.
- The API license imposes use, attribution, and redistribution restrictions. Public use of Semantic Scholar data has attribution requirements, and commercial/expanded use may require separate permission.

Project rules:

- The adapter is **disabled by default** unless the user explicitly supplies a key and enables it locally after reviewing the current terms.
- Never mirror or publish bulk Semantic Scholar data from this repository.
- Persist Semantic Scholar IDs and source attribution only when enrichment is actually performed.
- The core product must remain functional without this provider.

## arXiv — preprint freshness

Official documentation and terms:

- https://info.arxiv.org/help/api/user-manual.html
- https://info.arxiv.org/help/api/tou.html

Current operational facts checked on 2026-08-23:

- Descriptive arXiv metadata is offered under CC0.
- Legacy APIs require no more than one request every three seconds and a single connection at a time.
- arXiv e-print full text remains subject to the submission's copyright/license; arXiv explicitly warns against storing and serving PDFs without permission.

Project rules:

- Use arXiv metadata to improve freshness for agentic systems and enterprise-workflow topics.
- Enforce a minimum three-second interval for legacy API requests.
- Store metadata and links by default; download/process full text only when the license permits it or the user supplied the file.

## User-provided DOI, BibTeX, RIS, CSV, and PDF

- Imported metadata receives `source=user_import` plus an import run ID and retrieval/import timestamp.
- User-owned PDFs are private local data and are excluded from Git.
- A locally provided PDF may be processed for the user's research workflow, but the application does not infer redistribution rights from possession.
- Every chunk keeps a source locator and hash so generated evidence can point back to the user's local document without committing the document itself.

## Optional local embedding runtime

This is not a scholarly metadata source, but it affects retrieval and therefore has an explicit dependency/model policy.

- FastEmbed `0.8.0`: https://pypi.org/project/fastembed/ and https://github.com/qdrant/fastembed
- `sentence-transformers/all-MiniLM-L6-v2`: https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2
- `Xenova/ms-marco-MiniLM-L-6-v2`: optional experimental cross-encoder reranker supported by FastEmbed
- FastEmbed is Apache-2.0 licensed; the selected MiniLM model card is also Apache-2.0.
- The model is downloaded only when the user explicitly backfills or selects the optional neural provider. Model files live in the machine's model cache and are not committed to this repository.
- The canonical database keeps provider/model identifiers on every embedding row so neural and deterministic baselines can coexist and be evaluated separately.
- Retrieval uses FastEmbed's query-specific path for search queries and passage/document path for papers and chunks.
- The cross-encoder is an opt-in experiment and remains disabled by default after degrading the current manually judged retrieval set.

## Explicitly prohibited collection paths

- Google Scholar scraping.
- Unauthorized crawling of DBpia, RISS, Scopus, Web of Science, publisher sites, or any service requiring rights the user does not have.
- Treating a discoverable PDF URL as permission to mirror content.
- Committing raw PDFs, private exports, API keys, or large database dumps to Git.


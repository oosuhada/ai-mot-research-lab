# Data Sources, Terms, and Operational Rules

This document records the official-source checks used for the MVP design. It is not legal advice. Terms and limits can change, so provider adapters keep rate/policy settings explicit instead of hard-coding assumptions throughout the application.

Last reviewed: **2026-08-23**

## OpenAlex — primary metadata source

Official documentation:

- https://developers.openalex.org/
- https://developers.openalex.org/guides/authentication

Current operational facts checked on 2026-08-23:

- OpenAlex describes its complete dataset as CC0.
- API access is freemium. Without a key there is a small daily allowance; a free API key raises the daily allowance to $1 worth of usage.
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
- Current documented limits are 5 requests per rate interval with one concurrent request for the public pool, and 10 with three concurrent requests for the polite pool; clients should obey the rate-limit headers returned by the API.
- Crossref states that almost all deposited bibliographic metadata is reusable, while some abstracts can still be copyrighted.
- A full-text link in Crossref metadata does not itself guarantee access or text/data-mining permission.

Project rules:

- Use Crossref primarily for DOI normalization, publisher/venue/date/license/update enrichment.
- Default to one in-flight request and conservative pacing even when higher limits are advertised.
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

## Explicitly prohibited collection paths

- Google Scholar scraping.
- Unauthorized crawling of DBpia, RISS, Scopus, Web of Science, publisher sites, or any service requiring rights the user does not have.
- Treating a discoverable PDF URL as permission to mirror content.
- Committing raw PDFs, private exports, API keys, or large database dumps to Git.


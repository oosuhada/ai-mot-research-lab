# Self-hosted deployment

The public portfolio deployment is a **read-only research demo**. The web UI hides mutation forms, and the API must independently reject shared mutations. Do not rely on UI gating as the security boundary.

## Process layout

The current self-hosted shape uses two launchd services behind a Cloudflare Tunnel:

| Service | launchd label | Bind address | Purpose |
| --- | --- | --- | --- |
| API | `com.oosu.ai-mot-research-api` | `127.0.0.1:8160` | FastAPI research API |
| Web | `com.oosu.ai-mot-research-web` | `127.0.0.1:8260` | Next.js production server |

The public web hostname maps through Cloudflare Tunnel as:

```text
research.oosu.dev -> http://127.0.0.1:8260
```

The API is intentionally **internal-only**. It does not need to be publicly exposed for the web server to function.
Production Server Components and Server Actions use the loopback API URL. There is no supported public API hostname in
the current architecture.

## Required production environment

The API launchd service must explicitly set:

```text
APP_ENVIRONMENT=production
READ_ONLY_MODE=true
```

The web launchd service should set:

```text
NODE_ENV=production
NEXT_TELEMETRY_DISABLED=1
INTERNAL_API_BASE_URL=http://127.0.0.1:8160
```

Do not set `NEXT_PUBLIC_API_BASE_URL` for this deployment. The application API client uses `INTERNAL_API_BASE_URL`
server-side and does not need to expose an API origin to browser JavaScript.

`PUBLIC_API_HOSTS` remains available as an optional defense-in-depth guard if an API hostname is deliberately routed in
the future. It is blank by default because the current Cloudflare ingress has no API route. Production is still
independently protected by both `APP_ENVIRONMENT=production` and `READ_ONLY_MODE=true`, so the host allowlist is not a
substitute for the production write guard.

### Public API decision

As of 2026-08-23, repository search, Git history, the installed launchd services, and the Mac mini Cloudflare Tunnel
configuration show no external consumer that requires `aimot.oosu.dev`. The tunnel routes only
`research.oosu.dev -> 127.0.0.1:8260` for this application, while FastAPI listens on `127.0.0.1:8160`. Therefore
`https://aimot.oosu.dev/health` returning `404` is intentional architecture, not a service outage. Do not add a Tunnel
route merely to make that hostname return 200.

If an external API consumer is introduced later, treat that as an architecture change requiring authentication, an
explicit CORS allowlist, rate limiting, the production read-only guard, a health endpoint, and a documented Tunnel
route before traffic is accepted.

Do not commit launchd plist files containing user-specific home paths, secrets, tunnel credentials, or other host-private configuration. Keep those values on the host and use this document as the reproducible contract.

## Scheduled corpus intelligence

Several host-private launchd jobs may run beside the read-only API. Database writers remain controlled maintenance
tasks; they do not weaken the public HTTP write guard. The analytics job is read-only against PostgreSQL:

```text
research-lab discover-daily --lookback-days 3 --max-pages-per-axis 2
research-lab enrich-full-text --max-items 10 --max-pdf-bytes 30000000 --lease-minutes 20
research-lab translate-localizations --max-items 20 --max-characters 15000 --lookback-days 35
research-lab export-translation-queue --locale ko --limit 100 --output <outside-checkout-path>
research-lab translate-localization-export-gemini --input <queue.json> --output <ko.json> --ledger <ledger.json> --project <vertex-project>
scripts/run-nightly-analytics.sh
```

Schedule discovery daily after the primary corpus batch window. Schedule full-text enrichment separately with a small
batch size so PDF parsing cannot starve metadata ingestion. Translation export remains the provider-neutral fallback;
an authorized external/local translator must populate the output contract before `import-localizations` is run.

The production host may install `com.oosu.ai-mot-korean-localization` as a host-private daily launchd job, scheduled
after discovery and outside corpus/full-text/embedding writer windows. Its program calls
`scripts/run-korean-localization.sh`. The wrapper skips when another heavy writer is active. Each run calls DeepL
`/v2/usage`, spends at most 15,000 source characters, and leaves 10,000 monthly characters unused by default. DeepL
Free renews quota by account billing period but does not return the next reset timestamp in the Free usage response;
the daily usage check therefore resumes naturally after renewal instead of assuming the first day of a calendar
month. Keep `DEEPL_API_KEY` only in the host-private environment and optionally tune
`TRANSLATION_MONTHLY_RESERVE_CHARACTERS`. The API service remains `READ_ONLY_MODE=true`; this controlled worker writes
directly to PostgreSQL and does not expose a public mutation route.

### Bootstrap versus steady-state localization

Large first-time corpus construction uses a separate operator-side bootstrap path instead of increasing the recurring
DeepL allowance. `scripts/run-gemini-bootstrap-localization.sh` exports the untranslated queue from the production
host, translates that export on an authenticated operator workstation through Vertex AI, and imports only the
provenance-tagged localization JSON. The default model is `gemini-3.7-flash`, location `global`, and the wrapper uses
a deliberately conservative application-level budget ceiling of USD 15. The translator records prompt/output token usage and
estimated spend in an ignored artifact ledger; it reserves a pessimistic upper bound before submitting concurrent
requests, so parallel requests cannot collectively exceed the configured bootstrap budget. Google Cloud credentials
are not copied to the production host: the bootstrap client uses an ephemeral `gcloud auth print-access-token` token
and never stores it in the queue, output, ledger, localization provenance, or logs.

The production host may temporarily run `scripts/run-gemini-incremental-localization.sh` through
`com.oosu.ai-mot-gemini-incremental-localization` while initial localization coverage is being filled. The checked-in
launchd definition runs at load and every 7,200 seconds. The wrapper creates an ignored seven-day execution window on
its first run, becomes a no-op after that expiry, exports at most 64 abstract-ready papers that have no localization row
for `ko`, and skips whenever corpus expansion, full-text enrichment, embedding backfill, or the DeepL localization job
is already running. It reuses the same `artifacts/gemini-localization/ledger.json` and USD 15 ceiling rather than
starting a second budget. The host must have an authenticated `gcloud` CLI with Vertex AI access to the ledger's billed
project. `CLOUDSDK_PYTHON` is pinned in the launchd definition so non-interactive macOS sessions do not fall back to an
unsupported system Python.

This launchd worker is intentionally temporary, not a new steady-state translation policy. Once its seven-day window
expires or its shared Gemini budget is exhausted, the existing daily DeepL worker remains the steady-state translation
path and continues to obey the monthly character reserve.

The corpus follows the same phase boundary. While `corpus_count < target_total`, the resumable OpenAlex expansion job
continues its high-throughput half-hour cadence. With `OPENALEX_API_KEY` configured, `scripts/run-corpus-expansion.sh`
uses `bootstrap-corpus-bulk`. On first use it imports the existing `corpus-expansion/state.json` per-slice page
checkpoint so already-downloaded relevance pages are not fetched again. It continues those deterministic year slices
through basic page 100; only a slice that exhausts that range before the 100k target falls through to cursor-paged
`title_and_abstract.search`. It checkpoints after every API page and writes the raw page under
`artifacts/corpus-bulk-bootstrap/pages/`, and imports through the existing canonical/provenance pipeline only after the
local transparent taxonomy gate accepts the record. The default scheduled batch is 50 search requests (up to 5,000
candidates), but a persisted UTC-day ledger stops further requests at 480 search calls/day by default so the existing
authenticated content allowance still has budget headroom. Tune the burst with `AI_MOT_BULK_MAX_REQUESTS` and the
daily ceiling with `AI_MOT_BULK_DAILY_REQUEST_CAP`. Without a key the wrapper falls back to the older two-page
basic-paging batch.

The bulk state lives at `artifacts/corpus-bulk-bootstrap/state.json`, separately from the legacy
`artifacts/corpus-expansion/state.json`; deployment and recovery must preserve both. `research-lab corpus-bulk-status`
reports the cursor checkpoint. The worker also holds a non-blocking host file lock so a manual invocation cannot race
the launchd invocation; cumulative counters are reconciled from `ingestion_runs` so an interrupted or previously
overlapping process cannot make progress statistics regress. `scripts/run-steady-discovery.sh` checks the overall
corpus target and does nothing
during bootstrap. Once the target is reached, the wrapper switches to bounded recent-publication discovery plus
corpus-intelligence refresh; it can then be scheduled once daily as the stable maintenance path.

OpenAlex ingestion itself now creates or refreshes the full-text queue row in the same database transaction as each
resolvable paper. Full-text eligibility therefore no longer depends on a later whole-corpus intelligence refresh.
DOI, arXiv, and OpenAlex identifiers are all canonical identity keys during ingestion, preventing an OpenAlex record
for an already-known arXiv paper from attempting a duplicate insert.

`discover-daily` must not receive or modify the corpus-expansion state path. `enrich-full-text` processes queue rows
marked `rights_status=open_access` or `unknown`. Unknown rows never use an unverified publisher URL: the worker first
asks the configured official resolvers and promotes the row to open access only after one returns an explicit OA
PDF/XML candidate. It stores source/license provenance, never bypasses a paywall, and does not mark the stored file
redistributable by default.

The production host may also install `com.oosu.ai-mot-full-text-enrichment` as a host-private launchd job. The
recommended cadence is minutes `5,15,25,35,45,55` of every hour (10-minute cadence, avoiding the embedding job at
minute 20). Its program should call `scripts/run-full-text-enrichment.sh`; that wrapper exits without work whenever
the corpus-expansion or embedding-backfill launchd job is actively running. The worker claims each queue row with a
bounded lease (`worker_id`, `claimed_at`, `lease_expires_at`), and a later worker automatically recovers expired
`processing` leases rather than leaving rows permanently stuck. On upgrade, OA rows left in `failed` by the legacy
worker are requeued only when they have no `full_text_source_attempts` history, giving them one path into the new
resolver without repeatedly reopening failures already classified by the new worker.

The wrapper starts two workers by default, with 10 queue items per worker. PostgreSQL `FOR UPDATE SKIP LOCKED`
claims keep the workers on separate papers. Operators can tune the bounded concurrency with
`FULL_TEXT_ENRICHMENT_WORKERS` (1–4) and `FULL_TEXT_ENRICHMENT_MAX_ITEMS_PER_WORKER` (1–50); increase these only after
checking host CPU, run duration, resolver rate limits, and the recent completion/failure mix.

Full-text source failures are source-specific. `403`, `404`, non-PDF responses, timeouts, extraction failures, and
other failure kinds are recorded in `full_text_source_attempts` with source URL, domain, and publisher. The worker
does not retry a source URL after a terminal source failure; instead it refreshes the paper's current OpenAlex OA
locations and tries other explicitly open-access PDF locations. Domain history also informs routing: after at least
three observations, domains at or below a 25% success rate are deprioritized and OpenAlex alternatives are resolved
before the direct publisher URL is attempted. Candidate ranking uses a smoothed success score so one-off outcomes do
not dominate. `source_exhausted` items persist for future OA-location changes; unchanged OpenAlex location sets back
off from 24 hours to 3 days and then 7 days rather than consuming a queue slot every day. Inspect aggregate behavior
and each domain's `routing` decision with:

```bash
research-lab full-text-source-stats --limit 20
```

OpenAlex remains the primary source resolver. Single-work API lookups are used to refresh `best_oa_location`,
`primary_location`, and all OA `locations`; the request uses `select` so unrelated work metadata is not transferred.
If `OPENALEX_API_KEY` is configured, the worker also considers the official `content.openalex.org` PDF and
machine-readable GROBID/TEI XML archive via the work's `has_content` / `content_urls` fields. The API key is passed
only as a request parameter and is never stored in queue provenance, source-attempt URLs, or application logs.
OpenAlex content keeps the document's original copyright/license; local ingestion therefore remains
non-redistributable unless the recorded license says otherwise. `OPENALEX_CONTENT_DAILY_LIMIT` defaults to 40
combined authenticated content-file attempts per UTC day. Together with the scheduled metadata expansion below,
this keeps the default free-key workload below the $1/day budget with headroom; set it lower to disable or further
constrain paid content access. A successful
authenticated archive URL is evidence provenance only and never replaces the public `paper.pdf_url` shown to users.

The corpus-expansion launchd job should call `scripts/run-corpus-expansion.sh` at minutes `0` and `30`. The wrapper
adapts to the OpenAlex budget automatically: without a key it processes only 2 basic-paging search pages per run
(about 96 search requests/day); with `OPENALEX_API_KEY` configured it uses the cursor bulk path described above and
enforces its persisted daily request ceiling. It also skips a run if full-text enrichment or embedding backfill is
active, so increasing metadata throughput does not create uncontrolled writer
overlap on the Mac mini.

DOI-matched biomedical and life-sciences papers also use Europe PMC's official REST service as a second full-text
resolver. The worker searches only `OPEN_ACCESS:Y` records, resolves the PMCID, retrieves `/{PMCID}/fullTextXML`,
stores the JATS XML privately with license/source provenance, and chunks that structured text directly. It does not
crawl the Europe PMC website or automate the HTML/PDF reader; automated retrieval stays on Europe PMC's documented
REST Open Access subset. XML evidence can therefore complete a queue item even when the publisher PDF is blocked,
without replacing the paper's public PDF URL with an XML API endpoint.

OpenAlex ingestion also recovers arXiv identifiers from arXiv landing/PDF URLs in the work's locations and preserves
the normalized value as `papers.arxiv_id`. When present, the worker adds the deterministic
`https://arxiv.org/pdf/{arxiv_id}` endpoint as a high-priority public repository candidate before falling back to
low-yield publisher URLs. Version suffixes are removed when normalizing arXiv identifiers so repeated OpenAlex
refreshes update one canonical paper rather than creating version-specific identities.

The resolver registry also supports the following official channels:

- **Unpaywall v2**: DOI lookup using `UNPAYWALL_EMAIL` (or `CROSSREF_MAILTO` as fallback). It accepts only records
  explicitly marked `is_oa=true` and only `url_for_pdf` locations. Unpaywall does not issue API keys; use one stable
  operational contact email and do not rotate identities to evade its published limit.
- **CORE API v3**: DOI-exact output search using `CORE_API_KEY` as a Bearer token. The original `downloadUrl` is
  preferred, followed by explicit source PDF URLs, with the authenticated official `/outputs/{id}/download` endpoint
  retained as the final fallback. Request credentials are excluded from candidate repr, provenance, and error logs.
- **bioRxiv / medRxiv**: DOI lookup through `api.biorxiv.org`; the newest numeric version is selected and its official
  JATS XML is preferred before the matching repository PDF.
- **ChemRxiv**: DOI lookup through the Cambridge Open Engage public API; only the returned PDF asset and recorded
  license are accepted.

Every downloaded version now keeps its resolver-specific source kind (`arxiv_pdf`, `unpaywall_best_oa_pdf`,
`core_download_url_pdf`, `biorxiv_jats_xml`, `medrxiv_pdf`, `chemrxiv_pdf`, and so on) instead of being mislabeled as
OpenAlex. Terminal URL failures remain deduplicated through `full_text_source_attempts`, while unchanged resolver sets
use the existing 24-hour / 3-day / 7-day backoff.

Legacy OA PDF versions created before extraction provenance was recorded can be repaired idempotently from the
stored private blob with:

```bash
research-lab backfill-full-text-provenance --limit 100
```

This command verifies the stored SHA-256 and reruns pypdf extraction only to reconstruct extraction metadata. It does
not invent a historical source URL: if the old version did not record one, `source_url` stays null and the metadata
explicitly records that the backfill did not copy the current `paper.pdf_url` into historical provenance.
Inspect installed plist paths, environment, last exit status, and logs on the actual host before enabling any
schedule.

Schedule the DuckDB snapshot after discovery and ingestion. It contains aggregate trends only and atomically replaces
its target; PostgreSQL remains the source of truth. Install the API with both production extras before enabling it:

```bash
apps/api/.venv-prod/bin/pip install -e 'apps/api[local-embeddings,analytics]'
```

## PostgreSQL search observability

Migration `0004` creates `pg_trgm`, `pg_stat_statements`, the stored `paper_chunks` FTS vector, and matching GIN
indexes. `pg_stat_statements` also requires a one-time host setting and database restart. Inspect the current setting
first, then apply it during a quiet ingestion window:

```sql
SHOW shared_preload_libraries;
ALTER SYSTEM SET shared_preload_libraries = 'pg_stat_statements';
```

Restart only the PostgreSQL container, wait for `pg_isready`, run `alembic upgrade head`, and verify:

```sql
SELECT extname FROM pg_extension WHERE extname IN ('vector', 'pg_trgm', 'pg_stat_statements');
SELECT count(*) FROM pg_stat_statements;
```

Use `research-lab benchmark-retrieval --provider fastembed --repeats 20` for application P50/P95/P99 and
`research-lab search-statement-stats` for cumulative database mean/min/max and call counts. Never infer percentiles
from the cumulative PostgreSQL aggregates.

## Safe deployment procedure

Before pulling on the deployment host, inspect the checkout and preserve runtime artifacts:

```bash
git status --short
git diff
git rev-parse HEAD
git fetch origin main
git rev-parse origin/main
git pull --ff-only origin main
```

Do **not** run `git clean -fd` on the deployment checkout. Runtime jobs may keep untracked state under paths such as `artifacts/corpus-expansion/`.

When a deployment contains an Alembic schema migration, make a same-major PostgreSQL `pg_dump` safety backup before
`alembic upgrade head`. The `0008` research-workflow migration adds user-workspace tables and literature-tier columns;
it does not rewrite corpus records, but the backup is still mandatory before applying it to the live database.

For the web build, ensure the shell uses the same supported Node 22 installation as the launch agent before running:

```bash
cd apps/web
npm run build
```

If API code changed, restart the API launchd service. Restart the web launchd service after a successful production build. Inspect the installed plist and current `launchctl` state before restarting rather than assuming a host-specific path or domain target.

## Post-deploy verification

Verify loopback services first:

```text
GET http://127.0.0.1:8160/health -> 200
GET http://127.0.0.1:8260/ -> 200
GET http://127.0.0.1:8160/api/v1/corpus/coverage -> 200
GET http://127.0.0.1:8160/api/v1/whats-new -> 200
GET http://127.0.0.1:8160/api/v1/research-opportunities -> 200
```

Then verify the API write guard from the deployment host:

```text
POST /api/v1/saved-searches -> 403
```

Expected behavior is a public read-only message. Evidence Chat remains an intentional read-only exception, so an empty Chat POST should reach request validation rather than the mutation guard:

```text
POST evidence-chat endpoint with empty body -> 422 validation
```

Finally, verify `https://research.oosu.dev/` with a real browser. Because the app uses Next.js streaming, wait for final page content markers after `domcontentloaded`; do not use `networkidle` as the sole readiness signal.

The absence of an `aimot.oosu.dev` API route is expected. Do not report its `404` as a deployment failure while this
internal-only policy is in effect.

## Deployment invariants

- candidate evidence is not a conclusion;
- system inference is not an author-reported paper claim;
- insufficient evidence stays explicit;
- private PDF processing never implies redistribution permission;
- attaching a citation does not prove semantic entailment;
- only explicitly reviewed Research Cards feed research-question synthesis;
- proposal readiness measures workflow completeness, not research quality or novelty;
- the public portfolio deployment remains read-only at both UI and API layers.

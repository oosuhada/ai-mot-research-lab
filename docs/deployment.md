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
- the public portfolio deployment remains read-only at both UI and API layers.

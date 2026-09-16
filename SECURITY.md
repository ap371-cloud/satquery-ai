# Security

## Reporting a vulnerability

Please do **not** open a public issue for security problems. Report them
privately to the repository owner (see `LICENSE` for the copyright holder) with
as much detail as possible:

- Affected endpoint or component
- Steps to reproduce
- Any relevant logs (redacted of secrets)
- Suggested impact and, if known, a fix

You will receive an acknowledgement within a few days and a timeline for the fix.

## Scope

SatQuery AI is a single-user, publicly accessible demo. It does **not** ship
production-grade authentication or per-user multi-tenancy. Known boundaries and
how this codebase handles them are described below.

### Authentication / authorization

There is no login, session, or per-user isolation. Anyone who can reach the
deployment can upload datasets, run analyses, and read stored results. Do not
attach this service to accounts, billing, or private imagery without adding an
auth layer (e.g. a gateway, Vercel Functions protection, or an OIDC front-door
such as Vercel's Authentication middleware).

### Rate limiting

- Every costly endpoint is rate-limited per client IP: uploads, analysis
  creation, `/api/v1/plan`, `/api/v1/query/parse`, `/api/v1/demo/load`, and
  dataset statistics.
- Defaults are documented in `backend/.env.example` (`SATQUERY_RATE_*`). Limits
  are validated before any expensive work starts.
- On Vercel the backend runs as multiple container instances that share no
  local state. For **cross-instance** limits, set `UPSTASH_REDIS_REST_URL` /
  `UPSTASH_REDIS_REST_TOKEN` (Upstash Redis REST; no extra pip dependency).
  Without those variables a per-instance in-memory sliding window applies.

### Input validation

- Pydantic models constrain `query` length (`SATQUERY_MAX_QUERY_LEN`),
  `dataset_ids` cardinality (`SATQUERY_MAX_DATASET_IDS`), `dataset_count`
  bounds, and provider/modality values (allowlists in `backend/app/security.py`).
- Validation runs server-side before parsing, planning, model calls, or DB
  writes.

### Uploads

- Allowed extensions: `.tif`, `.tiff`, `.png`, `.jpg`, `.jpeg` (configurable in
  `main.py`).
- Size cap (`SATQUERY_MAX_UPLOAD_MB`, default 250 MB) and a raster pixel-count
  cap (`SATQUERY_PIXEL_SAFETY_LIMIT`, default 120M pixels) protect memory/CPU.
- Magic-byte validation confirms the declared extension matches the actual file
  signature (TIFF II*/MM*, PNG, JPEG) before raster decoding.
- Uploaded display names are sanitised (path separators stripped, length
  capped). Storage paths are always server-generated UUIDs.
- Raster parsing uses `rasterio`/PIL, which gate on format; unsupported or
  malformed content is rejected with a generic message (no internal paths).

### Error handling / information disclosure

- Exceptions are converted to generic user-facing messages; filesystem paths
  are stripped (`safe_error` in `backend/app/security.py`).
- `/api/v1/health` is redacted: internal specialist URLs, raw provider detail
  text, and error strings are removed.
- `/api/v1/ai/free-test` is a debug endpoint and returns 404 unless
  `SATQUERY_DEBUG=1`.

### Prompt-injection boundary (Gemini VLM)

- The user query is sent as user content; a fixed system instruction bounds the
  model to remote-sensing analysis, forbids fabricated measurements, tool use,
  external access, and prompt disclosure. This is a defense-in-depth measure,
  not a guarantee against all prompt-injection variants.

### Network / SSRF

- Specialist service URLs come only from environment variables (`*_URL`); user
  input never becomes a service URL.
- Location geocoding (Nominatim) and STAC retrieval are constrained to
  gaze-bounded place/bbox inputs.
- CORS is restricted to `SATQUERY_CORS_ORIGINS` (default: localhost dev).

### Transport / headers

- HTTPS is enforced via HSTS; security headers (CSP, `X-Content-Type-Options`,
  `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`,
  `X-Permitted-Cross-Domain-Policies`) are applied on the Vercel deployment
  (`vercel.json`) and to API responses (`SecurityHeadersMiddleware` in
  `backend/app/security.py`).

### Secrets

- All secrets set at runtime through environment variables (e.g.
  `GEMINI_API_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `UPSTASH_REDIS_REST_TOKEN`).
- `.env*` is gitignored with an explicit `!.env.example` allow-list; never
  commit `.env.local` or the Vercel CLI token.

## Hardening checklist for a public deployment

- [ ] Add authentication/authorization ahead of any multi-user use.
- [ ] Set `SATQUERY_CORS_ORIGINS` to the production origin (never `*`).
- [ ] Set `UPSTASH_REDIS_REST_URL` + `UPSTASH_REDIS_REST_TOKEN` for shared rate
      limiting, and tune `SATQUERY_RATE_*` to the expected traffic.
- [ ] Review `SATQUERY_MAX_UPLOAD_MB` and `SATQUERY_PIXEL_SAFETY_LIMIT`.
- [ ] Check the repository stays private; inspect git history before making it
      public (rewrite/purge any accidentally committed secrets).
- [ ] Keep the GitHub repo private if the mission/account does not require a
      public showcase.
- [ ] Terminate specialist services behind TLS and restrict network access.
- [ ] Run `npm audit` (frontend) and `pip-audit` (backend) before each release.
- [ ] Run `python scripts/test_security.py` and the existing CI suite.
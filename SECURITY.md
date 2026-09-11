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

The current build is an SIH-grade working prototype. It is intentionally
single-user and does **not** ship production auth/RBAC. Known boundaries:

- Datasets are stored locally under `backend/data/`. Do not deploy this upload
  flow on a public multi-user host without adding authentication and per-user
  storage isolation.
- The API trusts `SATQUERY_CORS_ORIGINS`; run it with explicit origins in any
  shared deployment.
- Specialist adapters talk to `*_URL` environment services over HTTP. In
  production, terminate these behind TLS and restrict the network.

## Hardening checklist

- Set `SATQUERY_MAX_UPLOAD_MB` and review the raster pixel-count safety limit
  before exposing uploads.
- Keep `.env` out of version control (already in `.gitignore`).
- Run the backend on a dedicated user/container, not as an administrator.
- If deploying to a public host, add authentication, per-user data isolation and
  rate limiting before accepting user uploads.
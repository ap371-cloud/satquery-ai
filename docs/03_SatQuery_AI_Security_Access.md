# v2 Implementation Note

Automatic STAC retrieval is server-side; satellite URLs and optional model downloads are never exposed as privileged frontend secrets. CORS is now configured by `SATQUERY_CORS_ORIGINS` rather than wildcard by default. Full production authentication/RBAC remains a deployment task.

---

# SatQuery AI — Security & Access Document

**Version:** 1.0  
**Project:** SatQuery AI

---

## 1. Security Goals

SatQuery AI processes uploaded geospatial data and executes AI/ML pipelines. Security must protect:

- user accounts
- uploaded datasets
- analysis results
- API credentials
- model endpoints
- database records
- storage objects
- system availability

---

## 2. Security Principles

1. Least privilege
2. Deny by default
3. Never trust client input
4. Keep secrets server-side
5. Validate every uploaded file
6. Separate user data by ownership
7. Log privileged actions
8. Do not expose internal model endpoints directly
9. Use signed URLs for private files
10. Fail safely when evidence or authorization is unclear

---

## 3. User Roles

### ROLE_USER

Can:

- upload own datasets
- create analyses
- view own sessions
- view own results
- delete own datasets/results
- export own results

Cannot:

- view other users' data
- change system models
- view system secrets
- modify users

---

### ROLE_ADMIN

Can:

- inspect system health
- view aggregate usage
- manage model configurations
- review failed jobs
- disable abusive users
- inspect audit logs where authorized

Admin access should be restricted and logged.

---

## 4. Access Control Matrix

| Resource | User | Admin |
|---|---:|---:|
| Own profile | R/W | R |
| Own datasets | R/W/D | R if required |
| Other users' datasets | No | Restricted |
| Own analyses | R/W | R |
| Model registry | No | R/W |
| System configuration | No | R/W |
| Audit logs | No | R |
| Secrets | No | No direct UI access |
| System metrics | No | R |

`R = Read`, `W = Write`, `D = Delete`

---

## 5. Authentication

Recommended options:

### MVP

- Supabase Auth, Auth.js or equivalent trusted authentication provider

or

- email/password with secure backend session

### Requirements

- secure password hashing if passwords are stored
- HTTP-only cookies preferred for browser sessions
- Secure flag in production
- SameSite protection
- short-lived access tokens
- refresh token rotation if token architecture is used

---

## 6. Authorization

Every protected API request must verify:

1. user identity
2. resource ownership
3. user role
4. requested operation

Never rely on a frontend-provided `user_id`.

Example:

Bad:

```json
{
  "dataset_id": "ds123",
  "user_id": "user456"
}
```

Good:

```text
Authenticated identity comes from server-verified token/session.
```

---

## 7. Dataset Access Policy

Each dataset must have an owner.

Suggested record:

```text
dataset.id
dataset.owner_user_id
dataset.storage_key
dataset.visibility = private
```

Default visibility:

```text
PRIVATE
```

No public storage buckets for raw user uploads.

---

## 8. File Upload Security

Uploads are a major risk.

### Validate

- file extension
- MIME type
- actual file signature where practical
- file size
- raster readability
- maximum dimensions
- band count
- compression constraints
- archive handling
- malformed metadata

### MVP Allowed Types

- .tif
- .tiff
- .png
- .jpg
- .jpeg

### Recommended Size Limit

Set a practical environment-specific limit, e.g.:

```text
100–500 MB per raster for prototype
```

Do not accept unlimited uploads.

---

## 9. Raster Bomb / Resource Abuse Protection

Large or malicious raster inputs may exhaust memory or CPU.

Controls:

- maximum file size
- maximum pixel count
- maximum width/height
- processing timeout
- memory limits
- job queue
- per-user concurrency limit

---

## 10. API Security

All production APIs use HTTPS.

### Required protections

- authentication
- authorization
- schema validation
- rate limiting
- request IDs
- safe error responses
- CORS allowlist
- CSRF protection where cookie auth applies

---

## 11. Rate Limiting

Suggested starting limits:

### Auth

```text
5–10 login attempts / minute / IP
```

### Query API

```text
30 requests / minute / user
```

### Heavy Analysis

```text
2–5 active jobs / user
```

### Upload

```text
controlled by size + count
```

Adjust after testing.

---

## 12. Secrets Management

Never store secrets in:

- frontend code
- Git repository
- committed `.env`
- logs
- error messages

Secrets include:

- database password
- model API keys
- object-storage credentials
- JWT/session secret
- admin credentials

Use deployment environment variables or a secrets manager.

---

## 13. Object Storage Security

Raw and derived files should be private.

Use:

- signed upload URLs
- signed download URLs
- short expiration
- access checks before URL generation

Avoid permanent public object URLs for private datasets.

---

## 14. Database Security

Requirements:

- parameterized queries / ORM
- encrypted transport
- private network where possible
- minimal DB permissions
- backups
- migrations
- ownership filters

If using Supabase/Postgres:

- apply Row Level Security where appropriate
- test every policy against cross-user access

---

## 15. Logging Policy

Log:

- login events
- dataset creation/deletion
- analysis creation
- admin actions
- model routing
- analysis failures
- permission failures

Avoid logging:

- passwords
- tokens
- full secret keys
- sensitive raw raster bytes
- unnecessary personal data

---

## 16. Audit Log Structure

```json
{
  "event_id": "evt_123",
  "timestamp": "2026-08-28T10:00:00Z",
  "actor_user_id": "u_12",
  "action": "analysis.created",
  "resource_type": "analysis",
  "resource_id": "a_44",
  "request_id": "req_99",
  "metadata": {
    "intent": "flood_detection"
  }
}
```

---

## 17. AI-Specific Security

### Prompt Injection

User query must not be able to:

- retrieve server secrets
- alter system authorization
- call arbitrary tools
- execute shell commands
- access other users' files

Tool calls must be limited by a predefined registry.

---

### Tool Allowlisting

The LLM planner may propose only known tools.

Example:

```text
ALLOWED_TOOLS:
- align_rasters
- change_detection
- segment_water
- calculate_area
- polygonize
```

Unknown tool request:

```text
REJECT
```

---

## 18. Plan Validation

LLM-generated plan is untrusted data.

Before execution validate:

- tool exists
- inputs exist
- user owns inputs
- dependency graph valid
- parameters within limits
- no unexpected external calls
- resource cost acceptable

---

## 19. Model Output Safety

A model output must not automatically become a factual conclusion.

Use:

```text
Model Output
↓
Post-processing
↓
Geo Validation
↓
Confidence Check
↓
Evidence Gate
↓
User Response
```

---

## 20. Data Privacy

The system should collect only necessary user data.

Recommended:

- email/account ID
- project/session metadata
- dataset metadata
- analysis logs

Avoid unnecessary personal profile collection.

Provide a deletion path for user-owned datasets.

---

## 21. Data Retention

MVP policy example:

- user-controlled uploaded datasets: retained until user deletes
- temporary processing files: auto-delete after configurable period
- logs: retain for limited operational period
- failed job temp files: cleanup automatically

Exact production retention policy must be documented before deployment.

---

## 22. Admin Security

Admin requirements:

- separate admin role
- strong authentication
- optional MFA for production
- short sessions
- audit all admin actions
- no admin-only controls hidden only through frontend

Backend authorization is mandatory.

---

## 23. CORS Policy

Production:

```text
Allow only known frontend origins.
```

Do not use:

```text
Access-Control-Allow-Origin: *
```

with credentialed private APIs.

---

## 24. Error Handling

Do not expose stack traces publicly.

Bad:

```text
Database password authentication failed for ...
```

Good:

```json
{
  "error": "ANALYSIS_FAILED",
  "message": "The analysis could not be completed."
}
```

Detailed error goes to secure logs.

---

## 25. Dependency Security

- pin dependencies
- keep lock files
- run vulnerability scans
- avoid unknown packages
- update critical CVEs
- scan Docker images

---

## 26. Container Security

Recommended:

- non-root container user
- read-only filesystem where possible
- memory/CPU limits
- minimal base image
- no Docker socket exposure
- restrict outbound network if possible

---

## 27. Threat Model

### Threat: Cross-user dataset access

**Mitigation:** ownership checks + RLS/private storage.

### Threat: Malicious uploaded raster

**Mitigation:** strict parsing, limits, sandboxed processing.

### Threat: Prompt injection

**Mitigation:** allowlisted tools + validated plans.

### Threat: API key theft

**Mitigation:** server-side secrets.

### Threat: GPU/CPU abuse

**Mitigation:** rate limits + job quotas.

### Threat: Admin misuse

**Mitigation:** RBAC + audit logging.

### Threat: Hallucinated result

**Mitigation:** evidence gate + deterministic calculations.

---

## 28. Security Acceptance Criteria

Before public demo:

- [ ] No secrets in frontend bundle
- [ ] No secrets committed to Git
- [ ] Authentication works
- [ ] Cross-user access tests fail correctly
- [ ] Upload size limit exists
- [ ] Raster dimension limit exists
- [ ] Tool registry allowlisted
- [ ] LLM plan validated
- [ ] Admin routes backend-protected
- [ ] CORS restricted
- [ ] HTTPS enabled
- [ ] Rate limiting enabled
- [ ] Logs redact sensitive values
- [ ] Private storage tested
- [ ] Error messages do not reveal internal secrets

---

## 29. Final Security Rule

> **The AI may choose from approved capabilities, but it must never control permissions, secrets or unrestricted execution.**

---

## v3 External Specialist Security Requirements

- Bind local research-model bridges to localhost/private networks by default.
- Do not expose filesystem-path bridge APIs directly to the public internet.
- Production deployments should replace shared local paths with authenticated object references or multipart upload between services.
- Apply timeouts and concurrency limits to VLM/change/segmentation services.
- Treat model responses as untrusted data; GIS normalization and evidence validation remain server-side.

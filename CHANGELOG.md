# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

While the project is pre-1.0, minor versions may contain breaking changes. Breaking
changes are always listed first in a release and marked **BREAKING**.

## [Unreleased]

### Added

- **Retry for evidence packages.** `POST /api/v1/systems/{id}/evidence/{package_id}/retry`
  re-queues a failed or stalled package with its original options, keeping one record
  per request. The Evidence tab offers Retry on those packages and folds failed
  attempts under a disclosure so completed packages lead.
- **Optional authentication.** `AUTH_DISABLED=true` runs the API without credentials for
  private-network deployments, attributing every request to a reserved, non-loginable
  system principal with the admin role. The server logs a loud warning at startup and
  `GET /health` reports the mode. Default remains `false`.
- `GET /api/v1/auth/mode` so a client can discover whether credentials are required.
- `GET /api/v1/audit-logs` and `/audit-logs/{id}` (admin only), filterable by resource,
  action, actor, `actor_type` and request id.
- `get_current_user_optional` dependency for endpoints that identify a caller when
  possible without rejecting them.
- Secure headers middleware (CSP, `X-Content-Type-Options`, `X-Frame-Options`,
  `Referrer-Policy`, `Permissions-Policy`, opt-in HSTS over TLS).
- Dedicated rate limits for login/refresh, evidence generation and policy checks, with a
  configurable storage backend.
- `/ready` as a top-level readiness probe alongside `/health/ready`.

### Changed

- **BREAKING:** every `/api/v1` response is now wrapped as
  `{"success": true, "data": ...}`, and errors as
  `{"success": false, "error": {"code", "message", "details", "request_id"}}`. The
  operational endpoints (`/health`, `/ready`, `/metrics`) stay unwrapped so probes and
  Prometheus keep working.
- **BREAKING:** error codes are now `UPPER_SNAKE_CASE` (`UNAUTHORIZED`, `FORBIDDEN`,
  `NOT_FOUND`, `VALIDATION_ERROR`, `RATE_LIMITED`, …).
- **BREAKING:** `audit_logs.entity_type` / `entity_id` / `correlation_id` / `changes` are
  renamed to `resource_type` / `resource_id` / `request_id` / `new_values`, and the table
  gains `actor_type`, `actor_label`, `ip_address`, `user_agent` and `old_values`
  (migration `0003_optional_auth`).
- **BREAKING:** `REFRESH_TOKEN_EXPIRE_MINUTES` is replaced by `REFRESH_TOKEN_EXPIRE_DAYS`,
  and `ACCESS_TOKEN_EXPIRE_MINUTES` now defaults to 30 rather than 480.
- The primary request header is `X-Request-ID`; `X-Correlation-ID` is still accepted and
  echoed. Log lines carry `request_id`.
- `require_writer` / `WriterUser` are renamed to `require_risk_officer` /
  `RiskOfficerUser`; the previous names remain as aliases.

### Fixed

- **Evidence generation failed intermittently with `[Errno 111] Connection refused`.**
  Worker tasks were declared with `@shared_task`, which resolves its Celery app
  through a thread-local. FastAPI serves sync endpoints from a threadpool, so on any
  request thread that had not imported the Celery app the task bound to Celery's
  broker-less `default` app and tried `amqp://localhost:5672`. Redis was healthy the
  whole time — the earlier diagnosis of a transient broker outage was wrong. Tasks are
  now bound with `@celery_app.task`, the app is set as Celery's default on every
  thread, and a regression test resolves each task on a freshly spawned thread.
- **Evidence packages stuck on "Generating…" forever.** Packages whose dispatch
  failed before that was handled, or whose worker died mid-job, never left `pending`,
  and kept every open evidence view polling every 3 seconds. A scheduled task now
  marks packages in flight with no activity for longer than
  `EVIDENCE_STALE_AFTER_SECONDS` (default 15 minutes) as failed, and the client stops polling for them.
- **`docker compose up` could not pull MinIO.** MinIO deleted its Docker Hub
  repository, so `minio/minio:latest` fails with `pull access denied … repository
  does not exist`. Compose aborts the other parallel pulls when one fails, which is
  why `openpolicyagent/opa:1.19.1` also reported `Interrupted` / `No such image` —
  that image was never the problem. MinIO now comes from
  `quay.io/minio/minio:RELEASE.2025-09-07T16-13-09Z`, pinned because the `latest` tag
  on quay.io has been frozen at that release.
- **The documented demo accounts could not log in.** They were seeded at
  `@aigov.local`, and `.local` is a reserved special-use name that `email-validator`
  rejects, so `POST /api/v1/auth/login` answered `422` for the credentials the README
  documents. Any response serialising one of those users — `/auth/me`, `/auth/users`, a
  system's `owner` — failed for the same reason. The seeder writes through the ORM,
  which does not validate email syntax, so nothing surfaced it until a request was made.
  Demo accounts now use the RFC 2606 reserved domain `@aigov.example.com`, and the
  seeder renames any pre-existing `@aigov.local` rows in place so an already-seeded
  database heals itself without being dropped.
- **The API container crash-looped after migrations succeeded.**
  `docker/entrypoint.sh` runs `python scripts/seed.py`, which puts `scripts/` on
  `sys.path` rather than the repository root, so `import app` raised
  `ModuleNotFoundError`. Both entrypoint scripts now add the repository root to
  `sys.path` themselves — which also fixes the documented local command — and the image
  sets `PYTHONPATH=/app`. Regression tests execute every script in `scripts/` as a
  subprocess, both as a file and via `python -m`, against a dead database so imports are
  proven without touching a real one.
- **`docker compose up` failed to start any service.** `CORS_ORIGINS` and
  `POLICY_LIBRARY_FILES` are list settings, and pydantic-settings JSON-decodes complex
  fields straight from the environment *before* field validators run — so the ordinary
  `CORS_ORIGINS=http://localhost:3000` raised `SettingsError` at import time and took
  down the API, worker and beat containers together. Both fields are now annotated
  `NoDecode` and parsed in the validator, which accepts a comma-separated list or a JSON
  array. Regression tests construct `Settings` from the real `docker-compose.yml` and
  `.env.example` values, and a guard test fails if a new list setting is added without
  the same treatment.

### Security

- Failed logins are written to the audit trail and committed even though the request
  itself fails.
- The system principal can never authenticate: login is refused before the password hash
  is consulted, and tokens naming it are rejected.

## [0.1.0] - 2026-08-25

First public release. The backend is feature-complete for single-tenant use: inventory,
jurisdiction detection, risk classification, policy-as-code evaluation, evidence
generation and dashboards.

### Added

#### AI system inventory
- CRUD for AI systems with soft delete and restore, advanced filtering (free-text search,
  status, owner, industry, use case, deployment region, jurisdiction, risk tier) and
  cursor-friendly pagination with sorting.
- Structured compliance metadata per system, with full version history: every mutation
  writes an immutable snapshot and a field-level diff, attributed to the actor.

#### Jurisdiction detection
- Pure `JurisdictionEngine` — no database, network or clock in the decision path — that
  evaluates configurable `JurisdictionRule`s against a frozen `SystemProfile`.
- Named trigger registry split into **nexus** triggers (deployment, offering, data
  subjects, data residency, service reachability, generated-content reachability,
  consequential decisions) and **amplifier** triggers, which raise confidence but can
  never establish jurisdiction on their own.
- Region normalisation folding free-form input (`Germany`, `california`, `PRC`,
  `worldwide`) to canonical codes, expanding EU/EEA groups in both directions and
  collapsing them again in explanations.
- Output carries applicable regimes with per-regime reasons, a recommended evaluation
  order (strictest first), the most-restrictive set (ties included) and conflict notes.
- Ships with EU, California, China, India and a GLOBAL internal baseline. Rules are data:
  strictness, triggers, territories and consequential use cases are tunable from the
  `jurisdictions` table without a deploy.

#### Risk classification
- Global baseline scoring plus per-jurisdiction taxonomy overlays that only ever escalate
  a tier, so "most restrictive" holds by construction.
- Classifications are append-only and record the metadata version they were computed
  against, so the dashboard can flag systems whose metadata changed since assessment.

#### Policy as code
- Open Policy Agent integration over the REST Data API, with a declarative fallback and an
  explicit `error` result when a policy cannot be evaluated — a check is never silently
  dropped.
- EU AI Act policy packages: high-risk obligations (Art. 9-15, 25, 27, 43, 49, 72, 73),
  prohibited practices (Art. 5) and transparency duties (Art. 50, 53), with Annex III use
  cases mapped by point so explanations cite the right one.
- Every finding carries a stable `rule_id`, the article, its own severity, a
  human-readable explanation and actionable remediation. Check severity reflects the worst
  finding raised, not the severity of the policy that looked.
- 33 Rego unit tests alongside the policies, plus an end-to-end suite against a live OPA.

#### Evidence packages
- Asynchronous generation via Celery: assembles inventory, classifications and policy
  checks, renders a jurisdiction-specific PDF (EU, California, China and India templates),
  writes a canonical JSON manifest, uploads both to S3-compatible storage and records a
  SHA-256 checksum.

#### Dashboards
- Portfolio summary and per-jurisdiction breakdown with risk-tier counts, compliance
  rates, recent failures and pending reviews. Cached in Redis, invalidated on mutation and
  refreshed on a schedule.

#### Platform
- JWT authentication with role-based access control (admin, risk officer, viewer).
- Correlation ID on every request, propagated into logs, the audit trail and Celery tasks.
- Append-only audit trail; risk classifications, policy checks and audit logs are
  protected by PostgreSQL triggers that reject `UPDATE` and `DELETE`.
- Consistent error envelope, structured JSON logging, Prometheus metrics, liveness and
  readiness probes, and Redis-backed rate limiting.
- Docker Compose stack (API, worker, beat, PostgreSQL, Redis, OPA, MinIO) that starts with
  one command.

### Security

- The application refuses to start in `staging` or `production` when `SECRET_KEY`,
  `POSTGRES_PASSWORD` or `S3_SECRET_ACCESS_KEY` still hold a value published in
  `.env.example`.
- The seeder refuses to create demo accounts outside `local`/`test` unless
  `SEED_DEMO_USERS` is set explicitly, and honours `SEED_ADMIN_PASSWORD`.

[Unreleased]: https://github.com/OWNER/REPO/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/OWNER/REPO/releases/tag/v0.1.0

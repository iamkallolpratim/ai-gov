# Roadmap

Companion to [STATE_OF_THE_PROJECT.md](STATE_OF_THE_PROJECT.md). Bug IDs (B1…) refer to its §6.
Effort: **S** ≤ 1 day · **M** 2–5 days · **L** 1–3 weeks (one person, part-time-ish).

The repo is already public with 3 stars, so "launch" here means the first *announced*
release, not flipping visibility. Nothing is announced until v0.1 is green.

---

## v0.1.0 — Launch-ready (must ship before announcing)

Exit criteria: a stranger runs one command, logs in to seeded data within 3 minutes, walks
register → classify → evaluate → evidence, and CI is green on the commit they cloned.

| # | Item | Why it matters | Files / modules | Effort | Depends on |
|---|---|---|---|---|---|
| 1.1 | **Replace MinIO** with a pinned, maintained S3 image (SeaweedFS verified) | B1: `docker compose up` fails for 100 % of new users today | `docker-compose.yml:91-104`, README/client README mentions of MinIO, `.env.example` (`MINIO_*` → `S3_*`) | S | — |
| 1.2 | **Single OPA source of truth.** OPA starts with no bundle (or only `policies/common`); API pushes active DB policies on start; exclude `*_test.rego` from serving | B2: every sync 400s; DB/API policy edits are silently ignored | `docker-compose.yml:79-89`, `scripts/sync_opa.py`, `app/services/policy.py:146-175`, `tests/integration/test_opa_live.py` | S–M | — |
| 1.3 | **Un-publish infra ports by default** (postgres/redis/opa/s3 reachable only on the compose network; opt-in via `compose.override.yml`) | Port clashes with locally installed Postgres/Redis are the #2 first-run failure | `docker-compose.yml` ports blocks, README "Quick start" | S | — |
| 1.4 | **Prebuilt images on GHCR** (`ghcr.io/iamkallolpratim/ai-gov-api`, `-client`) + `compose.yml` that pulls by default, builds with `--build` | Cold start drops from ~8 min to ~1–2 min; also needed by the hosted demo | new `.github/workflows/release-images.yml`, `docker-compose.yml` `image:` keys | M | 1.6 |
| 1.5 | **`make demo`** = `cp -n .env.example .env && docker compose up -d && wait-for /ready && open :3000` | The "3 commands" on the landing page become literally true | `Makefile`, `scripts/wait_ready.sh` | S | 1.1–1.3 |
| 1.6 | **CI**: ruff, mypy, pytest against Postgres service, `opa test policies/`, `opa check --strict`, client `lint`/`typecheck`/`build`, compose smoke test hitting `/ready` and the E2E flow | Nothing currently verifies a PR; badge on README | new `.github/workflows/ci.yml` | M | 1.1, 1.2 |
| 1.7 | **Fix mypy** (B5) | CI must be green on day 1 | `app/services/inventory.py:120,150` | S | — |
| 1.8 | **Dependency security**: `npm audit fix` (Next critical), replace `python-jose` → `PyJWT`, `passlib` → `bcrypt` directly (drops the `bcrypt==4.0.1` pin); add Dependabot | Open advisories are the first thing security-minded HN readers check | `client/package*.json`, `requirements.txt`, `pyproject.toml`, `app/core/security.py`, `.github/dependabot.yml` | S | — |
| 1.9 | **Auth hardening pass**: strip `input` from 422 bodies (B4); account lockout/backoff on top of the rate limit; refresh-token rotation + revocation list in Redis; check JWT `iss`/`aud` | Compliance tool must look secure by construction | `app/api/errors.py:71-77`, `app/core/security.py`, `app/api/v1/routers/auth.py:38-90` | M | 1.8 |
| 1.10 | **Global baseline to the decision contract** (B3): `rule_id`, `article` (or `source`), `severity`, `in_scope`, + Rego tests | Every finding the demo shows should carry a citation | `policies/global/global_transparency.rego`, new `policies/global/global_transparency_test.rego` | S | — |
| 1.11 | **Minimum non-EU policy packs** — one Rego package per jurisdiction encoding what the seed taxonomy already lists as obligations: CA ADMT (pre-use notice, opt-out/appeal, risk assessment), CN (CAC algorithm filing, security assessment, content labelling, localisation), IN DPDP (consent notice, grievance officer, DPIA/SDF duties) using `obligation()`/`readiness_violation()` where not yet in force | README promises four regimes; today 3 of 4 have zero evaluable rules (STATE §2). Without this the launch claim is false | new `policies/ca/`, `policies/cn/`, `policies/in/` + tests, `app/db/seed.py` `POLICIES` (L283+) | **L** | 1.10 |
| 1.12 | **Richer seed demo** — 8–10 systems covering every jurisdiction × tier, pre-run classifications/checks/evidence so the dashboard isn't empty on first load | First screen sells the product; the demo GIF needs it | `app/db/seed.py:400-500`, new `scripts/seed_demo_history.py` | M | 1.11 |
| 1.13 | **README rewrite**: ≤150 lines, monorepo title, GIF, 3-command quickstart, coverage table that matches reality, links to docs site. Move deep content (auth modes, decision contract, detection rules) to docs | 894-line "Backend" README hides the product | `README.md`, `client/README.md` | M | Phase 3 docs |
| 1.14 | **Placeholders & metadata** (B6–B10): OWNER/REPO, `main`→`production` links, OpenAPI version from package, repo description typo, topics, tag `v0.1.0` | Visible on launch day | `README.md`, `CHANGELOG.md`, `.github/ISSUE_TEMPLATE/*`, `app/main.py:101` | S | — |
| 1.15 | **Playwright smoke test** (login → new system → classify → check → evidence download) in CI | Only frontend coverage; doubles as the GIF recording script | `client/e2e/`, `client/playwright.config.ts`, `ci.yml` | M | 1.6 |
| 1.16 | **Demo-mode flag** (`DEMO_MODE=true`): read-only for non-admin demo users, banner, nightly reset | Required for the hosted demo (Phase 4) | `app/core/config.py`, `app/api/deps.py`, `client/components/layout/topbar.tsx`, beat task | M | 1.12 |

**Critical path:** 1.1 → 1.2 → 1.6 → 1.11 → 1.12 → 1.15 → tag. Realistic total: **3–4 weeks**
part-time, of which 1.11 is half.

**Explicitly not in v0.1:** policy editing UI, PDF redesign, multi-tenancy, SSO, Helm chart.

---

## v0.2 — Depth (≈ 6–8 weeks after launch)

| # | Item | Why | Files / modules | Effort | Depends on |
|---|---|---|---|---|---|
| 2.1 | **Regulation depth**: EU GPAI obligations (Art. 53–55) and Annex III completeness; CA CPPA ADMT final regs + SB 942; CN deep-synthesis + labelling measures; IN DPDP Rules (consent managers, SDF audits, children's data) | Breadth was v0.1, defensibility is v0.2; this is what compliance pros will probe | `policies/*`, `app/db/seed.py` taxonomies, `jurisdiction_engine.py` triggers | L | 1.11 |
| 2.2 | **Regulation mapping as data** — `policies/<jur>/MAPPING.yaml` (article → rule_id → test) rendered into docs pages and the PDF | Traceability is the product; also feeds the docs site | new files, `app/services/pdf.py`, site build | M | 2.1 |
| 2.3 | **Policy authoring UX**: Monaco Rego editor, input-document playground ("evaluate this rule against system X"), `opa check` on save, version diff, activate/deactivate | API already supports CRUD (`policies.py:64-101`); UI is read-only (`client/app/(dashboard)/policies/page.tsx`) | `client/app/(dashboard)/policies/[id]/`, new `POST /policies/{id}/dry-run` | L | 1.2 |
| 2.4 | **Evidence export v2**: signed JSON (detached signature / in-toto-style attestation), bundle ZIP (PDF + JSON + raw OPA decisions + audit slice), PDF template polish | Auditors want verifiable artefacts, not just PDFs | `app/services/evidence.py`, `pdf.py`, `tasks.py:39` | M | — |
| 2.5 | **Audit trail export** (CSV/JSON, date range, hash-chained rows for tamper evidence) | "Immutable trail" claim needs to be demonstrable | `app/models/audit.py`, `app/services/audit.py`, `routers/audit.py`, migration 0004 | M | — |
| 2.6 | **API keys** (scoped, hashed, per-key rate limit) for CI/automation | JWT login is wrong for machines; blocks CLI and GitHub Action | new `app/models/api_key.py`, `app/api/deps.py`, migration, Users page tab | M | 1.9 |
| 2.7 | **Outbound webhooks** (system.classified, check.failed, evidence.completed) with HMAC signatures + retries via Celery | Integrations hook point (Slack, Jira, ticketing) | new `app/services/webhooks.py`, `tasks.py`, model + migration | M | 2.6 |
| 2.8 | **CLI `aigov`** (Python, Typer): `aigov register system.yaml`, `aigov check --fail-on high`, `aigov evidence pull` — systems described as YAML in the repo | "Compliance as code" story for developers; foundation for 3.1 | new `cli/` package, published to PyPI | M | 2.6 |
| 2.9 | **Generated TS + Python SDKs** from OpenAPI | Cheap once OpenAPI is clean; replaces hand-written `client/types/api.ts` | `openapi-typescript`, `openapi-python-client`, CI job | S | — |
| 2.10 | **Questionnaire-driven system intake** (guided form that fills metadata attributes like `ai_content_labelled`) | Today users must know magic attribute names to clear findings | `client/components/systems/system-form.tsx`, attribute schema per policy | M | 2.2 |

---

## v0.3+ — Ecosystem

| # | Item | Why | Effort | Depends on |
|---|---|---|---|---|
| 3.1 | **GitHub Action** `aigov/check-action`: evaluates `aigov.yaml` in a repo on PR, comments findings, fails on threshold. Works offline with bundled Rego, or against a server | Best distribution channel to developers; marketplace listing | M | 2.8 |
| 3.2 | **Model registry importers**: MLflow, Hugging Face Hub model cards, SageMaker / Vertex registries → AI systems with pre-filled metadata | Removes manual inventory entry, the #1 adoption friction | L | 2.6 |
| 3.3 | **LLM gateway hooks**: LiteLLM / Envoy AI Gateway plugin that reports which models/apps are live and blocks unregistered ones | Runtime inventory = shadow-AI detection; strong demo | L | 2.6, 2.7 |
| 3.4 | **Multi-tenancy** (org_id on every table, RLS in Postgres, per-org OPA data namespace) | Required for any hosted offering; risky schema change, so do it before the user base grows | L | — |
| 3.5 | **Jurisdiction plugin system**: a jurisdiction = directory with `jurisdiction.yaml` (territories, triggers, taxonomy) + Rego + tests + mapping; discovered at boot instead of hard-coded in `seed.py` / `jurisdiction_engine.py` | Lets the community add Brazil, Korea, Colorado, UK without core PRs | L | 2.2 |
| 3.6 | SSO (OIDC/SAML), SCIM | Enterprise prerequisite | M | 3.4 |
| 3.7 | Helm chart + Terraform module | Self-hosting in real orgs | M | 1.4 |
| 3.8 | ISO/IEC 42001 & NIST AI RMF control crosswalks | Lets the tool serve orgs not directly regulated | M | 2.2 |

---

## What I would cut or defer

- **Beat task `recheck_all_systems`** in the demo — noisy, burns demo resources; enable per-deployment.
- **`AUTH_DISABLED` mode** — keep, but don't advertise it on the landing page; it invites misuse.
- **Prometheus `/metrics`** marketing — keep the endpoint, skip Grafana dashboards until someone asks.
- **3.3 LLM gateway hooks** — highest wow, highest maintenance; only after 3.1 proves demand.
- **3.4 multi-tenancy** — only if you decide to run a hosted SaaS. For self-hosted OSS, one
  instance per org is fine and far simpler. This is a business decision, not a technical one.
- **Chinese/Indian language UI** — tempting for those audiences, but English-only until v0.3.

## Risks

- **Legal accuracy.** A wrong citation on launch day is the most damaging possible HN
  comment. Every new rule in 1.11 needs a source link and a "last reviewed" date; consider
  one domain-expert review per jurisdiction before announcing.
- **Scope creep in 1.11.** Ship a *minimum* pack (3–6 rules per jurisdiction, all cited)
  and label it "starter coverage" rather than delaying the launch for completeness.
- **Single maintainer bus factor.** Good-first-issues + CONTRIBUTING's "Adding a jurisdiction"
  guide are the mitigation; Phase 4 should target jurisdiction contributors specifically.

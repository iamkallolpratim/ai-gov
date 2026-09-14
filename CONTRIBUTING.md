# Contributing to the AI Governance Console

Thanks for considering a contribution. This project tracks how organisations govern their
AI systems across jurisdictions, so contributions range from Python and Rego to
regulatory research — you do not need to be a backend engineer to help.

By participating you agree to the [Code of Conduct](CODE_OF_CONDUCT.md). Contributions are
accepted under the [Apache License 2.0](LICENSE).

---

## Contents

- [Getting set up](#getting-set-up)
- [Development workflow](#development-workflow)
- [Branch naming](#branch-naming)
- [Commit messages](#commit-messages)
- [Pull request process](#pull-request-process)
- [Code style](#code-style)
- [Testing expectations](#testing-expectations)
- [Adding a new jurisdiction](#adding-a-new-jurisdiction)
- [Adding or changing a policy](#adding-or-changing-a-policy)
- [Database migrations](#database-migrations)
- [A note on legal accuracy](#a-note-on-legal-accuracy)

---

## Getting set up

The whole stack runs in Docker:

```bash
git clone <your-fork-url> && cd ai-gov
cp .env.example .env
docker compose up --build
```

For day-to-day Python work, run the services in Docker and the app on your machine:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
docker compose up -d postgres redis opa minio
alembic upgrade head && python scripts/seed.py
uvicorn app.main:app --reload
```

To work on Rego you also want the OPA CLI (`brew install opa`, or download it from
[openpolicyagent.org](https://www.openpolicyagent.org/docs/latest/#running-opa)).

## Development workflow

```bash
make test        # pytest
make lint        # ruff + mypy
make fmt         # ruff format and autofix
make opa-test    # Rego unit tests
```

Everything must pass before you open a pull request. `make test` skips the live-OPA suite
when no policy engine is reachable; `make test-opa` starts one and runs the full set.

## Branch naming

Branch off the default branch (`main`) and use a `type/short-description` slug:

| Prefix | Use for | Example |
| --- | --- | --- |
| `feat/` | new functionality | `feat/brazil-jurisdiction` |
| `fix/` | bug fixes | `fix/pagination-off-by-one` |
| `policy/` | Rego policy changes | `policy/eu-art-26-deployer-duties` |
| `docs/` | documentation only | `docs/clarify-risk-tiers` |
| `test/` | test-only changes | `test/dashboard-edge-cases` |
| `chore/` | tooling, deps, CI | `chore/bump-fastapi` |
| `refactor/` | behaviour-preserving cleanup | `refactor/split-policy-service` |

Keep branches short-lived and focused on one change.

## Commit messages

[Conventional Commits](https://www.conventionalcommits.org/), because the changelog is
generated from them:

```
feat(jurisdictions): add Brazil (LGPD + PL 2338/2023) overlay

Adds a BR rule with deployment and data-subject nexus triggers, its risk
taxonomy, and seed data. Strictness sits between IN and CA.

Closes #42
```

Common scopes: `api`, `inventory`, `jurisdictions`, `risk`, `policy`, `evidence`,
`dashboard`, `workers`, `db`, `docs`, `deps`.

## Pull request process

1. **Open an issue first** for anything non-trivial, so the approach can be agreed before
   you spend time on it. Small fixes and typos can go straight to a PR.
2. Fork, branch, and make your change.
3. Add tests. A PR that changes behaviour without a test will be asked for one.
4. Run `make lint && make test` (and `make opa-test` if you touched Rego).
5. Update the docs you invalidated — `README.md`, docstrings, and `CHANGELOG.md` under
   `## [Unreleased]`.
6. Open the PR against `main` with:
   - what changed and **why** (the why matters more)
   - the issue it closes (`Closes #123`)
   - for policy changes, a citation to the article or section you implemented
   - for API changes, the before/after request and response
7. Keep the PR focused. Unrelated refactors make review slow; split them out.

Maintainers aim to give a first response within a week. CI must be green and at least one
maintainer approval is required before merge. We squash-merge, so your PR title becomes
the commit message — make it a good Conventional Commit.

## Code style

Enforced by `ruff` (line length 100) and `mypy`, both configured in `pyproject.toml`.
Beyond what the tools check:

- **Type everything.** Public functions get full annotations. `mypy app` must pass clean.
- **Layering is strict.** Routers depend on services, services depend on models, and
  nothing depends back up. Business logic does not belong in a router.
- **Keep the core pure.** `JurisdictionEngine` and the risk baseline take plain data and
  return plain data, with database access confined to thin adapters. New decision logic
  should follow that pattern — it is what makes this codebase testable.
- **Comment the why, never the what.** Explain a regulatory nuance, a non-obvious
  trade-off, or a workaround. Do not narrate the code.
- **Errors are typed.** Raise the domain exceptions in `app/core/exceptions.py`; the API
  layer turns them into the standard error envelope. Do not raise bare `HTTPException`
  from a service.
- **Audit data is immutable.** Never add an update or delete path for risk
  classifications, policy checks, or audit logs. Database triggers will reject it anyway.

Rego is formatted with `opa fmt --write policies/` and must pass `opa check policies/`.

## Testing expectations

| Change | Expected tests |
| --- | --- |
| Service logic | unit tests in `tests/unit/` |
| Endpoint | request/response test in `tests/integration/` |
| Rego policy | Rego unit tests beside the policy, plus a live-OPA case |
| Jurisdiction rule | one case per trigger, and one proving it does *not* over-match |
| Bug fix | a test that fails before your fix |

Unit tests run against in-memory SQLite and need no services. Keep them that way: if a
test needs PostgreSQL, mark it and make it skip cleanly when the database is absent.

The "does not over-match" case matters more than it looks. A jurisdiction rule that fires
too eagerly buries users in obligations they do not have, which is just as wrong as
missing one.

## Adding a new jurisdiction

Worked example: adding Brazil.

1. **Add the rule** in `app/services/jurisdiction_engine.py` (`DEFAULT_RULES`):

   ```python
   JurisdictionRule(
       code="BR",
       name="Brazil",
       regulation_name="LGPD; PL 2338/2023",
       territories=frozenset({"BR"}),
       strictness=65,                    # relative priority when regimes conflict
       triggers=(
           "deployment_nexus",
           "offering_nexus",
           "data_subject_nexus",
           "data_residency_nexus",
       ),
   )
   ```

2. **Add region aliases** in `app/services/regions.py` if the country is written more
   than one way (`"Brasil"`, `"BRA"` → `"BR"`).
3. **Add seed data** in `app/db/seed.py`: the `Jurisdiction` row with its `territories`,
   `overlay_config` (strictness, triggers) and `risk_taxonomy` (tier labels, high-risk and
   prohibited use cases, obligations per tier).
4. **Add tests** in `tests/unit/test_jurisdiction_engine.py` — one per trigger, plus a
   negative case proving an unrelated system stays out of scope.
5. **Add policies** for the regime (see below). A jurisdiction with no policies detects
   and classifies, but checks nothing.
6. **Document it** in the README's supported-jurisdictions table.

`strictness` decides which regime wins when obligations conflict. Place a new one relative
to the existing set (EU 100, CN 90, CA 70, IN 60, GLOBAL 10) and say why in the PR.

## Adding or changing a policy

Policies are Rego, versioned, and stored both on disk and in the database.

1. **Write the Rego** under `policies/<jurisdiction>/`. Import the shared helpers and emit
   the standard decision shape:

   ```rego
   package aigov.br.high_risk

   import data.aigov.eu.base   # or your own base helpers
   import rego.v1

   default in_scope := false
   default allow := false

   violations contains v if {
       in_scope
       not base.flag("human_oversight_documented")
       v := base.violation(
           "br.high_risk.art_X.human_oversight",   # stable, greppable rule id
           "Art. X",                               # the citation
           "critical",                             # severity of this finding
           "Explanation a compliance officer can act on, citing the article.",
           "Concrete remediation: the exact thing to go and do.",
       )
   }
   ```

2. **Write Rego unit tests** in `<name>_test.rego` beside it. Cover the rule firing, the
   rule *not* firing when the obligation is met, and out-of-scope systems.
3. **Seed it** in `app/db/seed.py` → `POLICIES`, with `key`, `version`, `severity`,
   `opa_package`, `rego_file` and `applies_to_risk_tiers`.
4. **Version, never edit in place.** Once a policy has evaluated real systems, its stored
   checks cite that version. Publish a new `version` instead of changing the old one, so
   historical evidence packages stay meaningful.
5. **Run** `make opa-test` and add a live-OPA case in `tests/integration/test_opa_live.py`.

Every violation must carry `rule_id`, `article`, `severity`, a human-readable `msg` and an
actionable `remediation`. The console renders these directly to compliance officers, so
"policy failed" is not an acceptable message. Write for someone who has to fix it.

Severity guidance: `critical` blocks market placement, `high` is a serious gap needing a
plan, `medium` is remediable in a sprint, `low` is a nice-to-have. Severity comes from the
finding, not the policy.

## Database migrations

Models and migrations must stay in step:

```bash
alembic revision --autogenerate -m "add X"   # or: make revision m="add X"
alembic upgrade head
```

Review the generated file before committing — autogenerate misses server defaults, JSONB
details and index renames. New columns on existing tables need a `server_default` for the
backfill, dropped afterwards if the application always supplies a value (see
`0002_system_reach_regions.py`). Every migration needs a working `downgrade()`.

## A note on legal accuracy

This project encodes regulation, and getting it wrong has consequences for the people
relying on it. When you add or change a rule:

- **Cite the source.** Article, section, or recital, in the code and in the PR.
- **Model the exemptions.** A rule that ignores a carve-out produces false positives, and
  users learn to ignore the tool. Where the Act has an exception, represent it explicitly
  as a documented, auditable attribute rather than assuming it away.
- **Prefer over-inclusion to silence,** and say so in the explanation. Telling someone to
  document a system that turns out to be limited-risk is cheap; missing a high-risk system
  is not.
- **Do not present this as legal advice.** Explanations should describe the obligation and
  cite the source, so a human expert can verify it.

Nobody expects you to be a lawyer. Cite what you implemented, flag what you are unsure
about in the PR, and a reviewer will work through it with you.

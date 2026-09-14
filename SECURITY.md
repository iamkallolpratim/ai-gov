# Security Policy

## Reporting a vulnerability

**Please do not open a public issue for a security problem.** Public issues are visible
to everyone, including people who would use the details before a fix ships.

Report privately through **[GitHub private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)**:

1. Open the **Security** tab of this repository.
2. Choose **Report a vulnerability**.
3. Describe the issue and how to reproduce it.

<!-- MAINTAINERS: add a monitored security contact address here before publishing,
     e.g. security@your-domain.example, and remove this comment. -->

If private reporting is unavailable to you, contact a maintainer directly and ask for a
private channel before sharing any details.

## What to include

The more of this you can provide, the faster a fix lands:

- What kind of issue it is (authentication bypass, injection, privilege escalation, …)
- The affected file, endpoint, or component
- Step-by-step reproduction, ideally a `curl` command or a failing test
- The impact you believe it has, and any proof-of-concept you have
- The version, commit SHA, or Docker image tag you tested

## Response process

| Stage | Target |
| --- | --- |
| Acknowledgement of your report | within 3 working days |
| Initial assessment and severity triage | within 7 working days |
| Fix or documented mitigation for high/critical issues | within 30 days |
| Public advisory and credit (if you want it) | after the fix is released |

We will keep you updated as the assessment progresses, credit you in the advisory unless
you prefer to stay anonymous, and let you know when the fix is public.

## Scope

This project is a backend for AI compliance record-keeping. Findings that are especially
relevant here:

- Authentication or JWT handling flaws (`app/core/security.py`, `app/api/deps.py`)
- Role-based access control gaps — a `viewer` performing a write, a user reading another
  tenant's systems (`app/api/deps.py`, the routers under `app/api/v1/routers/`)
- Anything that lets **immutable audit data be modified or deleted** — risk
  classifications, policy checks and audit logs are append-only and enforced by database
  triggers (`alembic/versions/0001_initial_schema.py`)
- SQL injection, SSRF (particularly through the OPA and S3 clients), or path traversal in
  evidence storage keys
- Policy evaluation that can be tricked into reporting a passing check for a
  non-compliant system
- Secrets leaking into logs, API responses, or generated evidence packages

### Out of scope

- The development credentials in `.env.example` and `docker-compose.yml`. These are
  public on purpose so the stack starts with one command. The application **refuses to
  boot** in `staging` or `production` if it finds them (`app/core/config.py`), and the
  seeder refuses to create demo accounts outside `local`/`test`.
- Denial of service through obviously unbounded local resource use (running the stack
  without rate limits enabled, and so on).
- Findings that require an already-compromised host or database.
- Missing hardening on the local Docker Compose stack, which is a development tool and is
  not intended to be exposed to a network.

## Supported versions

The project is pre-1.0. Fixes land on the default branch and in the next release; there
are no long-term support branches yet.

| Version | Supported |
| --- | --- |
| 0.1.x | ✅ |
| < 0.1 | ❌ |

## Deploying safely

If you run this yourself, at minimum:

- Set a real `SECRET_KEY` (`python -c "import secrets; print(secrets.token_urlsafe(48))"`)
- Replace every credential from `.env.example`
- Set `ENVIRONMENT=production` so the startup guard is active
- Terminate TLS in front of the API and restrict `CORS_ORIGINS`
- Rotate the seeded demo accounts, or never seed them (`SEED_ON_START=false`)
- Enable server-side encryption on the S3 bucket holding evidence packages

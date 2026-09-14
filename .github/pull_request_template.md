## What and why

<!-- What changes, and what problem it solves. The "why" matters more than the "what". -->

Closes #

## Type of change

- [ ] Bug fix
- [ ] New feature
- [ ] Jurisdiction or policy change
- [ ] Documentation
- [ ] Refactor / tooling

## Regulatory basis

<!-- Required for jurisdiction and policy changes. Cite the article or section you
     implemented, and note any exemptions the rule respects. Delete if not applicable. -->

## How this was tested

<!-- New tests added, and anything you verified by hand. -->

- [ ] `make lint` passes
- [ ] `make test` passes
- [ ] `make opa-test` passes (if Rego changed)

## Checklist

- [ ] Tests cover the new behaviour, and a bug fix has a test that failed before it
- [ ] Docs updated (`README.md`, docstrings) where this made them wrong
- [ ] `CHANGELOG.md` updated under `## [Unreleased]`
- [ ] A new policy version was published rather than an existing one edited in place
- [ ] No new update or delete path for audit data (classifications, checks, audit logs)
- [ ] No secrets, credentials, or real system data added

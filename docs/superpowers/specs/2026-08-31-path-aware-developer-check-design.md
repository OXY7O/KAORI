# KAORI Path-Aware Developer Check Design

**Issue:** #68  
**Status:** Implementation authority  
**Scope:** Draft development feedback, Pre-Ready cheap gate, CI readability, and progress observability

## Problem

KAORI Full Admission is intentionally comprehensive and expensive. Using it as a development/debug loop wastes self-hosted runner time and delays feedback for formatter, focused contract, migration, or path-local defects that can be found cheaply.

## Delivery Model

```text
Issue / Design
  -> work branch from kaori/staging
  -> Draft PR
  -> path-aware Developer Check
  -> collect findings
  -> batch repair
  -> Pre-Ready cheap gate PASS
  -> Ready + frozen final candidate
  -> one fresh Full Admission
  -> merge kaori/staging
  -> exact evidence reuse + Fast Smoke
  -> human UAT
  -> staging -> main Promotion
  -> evidence reuse + Fast Smoke
  -> post-promotion verification
```

Full Admission is the final-candidate admission boundary, not the ordinary development loop.

## Developer Check

`KAORI Developer Check` is a separate Draft-only workflow. It never consumes Full Admission evidence and never runs production image, Trivy, runtime, DAST, or the global test suite.

Changed paths are resolved once and routed into focused jobs:

- Python: Ruff check/format for changed Python scope plus Pyright when application/validation Python changes require it.
- Templates: djlint for changed Jinja templates.
- Frontend: existing npm formatting checks when frontend assets/tooling change.
- Migrations: migration graph plus focused migration tests when migrations/models change.
- Contracts: focused tests mapped from changed application/test domains.
- Validation authority: fail-safe wide Developer Check covering all cheap groups when CI/workflow/authority files change.

Unknown application paths fail safe by selecting the broad cheap contract group rather than silently skipping validation.

## Path Groups

Representative routing groups include platform/CI, Vault Management and access/security, tenant/user/settings, Intelligence, Reports, Kubernetes, Object Storage/storage, Integrations, and shared application infrastructure.

The router returns deterministic newline-safe GitHub outputs. Workflow jobs consume those outputs without evaluating PR-controlled strings as shell syntax.

## Pre-Ready

Pre-Ready means the latest Draft source head has a successful Developer Check and Critical/Important review findings are zero. Only then should the PR be marked Ready.

Ready freezes the candidate. A source change after Ready invalidates final-candidate evidence and returns the work to the Draft/development loop when repair is needed.

## Failure Handling

A failed Full Admission is not repaired one finding at a time. Collect all actionable findings from the failed run, return to Draft, perform a batch repair, pass Developer Check again, then create one new frozen Ready candidate and one new Full Admission.

## CI Readability

Governed graph names are concise:

- Resolve Profile
- Static & Governance
- Security
- Functional Tests
- Frontend
- Runtime & DAST
- Fast Smoke
- CI Admission

Telegram workflow/job names are `KAORI Telegram Notify / Notify`.

Operator output uses a consistent visual vocabulary:

- `✅` PASS
- `⚠️` SKIP / REUSED / FALLBACK context
- `❌` FAIL
- `📦` coverage
- `⏱` duration
- `➡️` next action

Static checks emit a start/progress line naming the active verifier and a completion duration. This makes long verifiers observable without streaming noisy successful command output.

## Safety

Developer Check is advisory development feedback; it never weakens or replaces Full Admission. Validation-authority changes continue to require fresh Full Admission at Ready. Staging and main retain exact evidence reuse, lineage verification, Fast Smoke, and human UAT authority.

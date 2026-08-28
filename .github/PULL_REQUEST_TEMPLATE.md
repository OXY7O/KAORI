## Linked Work

Use `Refs #<issue>` while the work is still moving through staging/UAT. Use `Closes #<issue>` only on the final PR whose successful merge is intended to close the Issue.

Refs #

## Why

Explain the problem, outcome, or engineering reason for this change in language a reviewer can understand without reading the diff first.

## What Changed

Summarize the implementation in a small number of concrete points. Name the important boundaries or files when that helps review.

## Out of Scope

State what was intentionally not changed. Use `None — <reason>` only when the scope genuinely has no meaningful exclusion.

## Acceptance Criteria Coverage

Map each linked acceptance criterion to implementation or evidence. Do not mark criteria complete based only on code presence when runtime/CI/UAT evidence is required.

## Verification Evidence

Record the exact evidence used for review:

- Targeted tests/checks:
- Full KAORI CI run:
- Validated commit SHA:
- Known warnings/skips and rationale:

Do not paste full logs here. Link the run/job and summarize the actionable result.

## Security Impact

State the security impact, trust-boundary change, vulnerability/security validation, or `None — <reason>`.

## Migration / Data Impact

State schema, migration, compatibility, retained-data, or data-lifecycle impact, or `None — <reason>`.

## Observability / Operational Impact

State logging, metrics, alerts, operational workflow, rollback, support, or runtime impact, or `None — <reason>`.

## UAT

- [ ] Work-branch validation only; staging UAT is not yet applicable.
- [ ] Integrated into `kaori/staging` and full staging CI passed.
- [ ] Local UAT from `kaori/staging` passed and explicit acceptance is recorded.

A change is not `Done` merely because implementation and branch CI are complete.

## Release Impact

State Milestone/release-target impact, compatibility notes, rollout considerations, and whether release documentation changes are required. Do not invent a Milestone for work that has no release target.

## Reviewer Checklist

- [ ] Title is concise, human-readable, and follows the KAORI Conventional Commit subject style.
- [ ] Linked Issue and relationship to the requested scope are clear.
- [ ] Change matches the agreed scope and out-of-scope boundary.
- [ ] Acceptance Criteria are covered by implementation and evidence.
- [ ] Required CI is green without suppressed or bypassed failures.
- [ ] No unexpected skipped tests, traceback, assertion failure, HTTP 5xx, migration failure, or runtime failure remains unexplained.
- [ ] Generated frontend artifacts are reproducible when applicable.
- [ ] Security, migration/data, observability, and operational impacts are explicitly addressed.
- [ ] Documentation and canonical contracts are aligned.
- [ ] `kaori/staging` full-CI and Local UAT evidence exist before work is marked `Done`.
- [ ] Promotion to `main` is explicitly approved and uses a merge commit.

## Summary

In 2–4 sentences, explain what this PR changes, why it matters, and the expected outcome. A reviewer should understand the purpose without opening the diff first.

## Why

Describe the problem, operational need, product outcome, or engineering reason behind the change. Include only the context needed to understand the decision.

## What Changed

List the meaningful changes in a small number of concrete bullets. Group related changes instead of narrating every file edit.

## Out of Scope

State the important boundaries: what this PR intentionally does not change, fix, migrate, or promote.

## Linked Work

Use `Refs #<issue>` while work is still moving through staging/UAT. Use `Closes #<issue>` only on the final PR whose successful merge is intended to close the Issue.

Refs #

## Acceptance Criteria Coverage

Summarize how the linked Issue acceptance criteria are satisfied. Distinguish implementation-complete criteria from staging/UAT criteria that are still pending.

## Verification Evidence

Keep this concise and evidence-based:

- **Validated SHA:**
- **Targeted checks:**
- **Full KAORI CI:**
- **Result:**
- **Known warnings / skips:** None, or explain why they are acceptable.

Link the relevant run when useful. Do not paste raw logs into the PR body.

## Security Impact

State the trust-boundary, secret, dependency, vulnerability, authorization, or security-validation impact. Use `None — <reason>` when there is no meaningful security impact.

## Migration / Data Impact

State schema, migration, compatibility, retained-data, or data-lifecycle impact. Use `None — <reason>` when not applicable.

## Observability / Operational Impact

State logging, metrics, alerts, runtime behavior, rollback, support, deployment, or operator-workflow impact. Keep the explanation focused on what changes operationally.

## UAT

- [ ] Work-branch validation is complete.
- [ ] Integrated into `kaori/staging` and full staging CI passed.
- [ ] Local UAT from `kaori/staging` passed and explicit acceptance is recorded.

A change is not `Done` merely because implementation and branch CI are complete.

## Release Impact

State the release target or Milestone when one exists, plus compatibility/rollout considerations. Do not invent a Milestone for work without a release target.

## Reviewer Checklist

- [ ] The title is concise, human-readable, and follows the KAORI Conventional Commit subject style.
- [ ] Scope and out-of-scope boundaries are clear.
- [ ] Linked work and acceptance coverage are traceable.
- [ ] Required CI evidence is green with no unexplained failure, traceback, HTTP 5xx, migration error, runtime error, or unexpected skip.
- [ ] Security, migration/data, and operational impacts are addressed.
- [ ] Documentation/contracts are aligned when applicable.
- [ ] `kaori/staging` CI and Local UAT exist before the work is marked `Done`.
- [ ] Promotion to `main`, when applicable, is explicitly approved and uses a merge commit.

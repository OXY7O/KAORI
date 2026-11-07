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

For external fork proposals without an accepted governing Issue, reference the relevant existing Issue or (when available) Discussion for maintainer triage. Do not claim that public PR creation, an unsolicited proposal, or community review constitutes acceptance. Maintainers must accept/link a governed Issue and adopt approved changes into an issue-linked, trusted `kaori/*` work branch before entering the normal staging path.

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

For external fork PRs, record any public fork-check result separately as **feedback only**. Fork checks (when available) are not trusted Developer Check PASS, Full Admission, staging validation, or UAT evidence. Mark unexecuted checks `NOT RUN`; never infer a passing result from skipped or unavailable workflows. Trusted checks must validate the maintainer-controlled, issue-linked `kaori/*` source at its exact SHA.

## Security Impact

State the trust-boundary, secret, dependency, vulnerability, authorization, or security-validation impact. Use `None — <reason>` when there is no meaningful security impact. Never include secrets, private endpoints/hostnames, credentials, unsanitized logs, or exploitable vulnerability details in a public PR. Follow [SECURITY.md](../SECURITY.md) for private security reporting.

## Migration / Data Impact

State schema, migration, compatibility, retained-data, or data-lifecycle impact. Use `None — <reason>` when not applicable.

## Observability / Operational Impact

State logging, metrics, alerts, runtime behavior, rollback, support, deployment, or operator-workflow impact. Keep the explanation focused on what changes operationally.

## UAT

- [ ] Work-branch validation is complete.
- [ ] Integrated into `kaori/staging` and full staging CI passed.
- [ ] Local UAT from `kaori/staging` passed and explicit acceptance is recorded.

A change is not `Done` merely because implementation and branch CI are complete. For external fork submissions awaiting maintainer adoption, leave staging/UAT boxes unchecked: community review and safe fork feedback are not release or human-acceptance authority.

## Artifact / Release Evidence

Complete this section when the change enters the artifact-backed VPS/release path. Use `N/A` for normal increments that are not yet being released; do not invent values.

- **Accepted staging SHA:**
- **Registry image:**
- **Candidate tag:**
- **OCI digest:**
- **Digest-qualified image reference:**
- **VPS deployment:** `https://kaori.cloud` / N/A
- **VPS UAT:** Pending / PASS / N/A
- **UAT-approved OCI digest:**
- **Semantic Versioning release:**
- **Rollback digest:**
- **Production RUN:** Pending / PASS / N/A

For release-bound work, VPS UAT must reference the exact accepted staging SHA and OCI digest. A stable release promotes/tags that same UAT-approved OCI digest without rebuilding application bits.

## Release Impact

State the release target or Milestone when one exists, plus compatibility/rollout considerations. Do not invent a Milestone for work without a release target.

## Reviewer Checklist

- [ ] The title is concise, human-readable, and follows the KAORI Conventional Commit subject style.
- [ ] Scope and out-of-scope boundaries are clear.
- [ ] Linked work and acceptance coverage are traceable.
- [ ] Assignee, canonical labels, Project membership, lifecycle Status, Sprint, and Milestone are synchronized where applicable; Issue-only planning fields are not duplicated onto the PR.
- [ ] The PR body does not contain a duplicate `Project Metadata` table or substitute labels for Project/native fields.
- [ ] If external/community-sourced, the proposal has been triaged under a governing Issue and has not been mistaken for licensed open-source release clearance, trusted CI, or staging/UAT acceptance.
- [ ] Required CI evidence is green with no unexplained failure, traceback, HTTP 5xx, migration error, runtime error, or unexpected skip.
- [ ] Security, migration/data, and operational impacts are addressed.
- [ ] Documentation/contracts are aligned when applicable.
- [ ] New/changed feature, domain, capability, provider or verifier follows the canonical release-owner and gate-evidence format: identity, purpose/scope, actual command, honest status, duration, raw evidence, actionable failures and traceable Issue/PR/SHA (REGISTERED is not TEST PASS).

- [ ] `kaori/staging` CI and Local UAT exist before the work is marked `Done`.
- [ ] Artifact/release evidence identifies the exact accepted SHA and digest when the VPS/release path applies.
- [ ] Promotion to `main`, when applicable, is explicitly approved and uses a merge commit.
- [ ] Stable release promotion reuses the UAT-approved OCI digest without rebuilding application bits.

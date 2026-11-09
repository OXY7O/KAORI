# GitHub-native security baseline — evidence register (#4215)

**Status: PARTIALLY VERIFIED / REMAINING SECURITY ACCEPTANCE PENDING.** This register separates a historical source-only NOT VERIFIED snapshot from dated administrator evidence and actual Dependabot intake. Previous enablement and successful CI do not prove a control remains enabled today. Never paste credentials, private advisory contents, vulnerability payloads, internal infrastructure details, or unredacted scan logs into public issues, PRs, CI artifacts or Slack.

## Scope and authority

This issue covers the KAORI application repository. Verify Website and Docs independently in their owning repositories. Preserve the existing Developer Check, Full Admission, Gitleaks, Trivy, DAST, immutable OCI and release gates; this document neither replaces nor enables them. The public-source rights decision belongs to #4212 and remains **NO-GO** for license cutover.

## Historical admin evidence checklist — 2026-11-08

All ten original rows below are the **2026-11-08 source-only snapshot**, not the current effective settings. They remain **NOT VERIFIED** for this snapshot, which could not access effective GitHub security settings. Keep this history distinct from the previously verified **2026-11-05 admin** observations and **2026-11-09 public source/bot** readback below; store sanitized evidence references privately.

| Control | Current evidence state | Verification / acceptance boundary |
| --- | --- | --- |
| Dependency Graph | NOT VERIFIED | Admin confirms effective graph and manifest coverage |
| Dependabot alerts | NOT VERIFIED | Admin confirms alerts and safe sample triage |
| Dependabot security updates | NOT VERIFIED | Admin confirms eligibility and actual advisory behavior |
| Dependabot version updates | NOT VERIFIED | #4220 merged only to review holding; schedule NOT ACTIVE until configuration exists on default `main` and a bot PR is observed |
| Secret scanning | NOT VERIFIED | Admin verifies availability, coverage and alert triage without revealing findings |
| Push protection | NOT VERIFIED | Admin checks effective policy and a harmless negative test |
| CodeQL / code scanning | NOT VERIFIED | Inspect existing workflows and default/advanced setup before enabling; avoid duplicate analysis |
| Dependency review | NOT VERIFIED | Confirm effective PR check context and safe sample |
| Private vulnerability reporting | NOT VERIFIED | Admin verifies the private report entry point; do not publish a real vulnerability to test |
| Security advisory workflow | NOT VERIFIED | Confirm private maintainer access and sanitized triage/closure evidence |

## Verified code and public metadata snapshot — 2026-11-08

These statements describe **source and public repository API access**, not native GitHub Settings activation or actual alert handling:

- **Dependabot version-update configuration:** `.github/dependabot.yml` exists on `kaori/review/staging-uat` (pip `/requirements`, npm `/`, GitHub Actions `/`; weekly Asia/Jakarta; two open PRs per ecosystem) after [holding PR #4220](https://github.com/OXY7O/KAORI/pull/4220), but a root `main` file read returned **404 Not Found**. The scheduler is **NOT ACTIVE from this holding change**; version update PR intake will require admitted default-branch promotion and an actual bot-PR observation. Dependabot alerts/security updates are independent native settings and remain NOT VERIFIED.
- **Existing scanner workflows:** `.github/workflows/quality.yml` on both `main` and holding includes an existing **Security Gate** invoking `.github/ci/run-security-static.sh`, and a Trivy image scan. This is **source presence only**; neither source file establishes a successful present-day admitted scan, active GitHub CodeQL, secret scanning, push protection or private reporting.
- **CodeQL availability boundary:** There is no dedicated `.github/workflows/codeql.yml` or `.github/workflows/codeql.yaml` in either branch checked. This **does not prove CodeQL is disabled**: GitHub default setup is not represented by a dedicated repository workflow. Review the effective Code Scanning settings and a real analysis record before making any enablement, duplication or disablement decision.
- **Public-fork workflow:** `.github/workflows/community-fork-check.yml` is present only in holding, not on `main` at this observation. That code remains unadmitted; its source does not demonstrate an actual external fork run or a configured branch-protection policy. See #4214/#4278 and #4216.
- **API access limitations:** Connected repository metadata does not expose effective `security_and_analysis` state; GitHub code-scanning-alert and Actions-artifact enumeration are not supported through this interface. **NOT EXPOSED / UNSUPPORTED is not DISABLED or zero alerts**. Admin must verify privately in the owning repository and capture sanitized after-state.

**2026-11-08 activation boundary:** No admin Settings changes, release, vulnerability simulation, credential access, license cutover, official staging Full Admission or Human UAT occurred as part of this metadata snapshot. All ten checklist controls above remain **NOT VERIFIED** for that source-only observation.

## Incremental control reconciliation — 2026-11-09 (#4377)

This dated readback does **not** retroactively change the earlier snapshot.
Evidence includes the [#4215](https://github.com/OXY7O/KAORI/issues/4215)
sanitized **2026-11-05** administrator-operated WSL `gh` checks; the actual
`main` and `kaori/staging` `.github/dependabot.yml` files read on
**2026-11-09**; and original bot PRs
[#4368](https://github.com/OXY7O/KAORI/pull/4368),
[#4369](https://github.com/OXY7O/KAORI/pull/4369) and
[#4370](https://github.com/OXY7O/KAORI/pull/4370).
Exact issue-owned adoption PRs
[#4373](https://github.com/OXY7O/KAORI/pull/4373) and
[#4374](https://github.com/OXY7O/KAORI/pull/4374) were reviewed and merged
into official staging. This demonstrates **version-update advisory intake**,
not effective security control settings or live GHAS triage.

| Control | Last supported evidence | Current-state verification / boundary |
| --- | --- | --- |
| Dependency Graph | NOT VERIFIED | Actual dependency graph and manifest coverage need current admin inspection |
| Dependabot alerts | ENABLED (2026-11-05 admin readback, HTTP 204) | CURRENT NOT RECHECKED; inspect alert access and sanitized triage |
| Dependabot security updates | DISABLED (2026-11-05 admin readback) | CURRENT NOT RECHECKED; keep changes on hold until default-`main` security PR intake is governed |
| Dependabot version updates | OBSERVED ACTIVE (2026-11-09 main config and bot PRs) | `.github/dependabot.yml` now exists on default `main` with pip/npm/github-actions, bounded weekly groups and `kaori/staging` targets; #4368/#4369/#4370 were advisory and #4373/#4374 were separately governed |
| Secret scanning | ENABLED (2026-11-05 admin readback) | CURRENT NOT RECHECKED; verify effective coverage and private escalation, no finding disclosure |
| Push protection | ENABLED (2026-11-05 admin readback) | CURRENT NOT RECHECKED; check policy and bypass governance, without pushing any secret-like tokens |
| CodeQL / code scanning | NOT VERIFIED | No dedicated CodeQL workflow in current tracked workflow directory **does not prove CodeQL default setup is disabled**; inspect effective setup and actual scans |
| Dependency review | NOT VERIFIED | Inspect existing safe PR check and available entitlement before adding any action |
| Private vulnerability reporting | ENABLED (2026-11-05 admin readback) | CURRENT NOT RECHECKED; verify private reporting entry point and maintainer ownership |
| Security advisory workflow | NOT VERIFIED | PVR availability alone does not establish completed advisory triage or disclosure process |

### Current administrator readback — 2026-11-09 (supersedes historical status where verified)

The repository administrator executed authenticated `gh api` in WSL on
**2026-11-09** and supplied sanitized API responses. This is an actual
**current control settings** readback, unlike the historical source-only
snapshot. The administrator—not this documentation change—executed the
CodeQL default-setup PATCH.

| Native control | 2026-11-09 effective setting | Still required for operational acceptance |
| --- | --- | --- |
| Dependabot alerts | **ENABLED**, `GET /vulnerability-alerts` returned HTTP 204 | Actual safe, private advisory triage not yet validated |
| Dependabot security updates | **DISABLED**, repository metadata and `GET /automated-security-fixes` returned `enabled=false` | Keep intentionally disabled pending approved default-`main` security PR intake |
| Secret scanning | **ENABLED**, `security_and_analysis.secret_scanning.status=enabled` | Alert inventory and private escalation evidence |
| Push protection | **ENABLED**, `security_and_analysis.secret_scanning_push_protection.status=enabled` | Actual effective coverage and governed bypass review |
| Secret scanning non-provider patterns | **DISABLED**, current repository metadata | Optional entitlement/policy decision; do not enable blindly |
| Secret scanning validity checks | **DISABLED**, current repository metadata | Optional entitlement/policy decision; do not enable blindly |
| Private vulnerability reporting | **ENABLED**, `GET /private-vulnerability-reporting` returned `enabled=true` | Validate private reporting entry point and sanitized triage |
| CodeQL Default Setup | **CONFIGURED**, `query_suite=default`, `runner_type=standard`; initial [CodeQL Setup run #42552941921](https://github.com/OXY7O/KAORI/actions/runs/42552941921) **SUCCESS** | Three CodeQL language jobs passed, but alert inventory and actual findings triage still require authorized review |
| Dependency Graph / Dependency review / advisory handling | **NOT VERIFIED** in the supplied effective-settings readback | Confirm manifest coverage, entitlement, check behavior and restricted handling |

**CodeQL setup provenance:** `GET /code-scanning/default-setup` initially
returned `state=not-configured`. The administrator then submitted
`PATCH /code-scanning/default-setup` with
`state=configured`, `query_suite=default`, and `runner_type=standard`;
immediate readback returned `state=configured`, `languages=[]` and
`updated_at=null`. The asynchronous
[CodeQL Setup run #42552941921](https://github.com/OXY7O/KAORI/actions/runs/42552941921)
was created on default `main` source
`6c3136fa1ffb1b0f2ee37b430ce4d089c2e9f745`.
Independent workflow-job readback showed analyses for **GitHub Actions**,
**JavaScript/TypeScript**, and **Python**. The run completed **SUCCESS** and
**all three language jobs passed**. The immediate `languages=[]` response
was not interpreted as zero language coverage. This is **initial CodeQL
scan PASS**, not evidence of zero vulnerabilities or completed findings
triage. Collect permitted sanitized `code-scanning/analyses` metadata and
classify any alerts privately before full operational acceptance.

Keep the existing `quality.yml` Security Gate, Gitleaks, Bandit, Semgrep,
Trivy, dependency audits and Runtime/DAST authoritative; CodeQL adds a
GitHub-native analysis surface, **not** a replacement or duplicate workflow.
No code scanning findings, payloads or private advisory details are copied
into this public repository document. This setup does not authorize
Dependabot security-update PRs, weakening branch protection, production
release, or rights/publication GO.

**Default branch hazard:** Dependabot **version updates** are routed by
`dependabot.yml` toward `kaori/staging`; Dependabot **security update PRs
target the repository default branch `main`**. Do not enable automated
security-update PR creation until #4215/#4219 approves an issue-linked
advisory triage/adoption path that cannot bypass protected staging admission,
review, or main promotion.

### Administrator verification and safe setup

1. Inspect **OXY7O/KAORI → Settings → Advanced Security** for Dependency
   Graph, Dependabot alerts, Secret scanning, Push protection and Private
   vulnerability reporting. The 2026-11-05 values are historical: do not
   change already enabled controls merely because this connector cannot
   read the current settings. Keep screenshots and alert identifiers private.
2. **CodeQL Default Setup is configured** and setup run #42552941921
   **PASS** across all three language jobs. Independently verify sanitized
   Code Scanning analysis metadata and restricted alert triage on default
   `main`; do not confuse successful scanning with zero findings. Do
   **not** commit a second `codeql.yml` or enable a competing Advanced
   setup. Existing Gitleaks, Bandit, Semgrep, Trivy, pip-audit, npm audit
   and DAST remain authoritative for their own scopes.
3. Check **Dependency review** eligibility and an actual safe PR result
   before considering any new check. Do not silently duplicate security
   scanners, protected statuses, or an untrusted-runner execution path.
4. Verify the private **Report a vulnerability** entry point, advisory
   access controls, and sanitized triage ownership without submitting a
   live vulnerability or posting an exploit. Confirm runner/branch
   protections independently through [#4216](https://github.com/OXY7O/KAORI/issues/4216).
5. Record each control's actual observation date, authorized administrator,
   sanitized evidence ID, effective state, scanner/run result, and human
   acceptance. Keep #4215 open until actual configuration and triage are
   independently demonstrated.

**Current-state limitation:** This connector does not expose effective
`security_and_analysis`, CodeQL default setup, secret scanning alerts or
dependency review settings. `NOT EXPOSED / UNSUPPORTED` is **not** `DISABLED`
or zero findings. No admin Settings, secrets, CodeQL workflow, release,
deployment or `main` source were mutated in this documentation work.
The publication and rights assessment #4212 remains **NO-GO**. Staging
and human acceptance still require their own evidence.

## Triage and non-escalation contract

1. Route suspected vulnerabilities privately using `SECURITY.md`; do not create a public reproduction issue.
2. Classify severity, affected release/source SHA, ownership, dependency/license impact and remediation urgency without exposing payloads.
3. If a live credential is exposed, escalate privately for authorized revocation/rotation immediately; this documentation does not authorize infrastructure or secret mutations.
4. Track approved code remediation under an issue-scoped branch and the existing exact-head gates. Bot-created `dependabot/*` PRs are advisory intake, not privileged admission.
5. Keep external fork checks on GitHub-hosted read-only runners. Never use `pull_request_target` with untrusted checkout or `workflow_run` to elevate fork results.
6. Admin verifies Rulesets/required checks separately under #4216, including fork/bot negative tests before enforcement.

## Evidence needed to complete #4215

For each control, capture observation date, repository, authorized reviewer, sanitized evidence ID, effective state, and any limitation. Confirm no redundant CodeQL/security jobs; demonstrate safe dependency and vulnerability intake; reconcile `SECURITY.md` with the actual private reporting route. **Do not mark #4215 complete** without independent admin evidence, exact-head applicable checks, and human acceptance. No license/publication, release, provider, main or official staging change is authorized here.

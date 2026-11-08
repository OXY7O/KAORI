# GitHub-native security baseline — evidence register (#4215)

**Status: PREPARED / NOT VERIFIED.** This register is a maintainer handover, not proof that any GitHub Settings control is enabled. Never paste credentials, private advisory contents, vulnerability payloads, internal infrastructure details, or unredacted scan logs into public issues, PRs, CI artifacts or Slack.

## Scope and authority

This issue covers the KAORI application repository. Verify Website and Docs independently in their owning repositories. Preserve the existing Developer Check, Full Admission, Gitleaks, Trivy, DAST, immutable OCI and release gates; this document neither replaces nor enables them. The public-source rights decision belongs to #4212 and remains **NO-GO** for license cutover.

## Admin evidence checklist

Record each control's actual **ENABLED / DISABLED / UNAVAILABLE / NOT VERIFIED** state only after a GitHub administrator observes it. Until then, all controls below are **NOT VERIFIED**. Store sanitized evidence references and observation timestamps in the approved private audit location; do not publish raw screenshots of sensitive settings.

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

**Current activation boundary:** No admin Settings changes, release, vulnerability simulation, credential access, license cutover, official staging Full Admission or Human UAT occurred as part of this metadata snapshot. All ten checklist controls above remain **NOT VERIFIED**.

## Triage and non-escalation contract

1. Route suspected vulnerabilities privately using `SECURITY.md`; do not create a public reproduction issue.
2. Classify severity, affected release/source SHA, ownership, dependency/license impact and remediation urgency without exposing payloads.
3. If a live credential is exposed, escalate privately for authorized revocation/rotation immediately; this documentation does not authorize infrastructure or secret mutations.
4. Track approved code remediation under an issue-scoped branch and the existing exact-head gates. Bot-created `dependabot/*` PRs are advisory intake, not privileged admission.
5. Keep external fork checks on GitHub-hosted read-only runners. Never use `pull_request_target` with untrusted checkout or `workflow_run` to elevate fork results.
6. Admin verifies Rulesets/required checks separately under #4216, including fork/bot negative tests before enforcement.

## Evidence needed to complete #4215

For each control, capture observation date, repository, authorized reviewer, sanitized evidence ID, effective state, and any limitation. Confirm no redundant CodeQL/security jobs; demonstrate safe dependency and vulnerability intake; reconcile `SECURITY.md` with the actual private reporting route. **Do not mark #4215 complete** without independent admin evidence, exact-head applicable checks, and human acceptance. No license/publication, release, provider, main or official staging change is authorized here.

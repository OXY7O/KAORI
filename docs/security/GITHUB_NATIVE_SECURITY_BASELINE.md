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
| Dependabot version updates | NOT VERIFIED | #4220 is Draft; schedule requires accepted default-branch config and observed bot PR |
| Secret scanning | NOT VERIFIED | Admin verifies availability, coverage and alert triage without revealing findings |
| Push protection | NOT VERIFIED | Admin checks effective policy and a harmless negative test |
| CodeQL / code scanning | NOT VERIFIED | Inspect existing workflows and default/advanced setup before enabling; avoid duplicate analysis |
| Dependency review | NOT VERIFIED | Confirm effective PR check context and safe sample |
| Private vulnerability reporting | NOT VERIFIED | Admin verifies the private report entry point; do not publish a real vulnerability to test |
| Security advisory workflow | NOT VERIFIED | Confirm private maintainer access and sanitized triage/closure evidence |

## Triage and non-escalation contract

1. Route suspected vulnerabilities privately using `SECURITY.md`; do not create a public reproduction issue.
2. Classify severity, affected release/source SHA, ownership, dependency/license impact and remediation urgency without exposing payloads.
3. If a live credential is exposed, escalate privately for authorized revocation/rotation immediately; this documentation does not authorize infrastructure or secret mutations.
4. Track approved code remediation under an issue-scoped branch and the existing exact-head gates. Bot-created `dependabot/*` PRs are advisory intake, not privileged admission.
5. Keep external fork checks on GitHub-hosted read-only runners. Never use `pull_request_target` with untrusted checkout or `workflow_run` to elevate fork results.
6. Admin verifies Rulesets/required checks separately under #4216, including fork/bot negative tests before enforcement.

## Evidence needed to complete #4215

For each control, capture observation date, repository, authorized reviewer, sanitized evidence ID, effective state, and any limitation. Confirm no redundant CodeQL/security jobs; demonstrate safe dependency and vulnerability intake; reconcile `SECURITY.md` with the actual private reporting route. **Do not mark #4215 complete** without independent admin evidence, exact-head applicable checks, and human acceptance. No license/publication, release, provider, main or official staging change is authorized here.

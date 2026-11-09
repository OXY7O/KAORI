# GitHub-native third-party SAST and DAST findings — reporting boundary

**Authority:** [#4390](https://github.com/OXY7O/KAORI/issues/4390) (SAST), [#4391](https://github.com/OXY7O/KAORI/issues/4391) (DAST), under #4215. Separate CodeQL protected-staging trigger investigation #4388 remains open.

**Current status (2026-11-09):** Semgrep SAST source publishing is **accepted on protected staging** at `a149825dfdfa03830cdeba6993fe62a2de51580d`; native SARIF ingestion completed successfully in the GitHub security provider. **Human security/UI acceptance remains pending**, and the current scan reported no Semgrep results under its ruleset. DAST/ZAP SARIF publication remains **NOT APPROVED** until its separate privacy and truthful-location evidence is accepted. Do not equate this technical SAST ingestion with rights GO, CodeQL staging coverage, DAST Code scanning visibility, production readiness or zero vulnerabilities.

## Source of truth and destinations

The existing **Full Admission Security** gate remains authoritative for security policy:
`.github/ci/run-security-static.sh` runs Gitleaks (redacted), Bandit, Semgrep OSS, dependency audits and workflow security lint; `.github/ci/run-runtime-validation.sh` runs isolated OWASP ZAP baseline against the container under test; Runtime & DAST also scans the production image with Trivy.

GitHub Actions artifacts and gate exit statuses are **execution evidence**, not persisted Code Scanning findings. GitHub **Security and quality → Code scanning** ingests supported third-party SARIF 2.1.0 reports by tool/category and branch commit. Do not equate a scanner PASS (possibly zero findings) with proof of zero vulnerabilities.

## Semgrep (first bounded SAST reporting slice, #4390)

- Existing approved Semgrep OSS rulebook: `.github/ci/semgrep.yml`; pinned Semgrep version comes from `.github/ci/requirements-security.txt`.
- The independently permissioned `.github/workflows/security-findings-publish.yml` runs on **trusted push events only** for `kaori/staging` and `main`. It checks out the event's exact `github.sha`, builds the **existing canonical** CI toolchain, scans the same `app scripts frontend` scope and exclusions, uses Semgrep's **native** SARIF output, validates its SARIF structure and uploads with pinned `github/codeql-action/upload-sarif`.
- The reporter is necessary because KAORI staging integration may correctly reuse a previously admitted source through **Fast Smoke**; Full Admission then has **no fresh SAST execution or SARIF artifact on that staging push**. A trusted source-branch analysis at the accepted merge SHA must not be falsely inferred from a PR-specific report or from reused CI.
- The job alone has `security-events: write`; its workflow does **not** run on `pull_request`, `pull_request_target`, `workflow_run`, forks or arbitrary branches, and does not grant this permission to Developer Check or Full Admission.
- SARIF category is stable: `kaori-sast-semgrep`. The uploaded finding locations are the real checked-out repository paths reported by Semgrep. CodeQL Default Setup is unaffected, and the reporting action is **not** a CodeQL analysis.
- `--error` is preserved. The reporter may upload a valid SARIF report containing findings **and still fail** the workflow when Semgrep returns failure. Upload errors and malformed reports likewise fail visibly. No `continue-on-error` outcome is accepted as a successful scan.
- The existing Security gate is unchanged. Nothing about this uploader downgrades or suppresses Bandit, Semgrep, Gitleaks, Trivy, ZAP, pip-audit, npm audit, CodeQL or other CI.
- This first slice **does not yet publish Bandit or Trivy**; both require separate approved native SARIF/provenance verification. Native SARIF must come from existing scanners rather than inventing findings or duplicating CodeQL.

## Actual Semgrep staging evidence (2026-11-09)

- [PR #4395](https://github.com/OXY7O/KAORI/pull/4395) was independently approved, had all selected exact-head Ready Full Admission jobs PASS, and merged by protected PR to official `kaori/staging@a149825dfdfa03830cdeba6993fe62a2de51580d`.
- Exact-merge [Full Admission #42574899860](https://github.com/OXY7O/KAORI/actions/runs/42574899860) **SUCCESS** on Fast Smoke and CI Admission. This does **not** imply the full matrix reran on this push.
- Separately, accepted-SHA [Security Findings Publication #42574899895](https://github.com/OXY7O/KAORI/actions/runs/42574899895) **SUCCESS**: Semgrep OSS generated SARIF **2.1.0** with `results=[]` on this policy/snapshot; the pinned upload action emitted `Successfully uploaded results` and `Analysis upload status is complete.` The active distinct category is `kaori-sast-semgrep`; this is a platform-processed **zero-result analysis**, not a claim of zero code vulnerabilities.
- The connected GitHub tooling does not expose the Code scanning **analyses listing**. A security owner must confirm the actual Security and quality UI record filtered by **Semgrep OSS**, `refs/heads/kaori/staging`, category `kaori-sast-semgrep`, accepted SHA, and verify no sensitive source material is unexpectedly disclosed. Record human acceptance before closing #4390 or reporting broad baseline completion.
- Existing GitHub-managed CodeQL Default Setup is independent and missing staging analysis remains #4388. Bandit, Trivy, Gitleaks and ZAP are **not** uploaded by this Semgrep-specific publisher.

## DAST and sensitive evidence policy (#4391)

The current ZAP baseline writes `baseline.html` and `baseline.json` under `tmp/ci-artifacts/zap`, with isolated CI runtime target `http://runtime:5000/`. The ZAP report-generation add-on has an official `sarif-json` template, but sample SARIF includes target URLs, probe text, cookies, HTTP headers and response bodies. **Never upload these raw fields to the public GitHub Security tab.**

For endpoint-only findings, an ephemeral HTTP URL is **not** a repository source path and must not be mapped to an invented file or line number. DAST findings without approved truthful source-location mapping remain **Actions security evidence** and source-traceable remediation issues, not fabricated Code Scanning alerts. The DAST workstream must test privacy redaction, valid SARIF source locations, provider feature compatibility and security ownership before enabling upload. No external scan targets, active attacks or production DAST are authorized here.

### DAST Code scanning eligibility and privacy decision gate (2026-11-09)

The official [ZAP `sarif-json` report sample](https://www.zaproxy.org/docs/desktop/addons/report-generation/report-sarif-json/) places scanned HTTP URLs (including query parameters and injected text) in `locations[].physicalLocation.artifactLocation.uri`. It also demonstrates request headers, cookies, response content, attack values and snippets as report fields. This is **not safe-by-default** for public GitHub Code scanning. Our current `-J baseline.json` is ZAP traditional JSON, not SARIF, and its existing warning dispositions remain authoritative.

[GitHub's SARIF requirements](https://docs.github.com/en/code-security/reference/code-scanning/sarif-files/sarif-support) use the result's first `locations[]` element as a source artifact location for annotations, and interpret uploaded paths relative to committed repository files where possible. An ephemeral ZAP target such as `http://runtime:5000/` is **not** a committed source file. Removing the URL is not permission to replace it with an invented `app/...` line number. A location-less result may not appear as an actionable Code scanning alert.

| Observed DAST report classification | Approved presentation until further review | Condition to enter Code scanning |
| --- | --- | --- |
| Alert with verified mapping to an actual offending repository source file and relevant lines | Restricted ZAP artifact and Actions gate (existing) | Security reviewer validates truthful and reproducible source correlation plus sanitized, synthetic-format SARIF and publication impact |
| Runtime/endpoint/header/configuration alert without trustworthy source-code location | Restricted ZAP HTML/JSON artifact, reviewed disposition and Actions evidence | **No SARIF Code scanning upload** solely for appearance; retain as DAST evidence or create a governed remediation issue |
| Alert carrying a runtime route, query/credential, cookie, body, attack string, session identifier or internal target | Protected evidence only; no raw public alert | Must prove lossless-enough privacy sanitization (no sensitive fields), safe result identity and approved source mapping before any publication |
| No alerts observed in one ZAP baseline | Existing exact-run scan status/evidence; no DAST SARIF claim | Do not synthesize a zero-result DAST Code scanning analysis unless this reporting capability has been separately validated and approved |

**Next required proof under #4391:** use **synthetic local test data only** to exercise ZAP traditional JSON and optional SARIF conversion and assert that every publicly exported field excludes private URL/host/path/query, Authorization/Cookie, request/response bodies, injection payload and user/session identifiers. Confirm that every retained finding has reviewer-approved source-location mapping with stable rules/partial fingerprints, or reject upload explicitly without silently dropping findings. Then seek independent security/privacy acceptance **before** adding any trusted-push reporter. Do not change ZAP scan scope, `-I`, existing warning dispositions, CI severity, deployment or production targets for reporting convenience.

Gitleaks secret matches and raw provider credentials must also **never** be published through SARIF. Existing redaction/push protection remains authoritative.

## Evidence and UAT

For SAST, after approval and staging merge, capture the SHA, GitHub Actions workflow run and conclusion, uploaded SARIF processing result, Code Scanning **analysis** `ref=refs/heads/kaori/staging`, `commit_sha`, `category`, `created_at`, tool identity, and alert count. A successful empty SARIF is a legitimate **zero-findings report**, not a missing analysis. An absent analysis remains **NOT VERIFIED**.

For DAST, keep source authorization and a separate redacted offline contract proving no sensitive URLs, headers, bodies, cookies, exploit text or fake source paths enter public SARIF.

Before declaring UAT/production readiness: pin the accepted source/merge SHA, prove output validity and non-disclosure, inspect permissions on the actual push run, verify no fork elevation, confirm full existing KAORI release/security checks and obtain independent human/security acceptance. Main promotion and release remain separately governed.

## Rollback

Revert the scoped issue-linked workflow if ingestion is incompatible or unstable, using the normal KAORI staging-first review path. Do not rewrite/dismiss existing Code Scanning alerts or reconfigure CodeQL Default Setup as a rollback.

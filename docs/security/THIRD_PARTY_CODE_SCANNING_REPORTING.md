# GitHub-native third-party SAST and DAST findings — reporting boundary

**Authority:** [#4390](https://github.com/OXY7O/KAORI/issues/4390) (SAST), [#4391](https://github.com/OXY7O/KAORI/issues/4391) (DAST), under #4215. Separate CodeQL protected-staging trigger investigation #4388 remains open.

**Candidate status:** source proposal until official Developer Check, Ready Full Admission, staging CI and human/security UAT accept a pinned commit. Do not treat this design document as an active GitHub Security configuration or proof of scan ingestion.

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

## Bandit native SARIF — proposed second trusted SAST slice (#4390)

The **existing admitted Semgrep publisher** has a separate, verified protected
staging report (`Semgrep OSS`, category `kaori-sast-semgrep`, commit
`a149825dfdfa03830cdeba6993fe62a2de51580d`); the maintainer confirmed
Semgrep OSS is visible in Security and quality. **Bandit is a separate candidate**
until its own exact-SHA branch upload, security inspection and Human Acceptance
are complete. Its stable planned category is `kaori-sast-bandit`.

The current Full Admission `.github/ci/run-security-static.sh` stays
authoritative: `bandit -r app scripts -q -ll -f json` writes the original
`bandit.json` evidence, with the same Medium-or-higher severity threshold,
noise contract, exit code and failure handling. The accepted-commit publisher
reuses **the same Bandit version, targets and flags** for a native **SARIF**
format report; it does not relabel PR-head evidence as staging data and does
not weaken the existing JSON-gated scan.

Native Bandit SARIF 2.1.0 uses the upstream optional `sarif` formatter, not
a local JSON converter. The candidate preserves `bandit[sarif]==1.9.4` and
explicitly pins `jschema-to-python==1.2.3` and `sarif-om==1.0.4` in the
existing security toolchain requirements. Because the optional libraries are
older packages, the full Security gate and independent supply-chain/security
review must confirm their suitability before merge; a dependency-inventory
declaration alone is not risk acceptance.

The trusted `.github/workflows/security-findings-publish.yml` job retains
a single GitHub-hosted job-scoped `security-events: write` token and the
exact `github.sha` checkout. It uploads the **Bandit** native SARIF as a
second, separately categorized analysis using the existing pinned uploader.
Both scanner exits, both SARIF validations and both uploads are checked in
the final fail-closed job outcome, including when a scanner produced valid
findings but returned a nonzero status. A completed upload with zero results
proves **only that scan**; a missing analysis is a reporting defect.

**Pre-acceptance test:** the existing pytest security contract executes
the native Bandit formatter on a synthetic no-findings Python fixture and
checks valid SARIF version, actual tool identity and results. Required
postmerge UAT: inspect the **Bandit** tool on
`refs/heads/kaori/staging`, category `kaori-sast-bandit`,
exact merge commit, scanner threshold and alert privacy; separately verify
Semgrep `kaori-sast-semgrep` remains unchanged. No third-party scanner
may transmit secret matches or raw DAST requests as a surrogate report.

## DAST and sensitive evidence policy (#4391)

The current ZAP baseline writes `baseline.html` and `baseline.json` under `tmp/ci-artifacts/zap`, with isolated CI runtime target `http://runtime:5000/`. The ZAP report-generation add-on has an official `sarif-json` template, but sample SARIF includes target URLs, probe text, cookies, HTTP headers and response bodies. **Never upload these raw fields to the public GitHub Security tab.**

For endpoint-only findings, an ephemeral HTTP URL is **not** a repository source path and must not be mapped to an invented file or line number. DAST findings without approved truthful source-location mapping remain **Actions security evidence** and source-traceable remediation issues, not fabricated Code Scanning alerts. The DAST workstream must test privacy redaction, valid SARIF source locations, provider feature compatibility and security ownership before enabling upload. No external scan targets, active attacks or production DAST are authorized here.

Gitleaks secret matches and raw provider credentials must also **never** be published through SARIF. Existing redaction/push protection remains authoritative.

## Evidence and UAT

For SAST, after approval and staging merge, capture the SHA, GitHub Actions workflow run and conclusion, uploaded SARIF processing result, Code Scanning **analysis** `ref=refs/heads/kaori/staging`, `commit_sha`, `category`, `created_at`, tool identity, and alert count. A successful empty SARIF is a legitimate **zero-findings report**, not a missing analysis. An absent analysis remains **NOT VERIFIED**.

For DAST, keep source authorization and a separate redacted offline contract proving no sensitive URLs, headers, bodies, cookies, exploit text or fake source paths enter public SARIF.

Before declaring UAT/production readiness: pin the accepted source/merge SHA, prove output validity and non-disclosure, inspect permissions on the actual push run, verify no fork elevation, confirm full existing KAORI release/security checks and obtain independent human/security acceptance. Main promotion and release remain separately governed.

## Rollback

Revert the scoped issue-linked workflow if ingestion is incompatible or unstable, using the normal KAORI staging-first review path. Do not rewrite/dismiss existing Code Scanning alerts or reconfigure CodeQL Default Setup as a rollback.

# GitHub-native third-party SAST and DAST findings — reporting boundary

**Authority:** [#4390](https://github.com/OXY7O/KAORI/issues/4390) (SAST), [#4391](https://github.com/OXY7O/KAORI/issues/4391) (DAST), under #4215. Separate CodeQL protected-staging trigger investigation #4388 remains open.

**Accepted reporting status (2026-11-10):** **Semgrep OSS** and **Bandit** SARIF publication are accepted under [#4390](https://github.com/OXY7O/KAORI/issues/4390), with recorded **SAST Human UAT PASS** on 2026-11-09. Their exact staging analyses on `b7cad6bacc80b85d9dbf532473abbee968186d62` are Semgrep `2124818618` (`kaori-sast-semgrep`, 0 findings) and Bandit `2124825336` (`kaori-sast-bandit`, 0 findings); these zero results cover only the respective scanner rules and accepted source SHA. Both reporter jobs also **SUCCESS** on protected staging `fab300550e0a655218282fee887003cdb53b1e0c` in [run #42739505684](https://github.com/OXY7O/KAORI/actions/runs/42739505684), but this workflow success is not a fresh per-tool Code Scanning API readback. **DAST** has an accepted safe **Actions** summary implementation (PR #4401, issue #4400), **not** a GitHub Code scanning SARIF analysis; independent DAST Human Security UAT remains **PENDING**. Native CodeQL protected-staging coverage remains **NOT VERIFIED** under [#4388](https://github.com/OXY7O/KAORI/issues/4388). No scanner gate was replaced or downgraded.

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
- Semgrep staging technical ingestion **PASS**: [PR #4395](https://github.com/OXY7O/KAORI/pull/4395), publisher [run #42574899895](https://github.com/OXY7O/KAORI/actions/runs/42574899895), GitHub analysis `2124505346` at exact staging commit. `results_count=0` reflects **Semgrep rules/scope only**, not zero vulnerabilities. The subsequent scoped Human UAT PASS and Bandit analysis are recorded above; Trivy remains outside this publication scope.

## Bandit (second bounded SAST reporting slice, #4390)

- The **mandatory** Python Security gate remains `bandit -r app scripts -q -ll -f json`, with its JSON evidence, exit policy and fail-fast interpretation unchanged.
- Native SARIF is enabled using pinned `bandit[sarif]==1.9.4` plus pinned native formatter dependencies `sarif-om==1.0.4`, `jschema-to-python==1.2.3`; these are installed by the existing canonical CI toolchain, not a new scanner or an unmanaged installer.
- A separate **Bandit Code Scanning** job in the same protected push-only publication workflow runs identical `app scripts` recursive scope, `-q -ll` severity/confidence thresholds, and outputs `bandit.sarif` with Bandit's supported native `-f sarif` formatter. The original Semgrep job, category and verified ingestion path remain unchanged.
- Bandit upload uses the existing pinned `github/codeql-action/upload-sarif` action with a **distinct, stable** `kaori-sast-bandit` category, job-scoped `security-events: write`, exact committed `github.sha` and `wait-for-processing: true`. GitHub explicitly separates different tool/category reports on the same commit.
- A synthetic local contract exercises native SARIF from an intentionally insecure **temporary test fixture**, confirms a real Bandit finding with its actual source path and line, and never uploads that fixture or finding. This is not a finding in KAORI source code.
- Any scanner finding preserves its failure outcome; a successfully uploaded report with findings **does not** turn a failed security scan into PASS. Missing SARIF, wrong tool identity or failed GitHub processing likewise produces a failed reporter. Actual staging branch API analysis metadata and independent security acceptance were subsequently recorded for the accepted `b7cad6ba` source under #4390; each later branch commit must still be checked against its own evidence.
- Source locations and snippets in native Bandit SARIF describe existing committed Python code; **do not** upload any credential, arbitrary secret match, private runtime payload or untrusted externally supplied report. Gitleaks remains redacted/private.


## DAST and sensitive evidence policy (#4391)

The current ZAP baseline writes `baseline.html` and `baseline.json` under `tmp/ci-artifacts/zap`, with isolated CI runtime target `http://runtime:5000/`. The ZAP report-generation add-on has an official `sarif-json` template, but sample SARIF includes target URLs, probe text, cookies, HTTP headers and response bodies. **Never upload these raw fields to the public GitHub Security tab.**

For endpoint-only findings, an ephemeral HTTP URL is **not** a repository source path and must not be mapped to an invented file or line number. DAST findings without approved truthful source-location mapping remain **Actions security evidence** and source-traceable remediation issues, not fabricated Code Scanning alerts. The DAST workstream must test privacy redaction, valid SARIF source locations, provider feature compatibility and security ownership before enabling upload. No external scan targets, active attacks or production DAST are authorized here.

### DAST sanitized GitHub Actions evidence (accepted implementation 2026-11-10)

- Under [#4400](https://github.com/OXY7O/KAORI/issues/4400), [PR #4401](https://github.com/OXY7O/KAORI/pull/4401) was independently approved and merged to protected `kaori/staging` at `fab300550e0a655218282fee887003cdb53b1e0c`. The implementation reuses **only** the existing ZAP traditional JSON after an actual `Runtime & DAST` run and publishes a strict numeric-allowlisted `sanitized-summary.md` to that run's GitHub Actions summary and three-day artifact. It does not add a scanner, expand targets, turn runtime URLs into source locations, or upload DAST SARIF to GitHub Code scanning.
- [Ready Full Admission #42734807019](https://github.com/OXY7O/KAORI/actions/runs/42734807019) executed full Runtime & DAST on reviewed source `c36feac9c4f5e461e3c24571529b5d0194d89b1a`. The authoritative ZAP CLI reported **FAIL-NEW 0, WARN-NEW 6, PASS 62**. The independently inspected sanitized artifact `full-admission-zap-safe-summary-42734807019-1` reported **High 0, Medium 2, Low 0, Informational 7; total 9 grouped alert records in one scanned site**. Grouped JSON alert records are **not** ZAP CLI rule-family counts and must not be presented as the same metric. The sanitized artifact contains no runtime URL/host/path, query, cookie, headers, body, attack snippet or free-text finding.
- The exact-merge staging [Full Admission #42739505361](https://github.com/OXY7O/KAORI/actions/runs/42739505361) used **Fast Smoke + CI Admission** and passed; [Security Findings Publication #42739505684](https://github.com/OXY7O/KAORI/actions/runs/42739505684) and [Branch Hygiene #42739505341](https://github.com/OXY7O/KAORI/actions/runs/42739505341) also passed. **Fast Smoke is not a fresh DAST scan** and must not emit a new ZAP summary for the merge SHA.
- **Human Security UAT/privacy acceptance is still pending for #4400**. Neither successful CI nor the absence of FAIL-NEW authorizes DAST SARIF publication, issue closure, `main` promotion or release. The Code scanning eligibility policy below remains a separate decision under #4391.

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

For DAST, preserve the synthetic privacy-negative contract and inspect the published allowlisted **Actions summary** (not public SARIF). A separate SARIF publication would require independent, explicit privacy approval and reproducible truthful source-file/line mapping under #4391.

Before declaring UAT/production readiness: pin the accepted source/merge SHA, prove output validity and non-disclosure, inspect permissions on the actual push run, verify no fork elevation, confirm full existing KAORI release/security checks and obtain independent human/security acceptance. Main promotion and release remain separately governed.

## Rollback

Revert the scoped issue-linked workflow if ingestion is incompatible or unstable, using the normal KAORI staging-first review path. Do not rewrite/dismiss existing Code Scanning alerts or reconfigure CodeQL Default Setup as a rollback.

# Security Policy

KAORI is currently maintained as an internal-use platform. Security reports must be handled privately so operators have time to validate impact, protect infrastructure, and prepare a governed fix before disclosure.

## Supported versions

Security fixes are prioritized for the currently governed release line and the active `kaori/staging` candidate. Historical product-baseline documentation may remain in the repository for traceability, but it does not imply ongoing security support for every historical version.

## Reporting a vulnerability

Use a private repository security-reporting channel available to the authorized KAORI maintainers. When GitHub Private Vulnerability Reporting / Security Advisories are enabled, prefer that channel. If it is not available, contact the repository maintainers through an approved private organizational channel.

Do **not** open a public Issue, Discussion, pull request, or commit containing exploitable details, credentials, private host information, tokens, keys, production configuration, or proof-of-concept material that could expose a live environment.

A useful report includes:

- affected KAORI version, tag, source SHA, or component;
- impact and preconditions;
- reproducible steps using sanitized/non-production data;
- relevant logs with secrets and private infrastructure details removed;
- recommended mitigation when known.

## Response boundary

Maintainers will validate the report, classify severity and affected release lines, track remediation through the governed KAORI Issue/branch/PR/validation flow, and coordinate disclosure when appropriate. An acknowledgement or technical deployment is not the same as release acceptance; security repairs remain subject to the applicable validation and promotion gates.

## Secrets and infrastructure

Never include real API tokens, SSH keys, passwords, private certificates, internal addresses, or production environment files in a report or repository artifact. If sensitive material is accidentally exposed, treat rotation/revocation as a separate immediate operational action rather than waiting for the software fix.

## Scope

This policy covers KAORI-owned source and delivery surfaces. Vulnerabilities in third-party dependencies or infrastructure should still be reported when they materially affect KAORI, but upstream remediation and third-party disclosure rules may also apply.

## Private advisory triage and GitHub-native controls

This is a maintainer procedure, **not** evidence that any GitHub repository setting is enabled. Record effective Settings and scan evidence under [#4215](https://github.com/OXY7O/KAORI/issues/4215) before marking a control operational.

| Intake classification | Initial handling | Disclosure and release boundary |
| --- | --- | --- |
| Critical: confirmed active credential exposure or exploitable production impact | Privately escalate immediately; isolate affected access and coordinate credential rotation/revocation under separate operational authority | Keep identifiers and reproduction private; no public issue or automatic release |
| High: exploitable vulnerability with material impact and credible preconditions | Privately assign remediation owner and scope affected source SHA, versions and dependencies | Governed security fix, regression test and required admission before release |
| Medium/Low: bounded weakness, hardening or dependency finding | Deduplicate against existing advisory/issue and assess reachability, severity and compensating controls | Use sanitized engineering issue only when disclosure is safe; do not publish proof of exploit |
| Unconfirmed / informational | Request sanitized evidence through private channel and document assessment outcome | No claim of confirmed exposure or successful scan |

For each private report, maintain a restricted evidence record: intake timestamp, affected release/source SHA, severity rationale, owner, containment status, remediation issue/PR, actual scanner results, validation SHA, disclosure decision and reviewer acceptance. **Never** copy raw secret values, private advisories, exploit steps or private logs into public Issues, PRs, CI summaries or Slack.

Before enabling or claiming a GitHub-native control, verify the effective repository/organization setting and an applicable test result for Dependency Graph, Dependabot alerts and security updates, secret scanning and push protection, CodeQL/code scanning, dependency review, and private vulnerability reporting. Existing CodeQL, Gitleaks, Trivy, SBOM/attestation and DAST workflows must be inventoried first to avoid duplicate scanning or conflicting required checks. Mark unavailable, unverified and skipped controls explicitly; a green unrelated CI job is not proof that a control is enabled.

Security advisories and public community feedback remain separate intake channels. External contribution launch and license changes remain blocked by the independent rights and publication review [#4212](https://github.com/OXY7O/KAORI/issues/4212).

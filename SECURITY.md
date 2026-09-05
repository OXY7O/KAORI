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

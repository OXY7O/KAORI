# Public-source exposure and rights audit — evidence boundary (#4212)

**Decision: NO-GO for relicensing and external contribution launch.** Public repository visibility is already an exposure fact, not publication or ownership approval. This checklist is an evidence collection plan; none of the categories below is attested complete.

## Coverage register

| Surface | Required evidence | Status |
| --- | --- | --- |
| Tracked HEAD tree | Sanitized inventory and classification of source, examples, templates, deployment documentation, screenshots and generated content | NOT VERIFIED |
| Full Git history | All reachable branches, tags and historical blobs assessed for credentials, private IP/host/operator records and rights | NOT VERIFIED |
| GitHub releases and assets | Releases, attached binaries, archives, SBOMs and published artifacts inventoried | NOT VERIFIED |
| Workflow logs and artifacts | Retention and public accessibility reviewed; findings privately triaged | NOT VERIFIED |
| Third-party rights | Dependency licenses, vendored code, fonts, logos, screenshots and documentation provenance verified | NOT VERIFIED |
| Organization ownership | Contributor grants, trademark/brand authority and copyright chain verified | NOT VERIFIED |
| Website and Docs | Independent owner-repository audits and generated-site publication checks | NOT VERIFIED |
| Secret-scanning effectiveness | Existing Gitleaks/GitHub controls and historical coverage independently evidenced | NOT VERIFIED |

## Evidence handling

Record repository, surface, bounded time window, scan/tool identity, reviewed ref or artifact identifier, reviewer, observation time, sanitized evidence ID and disposition in the approved private audit location. Public issues/PRs/Slack receive only non-sensitive coverage status and references. Do not paste credential values, private URLs, screenshots with sensitive data, or vulnerability reproduction. A confirmed active credential exposure is a private security incident requiring separately authorized rotation/revocation, not a public Issue attachment.

## Acceptance gate

A tracked-tree scan alone cannot establish history, release, artifact or rights coverage. Keep **NO-GO** until independent evidence covers all surfaces for KAORI, Website and Docs; ownership and third-party attribution decisions are explicit; active exposure has been privately handled; and the maintainer records a per-repository GO decision. Do not change `LICENSE`, `NOTICE`, SPDX identifiers, SaaS claims, public contribution settings, release authority or production infrastructure under this issue.

Related: #4211 foundation, #4213 license reconciliation, #4215 security baseline, #4214 fork-safe CI, OXY7O/kaori-website#136/#137, OXY7O/kaori-docs#74/#75.

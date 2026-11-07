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

## Verified public repository metadata — 2026-11-08 (limited scope)

Read-only GitHub repository metadata and root `LICENSE` file reads established only the **current public/default-branch disclosure posture** below. These reads do not scan previous Git history, secret values, published build output, release assets, logs, third-party rights or contributor grants. They are **not** a per-repository publication or relicensing GO.

| Repository | Visibility / default branch | Root code/content license on default branch | Finding |
| --- | --- | --- | --- |
| [OXY7O/KAORI](https://github.com/OXY7O/KAORI) | `public` / `main` | `KAORI INTERNAL USE LICENSE` | Published source is not yet licensed for unrestricted OSI reuse |
| [OXY7O/kaori-website](https://github.com/OXY7O/kaori-website) | `public` / `main` | Root `LICENSE` absent | Website source and protected brand/material scopes require explicit license and rights review |
| [OXY7O/kaori-docs](https://github.com/OXY7O/kaori-docs) | `public` / `main` | `KAORI INTERNAL USE LICENSE` | Code and publication-approved content require separately accepted rights/licensing scope |

**Observed controls are not sign-off:** Public visibility is enabled for all three repositories and is not equivalent to open-source licensing. The current approved *proposal* is Apache-2.0 for rights-cleared source code and a distinct CC BY 4.0 scope for approved public documentation, with brand/trademark and third-party exclusions. No current license file was changed. Default-branch metadata says nothing about private history, previous releases or legal ownership; retain all eight coverage categories as **NOT VERIFIED** until their independent evidence is accepted.

## Public release and workflow metadata snapshot — 2026-11-08

These are **read-only, public GitHub REST snapshots**; they are useful for prioritizing audit coverage, not a security scan or publication-rights sign-off. A public `GET /repos/{owner}/{repo}/releases?per_page=100` returned fewer than 100 entries for every repository. A separate `GET /repos/{owner}/{repo}/actions/runs?per_page=1` returned an API `total_count` but did not enumerate all run records or read logs.

| Repository | Visible GitHub Releases | Prerelease / stable | Attached Release assets in visible records | Actions workflow runs (API reported `total_count`) |
| --- | ---: | ---: | ---: | ---: |
| `OXY7O/KAORI` | 1 | 1 / 0 | 0 | 3,583 |
| `OXY7O/kaori-website` | 7 | 5 / 2 | 0 | 251 |
| `OXY7O/kaori-docs` | 9 | 9 / 0 | 0 | 222 |

**Coverage qualification:** `0 attached Release assets` means only that the release objects returned by this public API listed no attached GitHub Release assets **at the observation time**; it does **not** mean no registry OCI images, tags, deleted assets, workflow artifacts, logs or past public exposure exist. The Actions `total_count` numbers are only point-in-time provider-reported counts, **not** a completed pagination or a reviewed run-history corpus. Draft or inaccessible releases and historical deletions cannot be ruled out from these public reads. Values can change as workflows and releases run.

**Access limitation:** Attempts to query the public repository Actions artifact metadata endpoint through the connected read-only GitHub fetch interface were **unsupported**; its absence is **NOT VERIFIED**, not zero. Code-scanning alert API access through that interface was also unsupported; no disabled/enabled assertion is made. The existing sanctioned sanitized inventory tools (`scripts/publication_release_assets_inventory.py`, `scripts/publication_actions_inventory.py`, and `scripts/publication_workflow_runs_inventory.py`) require authenticated review in an approved environment, and they intentionally do not inspect artifact/log contents. Their existence does not establish that any audit was executed.

**Remaining review requirement:** Inspect publication history, attached/registry artifacts, retained workflow logs and contents, independently verify active secret exposure and third-party ownership, and collect per-repository reviewer evidence privately. Keep the eight coverage surfaces **NOT VERIFIED** and the overall relicensing/contributor launch decision **NO-GO**.

## Evidence handling

Record repository, surface, bounded time window, scan/tool identity, reviewed ref or artifact identifier, reviewer, observation time, sanitized evidence ID and disposition in the approved private audit location. Public issues/PRs/Slack receive only non-sensitive coverage status and references. Do not paste credential values, private URLs, screenshots with sensitive data, or vulnerability reproduction. A confirmed active credential exposure is a private security incident requiring separately authorized rotation/revocation, not a public Issue attachment.

## Acceptance gate

A tracked-tree scan alone cannot establish history, release, artifact or rights coverage. Keep **NO-GO** until independent evidence covers all surfaces for KAORI, Website and Docs; ownership and third-party attribution decisions are explicit; active exposure has been privately handled; and the maintainer records a per-repository GO decision. Do not change `LICENSE`, `NOTICE`, SPDX identifiers, SaaS claims, public contribution settings, release authority or production infrastructure under this issue.

Related: #4211 foundation, #4213 license reconciliation, #4215 security baseline, #4214 fork-safe CI, OXY7O/kaori-website#136/#137, OXY7O/kaori-docs#74/#75.

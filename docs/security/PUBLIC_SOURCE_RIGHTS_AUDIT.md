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

## Incremental public metadata readback — 2026-11-09 (NO-GO unchanged)

This is a **bounded, read-only public GitHub REST snapshot** collected for #4212,
not a replacement for the previous dated snapshots or a completed risk/rights
assessment. Each `main` ref was resolved and its current recursive tracked tree
enumerated; GitHub reported `truncated=false` for **each** tree. These counts
cover current reachable tracked paths at the specified commit **only**, not
historical, deleted, hidden, registry, generated or untracked material.

| Repository | Exact default-main SHA | Current tracked blobs / tree entries | Returned GitHub Releases / attached assets | Provider-reported Actions run count |
| --- | --- | ---: | ---: | ---: |
| [KAORI](https://github.com/OXY7O/KAORI) | `6c3136fa1ffb1b0f2ee37b430ce4d089c2e9f745` | 4,810 / 5,396 | 2 / 0 | 3,705 |
| [Website](https://github.com/OXY7O/kaori-website) | `41091df060e406e2ade7ae63fc67bc65c4454559` | 66 / 87 | 9 / 0 | 392 |
| [Docs](https://github.com/OXY7O/kaori-docs) | `6915fb97c5f53d8e5043876d51401d08bd683879` | 46 / 62 | 9 / 0 | 264 |

For release metadata, the read used `GET /repos/{owner}/{repo}/releases?per_page=100`;
all three responses were shorter than a page, and all **returned** release objects
listed zero **attached GitHub Release assets** at this point in time. This does
**not** attest absence of OCI registry images, generated source archives, deleted
assets, retained workflow artifacts, logs or previous exposure. Actions counts
were read from `GET /repos/{owner}/{repo}/actions/runs?per_page=1` using only
the provider's `total_count`; no run corpus, logs or artifact contents were
enumerated or assessed. The historical 2026-11-08 values above remain intact as
an earlier dated observation; counts may change.

The current public default branches still have the **internal-use root license**
in KAORI and Docs, and **no root LICENSE** in Website. Current tracked-tree
filename inspection revealed existing third-party license/notice candidates in
the Application under `app/static/fonts/inter/` and
`app/static/vendor/`; a tracked filename does **not** prove the license covers
all derivative or redistributed code, content or fonts.

The Website tree includes three current files under `public/branding/`:
`kaori-logo.svg`, `kaori-operations-fabric.svg`, and
`kaori-connected-operations-hub.webp`. A limited public commit-path query
for `public/branding` returned eight commit records dating to 2026-10-16–18;
their use of terms such as *approved* or *original* is **not** an ownership,
trademark, provenance or redistribution-rights sign-off. This is a narrowly
scoped public-history metadata sample, **not** full history coverage.

Public repository metadata currently reports `has_discussions=true` for
KAORI and Website, and `false` for Docs. A GitHub Discussions toggle does not
establish category configuration, moderation, live triage evidence, or approval
to launch community contribution intake under #4217. Do not announce a new
public contribution policy or link to an unaccepted canonical discussion.

**All eight coverage-register rows remain NOT VERIFIED.** Next accepted evidence
must include authorized private review of all reachable Git history and
deleted-file exposure; release/OCI registry and Actions artifact/log contents;
actual historical secret scanning and incident handling; contributor ownership
and each brand/illustration trademark permission; third-party font/code/license
obligations; and a documented per-repository human GO/NO-GO. Keep any sensitive
finding outside public Issues, PRs, and source files. Until then, no LICENSE,
NOTICE, public rights grant, external contributor launch, release, tag or
deployment is authorized by this metadata readback.

## Maintainer-reported Website artwork provenance — 2026-11-09 (partial evidence; NO-GO)

Under [Website licensing #136](https://github.com/OXY7O/kaori-website/issues/136), the KAORI maintainer supplied the following creation and usage statement. This is a **first-party assertion to investigate**, not an independent chain-of-title, copyright, or legal authorization:

| Website asset | Maintainer statement / present scope | Remaining rights decision |
| --- | --- | --- |
| `public/branding/kaori-logo.svg` | Designed by the KAORI team; an actively used KAORI identity asset, also aligned with the Application's canonical logo | Retain as protected logo/trademark; identify accountable brand rights holder and approved use terms, outside any blanket Apache-2.0 source-code grant |
| `public/branding/kaori-operations-fabric.svg` | Designed by the KAORI team and originally copied from the Application; **not used by the Website anymore** | Retire only the unused Website copy under [PR #186](https://github.com/OXY7O/kaori-website/pull/186), preserving historical provenance and the independent Application source; removal is not a retroactive history purge |
| `public/branding/kaori-connected-operations-hub.webp` | KAORI-directed collaborative exploration with ChatGPT / AI-assisted image generation, approved for the Website Hero; the existing Website #41 record traces its later caption crop, resize and compression | Validate AI service terms, inputs/third-party material, output usage/redistribution and human contributions before making an exclusive-copyright or trademark grant; preserve active Website use while pending |

The maintainer agreed **in principle** with Apache-2.0 for **rights-cleared software source**, separate protection/permission for KAORI brands and illustrations, and independent license/NOTICE obligations for third-party dependencies including Inter. This is **not** final publication authorization. The non-licensed current Website posture and historical public disclosure remain unchanged; public accessibility, in-house design, or AI-assisted creation alone do not establish all exclusive ownership or redistribution rights.

**Coverage reconciliation:** all eight pre-existing register rows above remain **NOT VERIFIED**. Still required: signed/recorded ownership and contribution authority; AI-provider terms/input provenance; third-party font/content attribution; full Git history and deleted blobs; release/OCI/workflow artifacts and logs; secret scanning effectiveness and private incident disposition; independent rights review; explicit per-repository human GO/NO-GO. The only action taken by the parallel Website PR is a scoped source asset retirement / documentation update; no license, community launch, new rights, deployment or release is approved here.

## Evidence handling

Record repository, surface, bounded time window, scan/tool identity, reviewed ref or artifact identifier, reviewer, observation time, sanitized evidence ID and disposition in the approved private audit location. Public issues/PRs/Slack receive only non-sensitive coverage status and references. Do not paste credential values, private URLs, screenshots with sensitive data, or vulnerability reproduction. A confirmed active credential exposure is a private security incident requiring separately authorized rotation/revocation, not a public Issue attachment.

## Acceptance gate

A tracked-tree scan alone cannot establish history, release, artifact or rights coverage. Keep **NO-GO** until independent evidence covers all surfaces for KAORI, Website and Docs; ownership and third-party attribution decisions are explicit; active exposure has been privately handled; and the maintainer records a per-repository GO decision. Do not change `LICENSE`, `NOTICE`, SPDX identifiers, SaaS claims, public contribution settings, release authority or production infrastructure under this issue.

Related: #4211 foundation, #4213 license reconciliation, #4215 security baseline, #4214 fork-safe CI, OXY7O/kaori-website#136/#137, OXY7O/kaori-docs#74/#75.

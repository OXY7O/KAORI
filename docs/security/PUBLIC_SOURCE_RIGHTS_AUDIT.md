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

**Creator/maintainer self-attestation (2026-11-09, subsequent clarification):** The individual KAORI creator states that the KAORI concept/original idea, software code and branding were personally developed and that the creator claims ownership of those works. The KAORI logo and historical operations-fabric SVG are reported as original KAORI designs. The active Website Hero illustration was developed through the creator's own ChatGPT/AI-assisted image exploration and subsequent Website adaptation. This clarifies **who is asserting authorship/ownership**, but it is not a completed authorship census of every historical commit, an employer/contractor/contributor assignment audit, a transfer of individual rights to the `OXY7O` organization, a registered-trademark certificate, or a guarantee of exclusive copyright in generative-AI output. The applicable tool terms, inputs, third-party components, exact copyright holder, and **who has authority to grant a public source-code license** must be verified and accepted independently. The documented proposal to license rights-cleared software under Apache-2.0 and reserve brand/imagery rights is **not** itself a rights grant. Owner-provided statement and sanitized provenance record: [#4212](https://github.com/OXY7O/KAORI/issues/4212#issuecomment-6732371146), [Website #136](https://github.com/OXY7O/kaori-website/issues/136#issuecomment-6732372218).

### Proposed individual copyright and protected-brand structure — preparatory only (2026-11-09)

The creator explicitly selected **individual personal copyright ownership**, not automatic transfer of their claimed rights to the `OXY7O` GitHub organization. This is a recorded **governance/intended-licensor decision**, NOT the final per-repository licensing GO and NOT an independent legal determination for every contributed file. The creator explicitly confirms **Lethisa Putri** is their chosen **public maintainer pseudonym/alias**, as already displayed under “Owner & Contact” in the Website footer; **it is not a confirmed legal name**. Any proposed public-facing copyright attribution using this alias must be separately checked for accuracy and validity under applicable law, and the real individual claimant's right to grant a license must be confirmed through an appropriately confidential rights review if required. Do not publish or solicit private legal identity details through public source, issues or PRs, or confuse the GitHub organization with an IP assignee.

| Material / surface | Proposed person, scope and separate treatment | Preconditions to activate |
| --- | --- | --- |
| KAORI-authored software source (Website first; Application separately governed by #4213) | Individual creator as claimed author/licensor; proposed **public pseudonymous attribution** `Copyright 2026 Lethisa Putri` (not a verified legal-identity statement); target Apache-2.0 only for source code for which the grantor possesses the necessary rights | Confirm public pseudonym/copyright-notice validity under applicable law, authorization of the actual individual rightsholder through private evidence if needed, copyright years, historical authors/contributors, employment/contractor terms, third-party inclusions and independent rights GO; adopt unmodified OSI license text and accurate code/metadata scope only in a separate approved licensing PR |
| KAORI name, logo and visual brand identity | Creator-claimed personal brand/mark stewardship; protected separately, **not granted as a mark license** by hosting software in the `OXY7O` organization or by the planned source-code Apache-2.0 license | Confirm authorization, actual trademark position/registrations if any, and a clear permitted-use policy; do not claim registered-trademark status without evidence |
| Website illustrations, including `kaori-connected-operations-hub.webp` and historical fabric SVG | Creator-directed design and AI-assisted exploration; excluded from the proposed blanket source-code grant; historical artifact remains in Git history even where removed from staging | Verify AI-service terms at generation time, any third-party prompts/reference inputs, human contribution and applicable output rights before promising exclusive copyright or redistribution |
| Third-party font, code, images and bundled assets | Each applicable upstream rights holder remains authoritative; e.g. Inter/`@fontsource-variable/inter@5.3.0` under OFL-1.1, not relabeled Apache-2.0 | Verify actual distributed build/OCI artifacts, licenses, notices and other obligations; do not treat lockfile metadata as completed attribution |
| Public Docs content | Separate workstream and rights review; a potential CC BY 4.0 scope remains proposed only for individually cleared documentation content | Independent Docs audit and approval; avoid re-licensing provider screenshots, code, diagrams or other third-party material by default |
| GitHub organization `OXY7O` | Repository hosting/management and engineering governance, **not automatically the legal owner/licensor** of the creator's personal IP | If an organization is to issue the license or commercially sublicense personally held IP, verify an explicit lawful authorization/license/assignment; do not invent an assignment |

**Future Website licensing implementation plan, inactive until #4212 GO:** use issue [Website #136](https://github.com/OXY7O/kaori-website/issues/136) as authority for a dedicated issue-linked branch to introduce the unmodified approved `LICENSE` (Apache-2.0 only for rights-cleared software), any applicable `NOTICE`/third-party attributions, accurate `README.md` license/brand exclusions, and `package.json` license metadata only after matching the actual grant. Protected brand and illustration policies must be clearly separated, not silently placed under source-code license terms. Evaluate the existing release/build/footer text for consistency without changing it merely for documentation aesthetics. Then require independent approval, Developer Check, Full Admission, Website browser/staging human acceptance, and separately approved promotion. **None of those license or public-facing changes are made by this audit note.**

**Required rights/evidence sign-off record:** exact repository and SHA, the public maintainer pseudonym (clearly marked as such), confidential verification of actual individual rightsholder authority only where necessary, covered source and excluded assets, contributor/contractor/employer-origin review, third-party distributed artifact notices, AI terms/input provenance, historical public secret/artifact exposure disposition, independent reviewers and dated per-repository GO/NO-GO. Keep private rights contracts and sensitive security details outside public files. The existing eight audit surfaces remain **NOT VERIFIED** and decision **NO-GO** until the required evidence and acceptance are actually complete.

The maintainer agreed **in principle** with Apache-2.0 for **rights-cleared software source**, separate protection/permission for KAORI brands and illustrations, and independent license/NOTICE obligations for third-party dependencies including Inter. This is **not** final publication authorization. The non-licensed current Website posture and historical public disclosure remain unchanged; public accessibility, in-house design, or AI-assisted creation alone do not establish all exclusive ownership or redistribution rights.

**Coverage reconciliation:** all eight pre-existing register rows above remain **NOT VERIFIED**. Still required: signed/recorded ownership and contribution authority; AI-provider terms/input provenance; third-party font/content attribution; full Git history and deleted blobs; release/OCI/workflow artifacts and logs; secret scanning effectiveness and private incident disposition; independent rights review; explicit per-repository human GO/NO-GO. The only action taken by the parallel Website PR is a scoped source asset retirement / documentation update; no license, community launch, new rights, deployment or release is approved here.

## Website dependency-license and retained-public-surface inventory — 2026-11-09 (partial evidence; NO-GO)

This is a dated **read-only source/metadata reconciliation** under #4212 and [Website #136](https://github.com/OXY7O/kaori-website/issues/136). The lockfile was read at accepted Website `kaori/staging@2aed567d2a692ad94f6dfa5db8caac7267d96937` (blob `50de93253ec9c03cb161ce078e7b030d8ef2ae93`), **not** from `main` or installed `node_modules`. Its lockfile v3 lists **394 non-root dependency records**; **394/394 declare a license *metadata string***. The website project's root `package.json` has **no `license` field**. A package declaration is **not** the actual package notice, legal completeness, or proof that the package ships with the public static output.

| Lockfile declared license expression | Non-root package records |
| --- | ---: |
| `MIT` | 298 |
| `MPL-2.0` | 26 |
| `Apache-2.0` | 20 |
| `ISC` | 16 |
| `LGPL-3.0-or-later` | 10 |
| `BSD-2-Clause` | 8 |
| `BSD-3-Clause` | 4 |
| `Apache-2.0 AND LGPL-3.0-or-later` | 3 |
| `BlueOak-1.0.0` | 3 |
| `0BSD` | 2 |
| `CC0-1.0` | 2 |
| `OFL-1.1` | 1 |
| `Apache-2.0 AND LGPL-3.0-or-later AND MIT` | 1 |
| **Total** | **394** |

**Distribution/rights boundaries:** direct runtime dependencies include `@fontsource-variable/inter@5.3.0` (`OFL-1.1`) and `astro@7.4.0` (`MIT`); test-only direct `@axe-core/playwright@4.10.2` declares `MPL-2.0`. The transitive inventory includes platform-optional `@img/sharp-*` and `@img/sharp-libvips-*` records with combined `Apache-2.0 AND LGPL-3.0-or-later` or `LGPL-3.0-or-later` expressions, plus `lightningcss` records with `MPL-2.0`. **Do not assume** all optional platform binaries or development/test packages are redistributed in the production static site or OCI image. Verify the actual **published image layers, generated static output, included license/notice texts and font files** before assigning redistribution and attribution obligations. Keep third-party font/artwork outside a blanket future Website Apache-2.0 grant.

**Brand current-vs-historical state:** source at official Website `kaori/staging@2aed567d2a692ad94f6dfa5db8caac7267d96937` has exactly **two current tracked files** under `public/branding/`: `kaori-logo.svg` (maintainer-reported KAORI design) and `kaori-connected-operations-hub.webp` (KAORI-directed ChatGPT/AI-assisted exploration). The old `kaori-operations-fabric.svg` is absent from staging after independently reviewed and admitted [Website PR #186](https://github.com/OXY7O/kaori-website/pull/186). The historical public `main` snapshot in the preceding section correctly showed three files **at its different SHA and date**. Deletion in staging **does not remove historical objects or deployed older copies**, nor confer exclusive copyright or trademark rights.

**Git/release metadata scope:** the Website default-`main` paginated commit endpoint returned **406 commit records** (`per_page=100`, pages 1–6 yielding 100/100/100/100/6/0) back to the first available record on 2026-10-16, while the single-page branch-list read returned **38 visible branch refs** at that observation. These are provider API **metadata inventories only**: there is no review of commit contents, deleted/unreachable objects, branch-exclusive histories or prior fork payloads. The Website release endpoint returned **9 visible Release records with 0 attached GitHub Release assets** in returned records, again not covering OCI images, retained Actions artifacts/logs or past deleted releases. Do not claim history or publication clearance.

**What remains to establish an actual Website rights GO:** owner/contributor chain-of-title and rights to license software; approval of trademark/logo and AI-service terms, inputs and any third-party-derived image material; exact third-party attribution and shipped-artifact license contents; credential/secret historical and currently active exposure assessment across three repos; Git refs/tags/release/OCI/Actions-log and generated-site contents; independent security and rights acceptance, with any confidential finding handled through approved private channels. All eight original coverage-register rows remain **NOT VERIFIED**; the overall decision remains **NO-GO** for `LICENSE`, `NOTICE`, SPDX license metadata, external contribution launch, production release or deployment. No actual license grant or security configuration mutation is performed in this evidence entry.

## Bounded default-branch tree and ref metadata — 2026-11-11 (NO-GO unchanged)

This is a **new read-only provider metadata checkpoint** under #4212, not a Git history, published artifact, vulnerability or legal rights clearance. The actual GitHub `GET /repos/{repo}/git/trees/main?recursive=1` response returned `truncated=false` for all three public repositories. Counts reflect **tracked blob names and sizes at the exact default-main commit**; they do not inspect blob contents, unreachable history, alternate branches, archives, generated sites, workflow output or private registries.

| Repository | Inspected default-main SHA | Tracked blobs | Markdown/MDX/RST | Image-like tracked blobs | Visible branch refs |
| --- | --- | ---: | ---: | ---: | ---: |
| `OXY7O/KAORI` | `12ea7c0e487569f3187a139a935e89c07ab46744` | 4,816 | 652 | 6 | 772 |
| `OXY7O/kaori-website` | `41091df060e406e2ade7ae63fc67bc65c4454559` | 66 | 14 | 3 | 38 |
| `OXY7O/kaori-docs` | `6915fb97c5f53d8e5043876d51401d08bd683879` | 46 | 9 | 1 | 58 |

File classes above use **extension-only filters**: documentation `.md/.mdx/.rst`; image-like `.svg/.png/.jpg/.jpeg/.webp/.gif/.ico`. The eight full GitHub branch-list pages for KAORI returned `100+100+100+100+100+100+100+72` records; Website and Docs returned 38 and 58 in their first page. The provider marked **two current branches protected** per repository in this snapshot. This branch inventory is a **scope and cleanup risk indicator**, not proof that all branch tips, tag refs, historical blobs or deleted references have been scanned. In particular, retained unmerged/test branches must not be deleted merely to make an audit look complete; audit first, then apply the existing governed Branch Hygiene and evidence-retention policy. The prior deliberately invalid test branch under #4278 remained visible among KAORI refs at this checkpoint.

A parallel read of public `GET /repos/{repo}/releases?per_page=100` and `GET /repos/{repo}/actions/runs?per_page=1` returned these **bounded current metadata results**:

| Repository | Visible Releases | Prerelease / non-prerelease | Attached GitHub Release assets in returned objects | Provider-reported total Actions workflow runs |
| --- | ---: | ---: | ---: | ---: |
| `OXY7O/KAORI` | 2 | 2 / 0 | 0 | 3,911 |
| `OXY7O/kaori-website` | 9 | 7 / 2 | 0 | 409 |
| `OXY7O/kaori-docs` | 9 | 9 / 0 | 0 | 264 |

These provider-reported counters change over time. The returned `assets=[]` on current Release objects **does not** rule out existing/deleted OCI images, workflow artifacts, Action logs, independent Pages/static site assets, deleted releases or historic exposures. A separate Git tags listing endpoint was unsupported through the connected fetch tool; tag-ref coverage remains **NOT VERIFIED**. The `total_count` workflow value is **not** a paginated run-content review. Current tree filename keywords can identify examples/tests and potential review candidates, but were **not** treated as proof of secrets or of their absence; no sensitive path list or credential value is published.

**Next safe evidence collection:** inspect/triage the bounded tracked-tree classes, all **reachable branch and tag tips plus earlier Git history**, public/retained GitHub Actions artifacts and logs using the **existing repository-approved inventories**, release/registry outputs and currently deployed Website/Docs, then privately reconcile credential alerts and source/content rights with independent owner sign-off. Maintain the original eight audit register rows at **NOT VERIFIED**, the licensing/public-contribution decision at **NO-GO**, and existing separate source-license/brand/AI attribution boundaries. No active secret, ownership transfer or rights-clearance conclusion is asserted by this metadata snapshot.

## Website recurring public RC publication boundary — 2026-11-17 (#4939)

The maintainer confirmed GitHub `staging`/`production` Environment setup
and authorized progressing the Website staging and production approval
implementation and this rights assessment. That conversation is an
**authorization to continue engineering and assess release rights**, not
independent evidence of third-party redistribution rights, a blanket
source-license grant or standing permission for every future public RC.

**Current evidence, scoped to Website only:**

- [Website PR #205](https://github.com/OXY7O/kaori-website/pull/205)
  received independent `donibawono` approval and an exact-head Developer
  Check PASS. The protected integration is
  `kaori/staging@06f5142d7a6578485516c4a1812bc950f1835b4e`.
  [Full Admission #44006999386](https://github.com/OXY7O/kaori-website/actions/runs/44006999386)
  completed with all four mandatory jobs SUCCESS: Promotion Policy, Full
  Admission, Container Admission and Browser Quality Evidence.
  Both admitted signed-RC publication and deployment jobs were **SKIPPED**;
  this is not a new public candidate or an accepted public rollout.
- The recursive Website tracked tree at that exact staging SHA returned
  **92 entries and `truncated=false`**, including active
  `public/branding/kaori-logo.svg`,
  `public/branding/kaori-connected-operations-hub.webp`,
  `public/licenses/inter/OFL-1.1.txt` (Git blob
  `40589daa9de8bc96606292ea0be712ff0f0626eb`) and
  `public/licenses/lucide/LICENSE.txt` (Git blob
  `718bb3f0e44153809972abed31839375804bf652`).
  These are **source notice files**, not independent proof of their
  exact bytes in a currently served image or HTTPS response. There is no
  root Website `LICENSE` at this tracked staging snapshot.
- Existing [Website #198](https://github.com/OXY7O/kaori-website/issues/198)
  documents signed RC.9 deployed on the single public Website slot and
  **Human UAT PASS** for exact prior staging
  `5c14567f3c374a5f63d874edd5f624492685e8aa`.
  This is a bounded historical public-UAT exception, not acceptance of
  new `06f5142` or recurring releases. A direct external verification
  of live notice URLs and current signed host/rollback receipt is still
  required; no current serving claim is made from source alone.
- [Website Draft PR #206](https://github.com/OXY7O/kaori-website/pull/206)
  integrates the official staging merge on production work-branch
  `a93716b5894ebd73c6eacb8265d4d8f4a87d9529` and passed
  [exact-head Developer Check #44007179607](https://github.com/OXY7O/kaori-website/actions/runs/44007179607).
  It is **not** a merged main release, accepted production Environment
  reviewer run, or stable same-digest publication. The production activation
  variable is not independently read or set by this audit.

**Cross-repository security-gate triage, bounded (2026-11-17):**
[Ready audit PR #4940 Full Admission #44007786726](https://github.com/OXY7O/KAORI/actions/runs/44007786726)
stopped at historical Gitleaks (`18,458` commits scanned;
`2` `generic-api-key` matches) before downstream Security and Ready
Admission could succeed. Read-only review of the retained diagnostic
artifact `14295157267` and original integration contract test contexts
confirmed both exact historical matches are literal `REDACTED` placeholders
used for rendering identity metadata, **not provider authentication keys**.
This is **not** proof that every repo's Git history, releases, registry
artifacts or active credentials have been cleared. Existing narrowly scoped
fingerprint-disposition precedent [#4171](https://github.com/OXY7O/KAORI/issues/4171)
is being reused in [#4941](https://github.com/OXY7O/KAORI/issues/4941)
and [PR #4942](https://github.com/OXY7O/KAORI/pull/4942) for exactly two
specific fixture fingerprints, retaining the complete scanner policy.
A new `Ready` security run, independent review and protected staging
admission must actually pass before audit PR #4940 can resume.
No scan-bypass or global security GO is inferred.

**Security-gate resolution and audit-branch integration (2026-11-17):**
The narrow two-fingerprint test-fixture disposition [#4941](https://github.com/OXY7O/KAORI/issues/4941)
and real `dnspython==2.9.2` advisory remediation
[#4945](https://github.com/OXY7O/KAORI/issues/4945) are **CLOSED/COMPLETED**.
Independent review of [PR #4942](https://github.com/OXY7O/KAORI/pull/4942)
and [Ready Full Admission #44036440202](https://github.com/OXY7O/KAORI/actions/runs/44036440202)
passed all five selected lanes (Frontend, Runtime & DAST, Functional,
Static & Governance, Security), CI Admission and Ready Admission Guard.
Actual Security included Gitleaks historical scan PASS, Bandit PASS,
Semgrep zero findings, both base and dev `pip-audit` no known vulnerabilities,
and npm audit PASS. Protected staging merge
`51d75e084275fec7e8530f0d96c5236874428780` passed
[post-merge Fast Smoke and CI Admission #44039924776](https://github.com/OXY7O/KAORI/actions/runs/44039924776).
This confirms the **KAORI staging repository's** scoped security correction,
not global source/registry/credential exposure clearance across all repositories.

The earlier [audit Ready run #44040153766](https://github.com/OXY7O/KAORI/actions/runs/44040153766)
still failed the original two synthetic Gitleaks matches because the
**audit branch was behind the already-fixed staging branch**; do not
misclassify its cancelled subsequent lanes as PASS. The existing rights-audit
work branch was therefore synchronized by a two-parent merge commit
`f393d7dc13acf8f77d0fa24ef80d5657c3541d3f` joining the prior
audit head and the admitted security staging head, while preserving the
prior approved rights-audit document. Only this document differs from staging.
A **fresh exact-head Ready Security / Full Admission** is still required
before merging audit PR #4940, and no recurring Website publication GO
is granted by these security outcomes.

**Maintainer-operated public runtime readback (2026-11-17):**
The authorized Website host operator supplied the read-only result for the
current public `kaori-website` Compose service, not an assistant-initiated
deployment. The current `release.env` and previous `previous-release.env`
both exist and are readable. `docker inspect` returned active signed
RC.9 image `docker.io/lethisaputri/kaori-website@sha256:f34414c1308c91515feb30f1bc5aee41dd117c74bcd93dcf3979be0ac4233c19`,
health `healthy`. HTTPS checks returned `healthy` for
`https://kaori.cloud/healthz` and
`https://docs.kaori.cloud/healthz`; Application
`https://app.kaori.cloud/health/ready` returned ready with database and
Redis both `ok`. Exact captured operator evidence was linked to
[Website #198](https://github.com/OXY7O/kaori-website/issues/198#issuecomment-6937662655).

**Remaining runtime qualifications:** presence of `previous-release.env`
does not verify its signed image/source/version identity or a completed
rollback exercise. Actual bytes of publicly served Inter OFL and
Lucide/Feather notice files have **not** yet been compared to the exact
signed RC.9 source or OCI image; do not misreport source notice paths as
served-asset verification. The maintainer additionally reported both
repository release activation variables enabled; that is operator
attestation only, with no independent GitHub Settings API readback.
These facts improve the old RC.9 operational evidence but are **not a
standing future public publication rights GO**.

**Decision: HOLD / NO-GO for standing automatic public RC publication.**
The specific additional work and approval authority is
[KAORI #4939](https://github.com/OXY7O/KAORI/issues/4939).
Before enabling the repository `KAORI_WEBSITE_AUTO_STAGING_ENABLED` switch,
record a reviewed and expressly accepted recurring-publication scope:
permitted Website source/third-party/brand boundaries, evidence of actual
static asset notices in a signed OCI and HTTPS serving, previous signed
rollback and recovery proof, safe source/history/artifact exposure
disposition, and an authorized maintainer GO with clear revocation conditions.
A one-time manually approved RC is not a perpetual publication exception.
The maintainer's GitHub Environment verification is classified as
**operator-attested**, not independent repository-Settings/API readback,
and a live approval gate must still be observed for production.

**Separate broader decision remains unchanged:** the cross-repository
eight-surface rights assessment in this register is still not completed.
Website [#136](https://github.com/OXY7O/kaori-website/issues/136)
source licensing, KAORI/Docs licensing, contributor launch, trademark rights
and any Apache-2.0/CC-BY grant remain **NO-GO** absent their own independent
acceptance. Neither this audit increment nor #4939 releases an image, changes
license metadata, edits credentials, triggers a deployment or grants public
source reuse rights.

### Website signed RC.10: bounded third-party-license evidence and Human Acceptance (2026-11-17)

**Scope:** This is a narrowly bounded evidence review of the already-public,
maintainer-accepted KAORI Website RC, **not** approval for OSI relicensing,
brand sublicensing, a new public deployment, or indefinite recurring RCs.
The Website package sets `private: true`, while the public repository has no
root `LICENSE`. Public visibility is not evidence of an OSI license grant.

| Surface | Authoritative evidence | Decision / limitation |
| --- | --- | --- |
| Signed immutable RC.10 | [Release `v0.1.2-rc.10`](https://github.com/OXY7O/kaori-website/releases/tag/v0.1.2-rc.10), admitted source `c492b64ae2b171b80ac54a18c38cd504f6b21019`, OCI digest `sha256:d4a985e44a938911c073be2164388bb4c7c8be2a2e7a742266d6ca783c6528a7`, SPDX SBOM SHA256 `59f2bf1890beb429a16f98d375fb91556bfa850eb32d280651dd8903f74d747d`; [publisher and deploy run #44018249727](https://github.com/OXY7O/kaori-website/actions/runs/44018249727) | **PASS for published identity and technical deployment**: 4/4 Full Admission, signed provenance, zero HIGH/CRITICAL Trivy findings reported, single public-slot deployment, healthy non-root image, matching public build footer, App/Docs ready. This is not legal or license verification. |
| Human UAT | Maintainer explicitly stated **`RC.10 APPROVED`**; [exact-source / tag / digest Human Acceptance comment](https://github.com/OXY7O/kaori-website/issues/202#issuecomment-6939870730) | **ACCEPTED for this specific RC**. Do not request repeated Human Acceptance for the same immutable identity; this is neither a blanket license grant nor authorization for later RCs. |
| Inter fonts | Upstream `@fontsource-variable/inter@5.3.0`, OFL-1.1; official terms: https://openfontlicense.org/open-font-license-official-text/ ; RC.10 source `public/licenses/inter/OFL-1.1.txt`, Git blob `40589daa9de8bc96606292ea0be712ff0f0626eb`, 4,477 bytes | **PASS for upstream notice and static build**. Existing Full Admission verifies the produced `dist/licenses/inter/OFL-1.1.txt` with `cmp` against installed upstream package `LICENSE`. OFL permits webfont distribution with copyright + full-license notice. **Operator readback PASS on live RC.10**: `curl -fsS https://kaori.cloud/licenses/inter/OFL-1.1.txt | git hash-object --stdin` matched the exact source blob `40589daa9de8bc96606292ea0be712ff0f0626eb`; [Website #190 accepted and CLOSED](https://github.com/OXY7O/kaori-website/issues/190#issuecomment-6940472458). |
| Lucide/Feather icons | Official https://lucide.dev/license and https://github.com/lucide-icons/lucide/blob/main/LICENSE; official file and exact RC.10 `public/licenses/lucide/LICENSE.txt` both Git blob `718bb3f0e44153809972abed31839375804bf652` (3,208 bytes) | **PASS for source notice and build presence**. License retains Lucide ISC copyright/permission and the Feather-derived icon list + MIT terms. Existing Full Admission asserts the output notice and key provisions. Inline SVG geometry alone is not ownership of the upstream icons. **Operator readback PASS on live RC.10**: `curl -fsS https://kaori.cloud/licenses/lucide/LICENSE.txt | git hash-object --stdin` matched exact official/source blob `718bb3f0e44153809972abed31839375804bf652`; [Website #192 accepted and CLOSED](https://github.com/OXY7O/kaori-website/issues/192#issuecomment-6940473336). |
| Static artifact assembly | RC.10 `Dockerfile` copies `/build/dist/` to `/usr/share/nginx/html/` in a digest-pinned unprivileged NGINX image; NGINX `location /` uses `try_files $uri $uri/ =404`, with no license-file exclusion; Full Admission asserts both `dist/licenses/...` files | **PASS for deterministic source-to-build-to-container-copy path**, not an independently extracted/hashed deployed OCI layer or remotely fetched static notice response. |
| KAORI brand and AI-assisted Hero | RC.10 `public/branding/kaori-logo.svg` Git blob `d463e5e8f2f2d97718b6fb6c1d6bb0f8503bf07f` and `kaori-connected-operations-hub.webp` blob `217f093c6c04c2201a4f01a26e8e6bb7edce68a8`; README/HOMEPAGE_REVIEW origin description | **Protected assets, no new license**. Maintainer-designed logo / AI-assisted illustration provenance is recorded, but exact commercial sublicensing/exclusive copyright and external rights cannot be inferred. No Apache-2.0, CC BY, trademark or model-provider rights grant. |
| OCI base and transitive components | Pinned `ghcr.io/nginx/nginx-unprivileged:1.30.6-alpine3.24-slim` base, published signed SPDX SBOM and Trivy scan | **Security and inventory evidence, not an all-components notice compliance opinion**. Need inspect what license notices actually ship in the published OCI; distinguish build/dev-only npm packages from runtime layers. |
| Public-served notice and rollback readback | Authorized operator `root@kaori` executed exact digest-qualified live Compose image comparison plus full-HTTPS-response Git-blob checks for Inter and Lucide at the public `kaori.cloud` URLs; prior RC.9 evidence confirmed `release.env` and `previous-release.env` exist | **PASS operator-attested for active RC.10 digest and both public license notices**. The terminal yielded `PASS: RC.10 image`, `PASS: Inter license`, and `PASS: Lucide/Feather license`. These are direct live checks supplied by the operator, not assistant-originated independent host access. **RC.10 prior signed rollback-image identity and actual recovery remain NOT VERIFIED**; the previous receipt's presence alone is not a rollback proof. |

**Read-only completion check (authorized Website host/operator; COMPLETED for RC.10):** The exact
published RC.10 source files have Git blob IDs above. The following host-side
HTTPS readback can be performed without deployment, file edits, signing,
secret access, restart or any release mutation. Record only PASS/FAIL and
Git blob IDs in public evidence; do not expose host credentials.

```bash
set -Eeuo pipefail
actual_inter="$(curl -fsS --connect-timeout 5 --max-time 15 https://kaori.cloud/licenses/inter/OFL-1.1.txt | git hash-object --stdin)"
actual_lucide="$(curl -fsS --connect-timeout 5 --max-time 15 https://kaori.cloud/licenses/lucide/LICENSE.txt | git hash-object --stdin)"
test "$actual_inter" = 40589daa9de8bc96606292ea0be712ff0f0626eb
test "$actual_lucide" = 718bb3f0e44153809972abed31839375804bf652
printf 'PASS: RC.10 public Inter/Lucide notice Git blobs match signed source\n'
```

**Completed license readback evidence, 2026-11-17:** The maintainer supplied the exact `root@kaori` shell output after running the accepted read-only checks. `docker ps --filter label=com.docker.compose.project=kaori-website --filter label=com.docker.compose.service=web` selected the public Compose web container, and `docker inspect --format '{{.Config.Image}}'` matched the exact signed RC.10 OCI digest `sha256:d4a985e44a938911c073be2164388bb4c7c8be2a2e7a742266d6ca783c6528a7`. Both complete `curl -fsS` HTTPS responses were hashed with `git hash-object --stdin` and checked against the pinned source Git blobs; all three checks returned `PASS`. This is **strong operator-supplied end-to-end served-file evidence**, not an independent auditor session. No deploy, rollback, credential read or server mutation was performed to establish it. The narrow [Inter issue #190](https://github.com/OXY7O/kaori-website/issues/190) and [Lucide/Feather issue #192](https://github.com/OXY7O/kaori-website/issues/192) have been **CLOSED/COMPLETED** on this evidence. The broader publication and own-code/brand rights gates remain distinct.

**Governance interpretation:** Standard OFL/ISC/MIT permission and the
verified source/CI notice artifacts remove the *known source-attribution gap*
for Inter and Lucide. They do **not** prove every OCI runtime layer, prior
Git history, third-party image or KAORI-owned asset is cleared. The approved
RC.10 release remains accepted and immutable. Keep one independent
[KAORI #4939](https://github.com/OXY7O/KAORI/issues/4939) scoped
publication-rights decision for subsequent public activation, separate from
the cross-repository open-source/relicense [#4212](https://github.com/OXY7O/KAORI/issues/4212).
Do not introduce repetitive human UAT or separate legal approval for every
unmodified open-license notice; only a source/content change outside the
approved scope warrants renewed rights review. The currently merged Website
#208 gate uses an exact-source approval marker per staging commit: this is
**overly strict for recurring authorization** and must be reconciled with
the approved scope in a reviewed follow-up rather than disabled or silently
bypassed. `KAORI_WEBSITE_AUTO_STAGING_ENABLED=false` stays operator-attested
and release mutation is disabled until that integration is accepted.

## Website signed RC.11 and stable v0.1.2 public release metadata — 2026-11-21 (NO-GO unchanged)

**Dated, bounded provider evidence; not a complete rights or exposure clearance.** This incremental observation supersedes the *current-release identity* in older Website RC.10 checkpoints, **not** those historically accurate license/notice readbacks, and does not change any of the eight original `NOT VERIFIED` coverage categories. The cross-repository license/contributor decision under [#4212](https://github.com/OXY7O/KAORI/issues/4212) remains **NO-GO**.

| Public evidence | Read-only observation and source |
| --- | --- |
| Official stable Release | [Website `v0.1.2`](https://github.com/OXY7O/kaori-website/releases/tag/v0.1.2) is published (`prerelease=false`, `draft=false`, 2026-11-21T01:31:20Z); its Git tag commit and `target_commitish` both point to protected `main@6b12d441a85b7e55b132dddd04b11034ace98509` |
| Signed Human Accepted RC | [`v0.1.2-rc.11`](https://github.com/OXY7O/kaori-website/releases/tag/v0.1.2-rc.11) is a separate prerelease, source `e289b8e2ddf322f2cd395a59312b0ef006312701`, deployed to the existing public Website by [#44845009154](https://github.com/OXY7O/kaori-website/actions/runs/44845009154) SUCCESS, and explicitly owner Human Accepted in [Website #202](https://github.com/OXY7O/kaori-website/issues/202#issuecomment-7054463015) |
| Artifact equivalence | Stable and accepted RC.11 GitHub release metadata identify **the same** immutable image `docker.io/lethisaputri/kaori-website@sha256:e7cb2b32ec8f9262fde51eb0021c8138212c8e5c383121cd9e5999d17c388a24`, no rebuild or tag mutation during stable publication; RC metadata identify SPDX SBOM SHA256 `6745dfa99a02745b01e543073b9e5dbc92c5d4d1c3571d82c859fea5a7a17c98` |
| Code, checks and GitHub approvals | Independent code review and protected [promotion PR #219](https://github.com/OXY7O/kaori-website/pull/219); [main admission and stable publisher #44849431955](https://github.com/OXY7O/kaori-website/actions/runs/44849431955) SUCCESS (four mandated admission jobs and protected stable job), GitHub Environment `production` reviewer `donibawono` actually **approved** |
| Runtime / signature verification | Stable publisher log records matching public Website immutable digest and release receipt, healthy non-root HTTP and shared edge, Cosign image signature and signed SPDX/SLSA attestations, and Website/Application/Docs HTTPS readiness, without replacing the deployed RC.11 container |
| Rollback boundary | Release preflight required a prior immutable rollback receipt/digest and verified the live current receipt; a **live rollback drill was not performed**, and cross-history availability and disaster-recovery guarantees are not inferred |
| Own-source license boundary | A read-only GitHub default-`main` `contents/LICENSE` lookup for `OXY7O/kaori-website` returned **404 (root LICENSE absent)** on 2026-11-21. First-party Website operation and image-release rights were explicitly authorized under completed [#4939](https://github.com/OXY7O/KAORI/issues/4939); this is **not** an Apache-2.0, broad trademark, illustration, third-party attribution, or external-contributor license grant |

**Unresolved cross-repo exposure/rights scope:** No full Git history, retained Actions artifact/log content, all historic OCI layers, independently verified third-party asset provenance, comprehensive active-secret coverage or legal chain-of-title clearance was completed by the stable publication. Do not infer that an accepted operational release grants unrestricted reuse of the source or protected brand assets. [Website license #136](https://github.com/OXY7O/kaori-website/issues/136) and [Website community #137](https://github.com/OXY7O/kaori-website/issues/137) remain **OPEN**, with central rights #4212 and community #4217 independently governed. Website delivery [#201](https://github.com/OXY7O/kaori-website/issues/201) and scoped release children #202/#203/#204 are **CLOSED/COMPLETED**; unrelated KAORI Application and Docs licenses/releases are not authorized by this record.

## Evidence handling

Record repository, surface, bounded time window, scan/tool identity, reviewed ref or artifact identifier, reviewer, observation time, sanitized evidence ID and disposition in the approved private audit location. Public issues/PRs/Slack receive only non-sensitive coverage status and references. Do not paste credential values, private URLs, screenshots with sensitive data, or vulnerability reproduction. A confirmed active credential exposure is a private security incident requiring separately authorized rotation/revocation, not a public Issue attachment.

## Acceptance gate

A tracked-tree scan alone cannot establish history, release, artifact or rights coverage. Keep **NO-GO** until independent evidence covers all surfaces for KAORI, Website and Docs; ownership and third-party attribution decisions are explicit; active exposure has been privately handled; and the maintainer records a per-repository GO decision. Do not change `LICENSE`, `NOTICE`, SPDX identifiers, SaaS claims, public contribution settings, release authority or production infrastructure under this issue.

Related: #4211 foundation, #4213 license reconciliation, #4215 security baseline, #4214 fork-safe CI, OXY7O/kaori-website#136/#137, OXY7O/kaori-docs#74/#75.

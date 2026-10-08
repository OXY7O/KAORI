# Source Control — GitHub App Multi-Organization Foundation

**Status:** Architecture discussion addendum agreed for the next Source Control phase; pending normal documentation review/admission. Not an implemented capability.
**Foundation authority:** [#559](https://github.com/OXY7O/KAORI/issues/559) and its accepted architecture-decision comments.
**Documentation work item:** [#958](https://github.com/OXY7O/KAORI/issues/958).
**Relevant authorities:** #561 (roadmap); #711/#723 (Service and Team ownership); #712 (Asset identity); #624 (Integrations navigation); #888/#891 (browser authentication); #440/#529 (delivery evidence); #724 (resource-scoped authorization); #638/#641 (security).

This addendum records the **GitHub App onboarding, multi-organization, and host-compatibility decisions** made after #559. It does **not** replace #559's accepted contracts for revisions, pull requests, reviews, checks, Actions, governance, contributions, deployments, audit, or lineage. Those accepted decision records remain authoritative. The current `kaori/staging` implementation and `app/definitions/catalogs/integrations/taxonomy.yaml` do **not yet** register Source Control as a deployed capability.

## Decision summary

| Concern | Decision |
| --- | --- |
| Product capability | **Source Control** is provider-neutral; **GitHub** is the first provider. |
| Initial target | **GitHub.com Cloud** only for the first implementable MVP. |
| Future host | GitHub Enterprise Server (GHES) is a host-qualified future extension; no GHES adapter or compatibility guarantee is claimed for this MVP. |
| Provider authentication | Prefer a least-privilege **GitHub App** and installation-scoped access; broad, long-lived PATs are not the default. |
| Organization topology | Design for **multiple organizations/accounts and multiple installations from the first schema/adapter contract**. |
| First onboarding | `OXY7O` is the initial reference organization; a second real test organization/installation is required to prove isolation before multi-org acceptance. |
| Repository grant | Support GitHub-authoritative **All Repositories** and **Selected Repositories** installation modes. Recommend **Selected Repositories** for initial onboarding, not as a mandatory KAORI-imposed restriction. |
| UI and evidence | Integration pages manage connection/readiness; Source Control pages read normalized committed KAORI evidence. |
| Execution authority | GitHub owns repository/PR/review/Actions/release/deployment controls. KAORI normalizes, correlates, governs, and audits; it does not clone GitHub or independently approve/execute provider operations. |
| Delivery | Discuss/approve architecture first; implement only through bounded child issues of #559 and normal KAORI admission/UAT. |

These are product and architecture decisions, **not claims that multi-org connectivity, GitHub App authentication, or Source Control persistence are already implemented**.

## Ownership and information architecture

Keep configuration separate from operational evidence:

~~~text
Integrations
└── Source Control
    └── GitHub
        ├── GitHub App / host configuration
        ├── Installation: OXY7O
        │   ├── Granted repository: KAORI
        │   └── Granted repository: ops-runbook
        └── Installation: Future Organization B
            └── Granted repositories...

Source Control
├── Overview
├── Repositories
├── Pull Requests
├── CI/CD
├── Releases / Deployments
├── Governance
└── Audit / flow evidence
~~~

The exact Source Control navigation composition remains governed by #559 and the approved KAORI sidebar/workspace standard; the diagram illustrates identities, **not** a new sidebar/tab hierarchy. In the integration registry, use the existing `IntegrationModule`, `IntegrationImplementation`, `IntegrationInstance`, adapter/definition, readiness, lifecycle, and shared-workspace contracts. A new `source_control` domain/capability must be introduced through the canonical taxonomy, not a GitHub-specific global navigation branch.

The `IntegrationInstance` remains the canonical *provider connection* identity; it must not be confused with the GitHub *account* owning repositories or with a GitHub *App installation* authorization grant. Resolve exact cardinality and persistence using the existing integration kernel in SC-01; do not introduce a second global integration registry or duplicate App private keys per repository/installation.

## Stable identities and scope

| Logical identity | Planned key and boundary |
| --- | --- |
| Provider host | Canonical trusted API/web origin, with an explicit host type (`github.com` first; GHES later). Host qualifies provider-native IDs. |
| App configuration | Host-qualified GitHub App ID and a protected private-key/webhook-secret reference. A single App configuration may authorize multiple installations on its host. |
| Integration instance | KAORI canonical connection/lifecycle ID, linked explicitly to its GitHub installation authorization context. |
| Source account | Host-qualified immutable GitHub account ID and account type (organization versus user), separate from an installation ID and mutable login/name. |
| Installation | Host-qualified immutable GitHub installation ID, explicit App/account association and authorization/lifecycle state. An uninstall/reinstall must not silently reuse the former grant identity. |
| Source repository | Host-qualified GitHub native repository ID. Owner, name, path, and URL are mutable descriptions/history; repository-to-installation access is separately evidenced. |
| Source revision | Canonical Repository + exact commit SHA, not a SHA globally shared among unrelated repositories. |
| References and activity | Branch/tag targets, PR revisions, Actions runs/attempts, releases and deployments follow the distinct, accepted identities documented in #559. |

The accepted #559 persistence direction is `IntegrationInstance -> SourceAccount -> SourceRepository`, with GitHub App installation/connection modeled as a **distinct authority**. Keep a host-qualified installation-to-account/repository grant relationship without inferring authorization from names. Account transfer/rename and repository transfer/rename must preserve native identity only when deterministic provider evidence proves continuity.

One repository may support multiple Services, and one Service may use multiple repositories (#711). GitHub team, CODEOWNERS, repository topic, and GitHub login are not automatically KAORI Team/Service ownership (#723). Relationships preserve authoritative/declared/inferred provenance.

## Installation repository grants and visibility

1. GitHub is authoritative for current installation permissions, account ownership, and **All** versus **Selected** repository grants.
2. Selected-repository access is a valid *partial coverage scope*. A newly connected organization does not imply visibility over all repositories in that organization.
3. Onboarding may recommend Selected Repositories for least privilege, but KAORI does not silently override an explicit GitHub All Repositories grant.
4. Reconcile the exact set of repositories accessible *through each installation*. Do not infer unavailable repositories, inaccessible governance features, or organizational totals outside proven scope.
5. Model provider **presence**, KAORI **access**, and **archived state** independently. Deselection, removed permissions, revoked installation, or rate limiting must not be recorded as repository deletion.
6. A stable native repository ID may continue across proven rename/transfer; its access/installation mapping and ownership history change independently.
7. Installation-scoped data access must enforce server-side authorization for list, counts, filters, detail, search, analytics, exports, reports, and async collection (#724); organization selection in the UI is not an authorization boundary.
8. Provider capabilities and freshness are per installation/evidence family. A missing permission for Governance does not block valid Repository Inventory or PR evidence; absence of evidence is `Unknown`/unavailable, not `PASS` or zero.
9. Do not introduce a globally unique `owner/repo` or mutable account-login database key. Names may collide across organizations or hosts.

## GitHub App versus GitHub browser SSO

GitHub browser login remains owned by **Access -> Authentication -> Identity Providers**, following #888/#891. It uses the existing OAuth authorization-code and user-identity projection contracts. It must not provide Source Control repository permissions merely because a person can log into KAORI.

GitHub App installation authorization belongs to **Integrations -> Source Control -> GitHub**. The first MVP follows GitHub.com's GitHub App installation-token model, with App credentials and per-installation permissions kept apart from user SSO tokens. Design requirements:

- Persist only the approved App private-key and webhook-secret **references**, not their plaintext in normalized operational records, event payloads, task arguments, evidence, UI, logs, or reports.
- Mint installation access tokens only through a bounded server/worker credential boundary; treat them as short-lived and do not persist them as Source Control inventory.
- Installations are independently revocable/suspendable. Validate the requested installation, host, account, and repository grant before using a token.
- Use least-privilege, capability-specific GitHub App permissions. The precise permission matrix belongs in SC-02 and must be verified against actual GitHub APIs before onboarding.
- Authenticate webhook ingress using the raw request body's GitHub HMAC signature, verify the expected App/installation context, bound payload size, deduplicate delivery IDs, and reject malformed/unauthorized/replayed deliveries without mutating domain state.
- Persist safe status/error/provenance evidence without secrets, raw full payloads, or provider personal data beyond the approved minimization boundary.
- Apply approved secret and App-key rotation/revocation procedures without expanding the user-login authentication model.

## Sync, failure and recovery

The existing integration lifecycle standard governs registration, configuration, validation, capability discovery, diagnostics, consumer availability, and history. Do not build a parallel GitHub lifecycle framework.

~~~text
GitHub App host/profile
  -> Installation grant / validation
  -> Account and granted-repository discovery
  -> paginated, generation-safe committed inventory
  -> provider-normalized repository / revision / PR / CI evidence
  -> Source Control / governance / correlation (committed reads)

Verified GitHub webhook -> idempotent targeted refresh (fast path)
Scheduled reconciliation -> exhaustive granted-scope correction (correctness path)
~~~

- Keep connection readiness, installation grant, repository discovery, webhook transport, and evidence-family freshness separate. `Connected` is not `Inventory Collected`.
- Background collection reuses the existing Celery/Job Execution topology, bounded pagination, rate-limit handling, safe retries, and generation/cutoff publication; no live GitHub API fan-out on normal page requests.
- Webhook arrival order is not authoritative provider state order. Older events or incomplete inventory generations must not overwrite newer committed evidence.
- Only a successful **exhaustive reconciliation within a proven authorized scope** can establish absence inside that scope. An incomplete page/rate-limited scan cannot declare deleted records.
- Distinguish GitHub App unconfigured, installation missing/revoked/suspended, repository removed from selected grants, insufficient permission, rate limited, API unavailable, webhook impaired, and stale/partial committed evidence.
- Preserve prior committed evidence and auditable access transitions according to retention/privacy policy; do not imply that disconnected access is healthy or live.
- A transfer, rename, uninstall, reinstall, or repository grant change must not silently merge unrelated organization identities or permit cross-organization leakage.

## GitHub.com MVP and future GHES boundary

**Implement GitHub.com Cloud first.** It is the only host that must be qualified in the initial integration/UAT. Treat GHES as a **future explicit compatibility profile**, with separately qualified host/API URL, App registration/credential, installation IDs, supported API/permission/version behavior, TLS/trust configuration, webhook delivery routing, and lifecycle.

Stable domain identity must include provider/host qualification and never assume GitHub.com IDs or web URLs are globally unique across a future GHES fleet. Do not assume one GitHub.com App credential works on GHES. No speculative GHES network client, host fallback, or configuration UI is authorized by this documentation task.

The existing CDEvents #440 architecture currently uses a KAORI-specific delivery repository/SHA contract. Reuse its **delivery evidence** in #559 but do not generalize its `OXY7O/KAORI` or 40-character exact-SHA assumptions into a universal Source Control repository/revision schema.

## Bounded implementation sequence and acceptance handoff

Implementation is **not** authorized directly from closed architecture issue #559 or this documentation addendum. Create reviewable child workstreams:

1. **SC-01 — Taxonomy and identity contract:** capability registration, IntegrationInstance/App/installation/account/repository cardinality, host-qualification, schema and resource-scoped RBAC; document the no-duplicate-provider-registry decision.
2. **SC-02 — GitHub App provider onboarding:** secure credentials/token broker, installation selection, dual repository grants, capability/readiness, webhook verification, rate-limit/revocation and admin UX.
3. **SC-03 — Committed repository discovery:** authorized pagination, deterministic native IDs, rename/transfer history, selective access, generation-safe reconciliation, independent Job evidence and freshness.

Later #559 workstreams handle PR/review/check, Actions/CI, governance, contributions, releases/deployments, Source -> Artifact -> Runtime lineage, Intelligence, reporting, and Source Control operational UX. They must consume the same stable identities instead of inventing parallel provider records.

**Required future validation (SC-01–SC-03):**

- Two independent real GitHub App installations covering two distinct organizations; `OXY7O` is the first reference.
- Both Selected Repositories and All Repositories configurations, including additions and removals; zero leak across organization/installation scope.
- Repository rename/transfer continuity; deselection or inaccessible grants yield Access Lost, not Deleted.
- Missing capability permission versus invalid/unavailable installation; independent evidence freshness.
- Webhook signature, spoofing, replay/deduplication, malformed payload, stale-event ordering, retry and reconciliation recovery.
- Revoked credential, rotated key, suspension/uninstall/reinstall, expired token, API outage, partial pagination, rate-limit exhaustion, and no plaintext secrets in evidence.
- GitHub.com API-specific acceptance and real integration UAT; GHES is **not** counted as tested or supported.

Documentation changes do not bypass Developer Check, Full Admission, human review, or later real-environment UAT. Registry UAT remains separately held; the shared `kaori/review/staging-uat` review branch is not part of this work.

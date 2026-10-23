# Source Control — SC-01 foundation

Authority: [#559](https://github.com/OXY7O/KAORI/issues/559), [#958](https://github.com/OXY7O/KAORI/issues/958), implementation [#2740](https://github.com/OXY7O/KAORI/issues/2740).

This initial SC-01 increment reserves the **Source Control** capability in the canonical integration taxonomy, and **GitHub** in the provider matrix as **planned**, not Available. The shared Integrations domain route uses the existing workspace; no provider adapter/instance is registered and no live GitHub access, tokens, inventory or Product UI are claimed.

`identity.py` defines immutable, host-qualified provider-native keys for App installation, account, repository, exact revision and branch/tag reference. It does **not** represent a GitHub App installation as an account, infer repository access from a name, interpret branch/tag as immutable source, or provide authorization by itself.

## Next bounded SC-01 work

- Review the new inert persisted identities against the live schema and verify migrations/foreign keys with Dev Container tests.
- Preserve committed relationship history, effective dates, observation/freshness, and explicit access-lost vs deleted semantics.
- Verify existing migrations, identity service, RBAC/#724, definition and navigation contracts before marking SC-01 complete.

SC-02 (#2741) owns provider authentication/readiness; SC-03 (#2742) owns authorized collection, snapshot publication and reconciliation. Do not activate GitHub in the provider matrix until its real adapter and security/validation gates are admitted.


## Persisted identity contract (SC-01 increment)

The migration `20261023_sc_identity` adds *inert* source records with no seeded
connection, GitHub tokens, live API reads, or provider availability claims.

| Model | Authority |
| --- | --- |
| `SourceAccount` | Host-qualified GitHub native account, independent of mutable login |
| `SourceInstallation` | One IntegrationInstance to one App installation grant; optional linked account |
| `SourceRepository` | Host-qualified native repository ID, independent of name/owner and installation |
| `SourceRepositoryGrant` | Installation-to-repository access, effective-dated independently of provider presence |
| `SourceRevision` | Sparse repository-scoped exact SHA; no git history mirror |
| `SourceReference` / `SourceReferenceTransition` | Current branch/tag targets and independently observed ref transitions |

The database uniquely keys accounts, repository IDs, installations and
repository-scoped source revisions. A partial unique index limits each
installation/repository pair to one currently open access grant; historical
records remain retained. A repository may be visible through multiple
installations without duplicating its identity. `provider_presence`,
`archived`, `grant_status` and `access_status` are independent; data
absence, scope change and provider unavailability are not deletion proof.

SC-02 must never persist App private keys or short-lived installation tokens in
these tables. Only the canonical credential boundary can own such protected
material. SC-03 must enforce same-host/same-repository references, verified
source identity, generation-safe writes, observations and effective-dated
transition semantics in its worker/services; raw CRUD writes are not
authorization or observation evidence.

**UI contract:** reuse the existing Integration domain page and its shared
Hero, cards, tables, modals, pagination, HTMX and semantic state components.
No GitHub-specific page or duplicated Violet styles are introduced by SC-01.
The provider remains `planned` until qualified SC-02 readiness/UAT.


## SC-03 — GitHub committed Repository Inventory (#2742, in implementation)

This section is a **candidate on issue-scoped branch**, not an admitted
capability. It depends on SC-01 #2740 and SC-02 #2741, whose Draft PRs
remain unmerged. GitHub is still `planned`; no connection, JobExecution
or repository inventory may be advertised Ready in live UI.

- `repository_discovery.py` asks GitHub.com for the installation's exact
  granted repository pages (20 per page, bounded to 200 pages). It verifies
  installation App/account/scope before and after collection; token scope,
  native owner identity, stable `total_count`, unique native IDs and
  exhaustive pagination. A rate limit, malformed page, revoked installation,
  unexpected scope, token expiry or bound exceeded must **fail closed** with
  no committed inventory changes.
- `SourceRepositoryCollectionState` provides per-installation fencing:
  reserve a generation and commit that reservation before network reads.
  A later reservation makes an older scan stale; only the current complete
  generation can commit. Collection state, scope, prior successful coverage,
  last-committed timestamp and count remain distinct.
- `repository_commit.py` updates SourceAccount/SourceRepository by their
  immutable provider+host+native IDs, preserving rename continuity and
  optional previously observed values. Access is separately effective-dated
  per installation. Only a complete grant inventory may close a granted
  relationship into `access_lost`. A repository is **never labeled deleted**
  because its selected installation grant disappeared; other installations
  retain their own access evidence.
- `repository_sync.py` is a candidate service callable by a future worker:
  reserve -> collect -> publish, or record a sanitized degraded generation.
  It does not register a new Celery task or dispatch a job. The approved
  worker must reuse canonical KAORI JobExecution and SC-02 installation
  identity, implementing scheduling, retries, recovery and webhook-triggered
  reconciliation only after security/CI/UAT admission.
- `repository_inventory.py` is a **committed-state-only** page projection,
  with KAORI pagination 5/10/25/50. It requires an installation ID that
  has already passed #724 resource-scoped authorization; it has no route
  until that constraint is enforced. If no complete generation was committed,
  count and coverage are UNKNOWN rather than zero.
- This increment does not implement a Git clone, file blobs, PR/Actions,
  committed default-branch SHA, ref transition collection, branch/tag
  history, full repository timeline, global Source Control inventory route,
  provider kernel activation, new UI primitives, or production GitHub calls.
  Exact source revision/ref evidence requires independently verified
  GitHub API reads before being committed.

**Migration:** `20261023_sc_repo_collection`, downstream of
`20261023_sc_webhook_delivery` on the stacked review branch. It adds
`default_branch`, `visibility`, and a new collection-state table; no
provider identities or repository rows are seeded. Run existing KAORI
`verify_migration_graph.py`, migration upgrade/downgrade, `ruff`,
`pyright`, and focused `pytest` through Developer Check in the
Dev Container. Evidence must include cross-organization/installation
negative tests and live All/Selected grant reconciliation. No official
staging/main CI is authorized yet.

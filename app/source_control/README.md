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

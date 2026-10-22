# Source Control — SC-01 foundation

Authority: [#559](https://github.com/OXY7O/KAORI/issues/559), [#958](https://github.com/OXY7O/KAORI/issues/958), implementation [#2740](https://github.com/OXY7O/KAORI/issues/2740).

This initial SC-01 increment reserves the **Source Control** capability in the canonical integration taxonomy, and **GitHub** in the provider matrix as **planned**, not Available. The shared Integrations domain route uses the existing workspace; no provider adapter/instance is registered and no live GitHub access, tokens, inventory or Product UI are claimed.

`identity.py` defines immutable, host-qualified provider-native keys for App installation, account, repository, exact revision and branch/tag reference. It does **not** represent a GitHub App installation as an account, infer repository access from a name, interpret branch/tag as immutable source, or provide authorization by itself.

## Next bounded SC-01 work

- Reconcile existing `IntegrationInstance` cardinality with the App/installation grant model and implement reviewed persistence/migrations for SourceAccount/Repository/SourceRevision/Reference plus access/grant relationship.
- Preserve committed relationship history, effective dates, observation/freshness, and explicit access-lost vs deleted semantics.
- Verify existing migrations, identity service, RBAC/#724, definition and navigation contracts before marking SC-01 complete.

SC-02 (#2741) owns provider authentication/readiness; SC-03 (#2742) owns authorized collection, snapshot publication and reconciliation. Do not activate GitHub in the provider matrix until its real adapter and security/validation gates are admitted.

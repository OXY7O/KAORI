# Scoped Secrets & PKI KV v2 Registry — pre-admission contract (#2678)

## Authority

Secrets & PKI (#714, #2591, #2597) and accepted Scoped Authorization v1
(#724) are independent. RBAC secrets_pki.view answers what action is
allowed; the #724 policy must decide which IntegrationInstance, namespace
and mount the actor can see. Ownership, Team membership, similarly named
Secret paths, and provider Vault ACLs never grant KAORI rights implicitly.

## Status: prepared, not exposed

The new app/secrets_pki/scoped_registry.py is a server-internal SQL read
model. No HTTP route, UI link, new scope-policy engine/table, JobExecution,
migration, provider call, Secret value access or permission is added.
Until #724 supplies an admitted persisted policy evaluator, no real user
can browse rows through KAORI. The ScopedRegistryDecision passed to
the function is *not* itself an authorization system, policy grant or
cryptographic evidence. Test fixtures may construct synthetic decisions;
production must never construct them from request params, cookies,
Vault paths, provider data, user preferences or role alone.

## Query safety

Future decisions must be fresh (up to five minutes), valid for at most
fifteen minutes, and bound to exact current actor, permission,
IntegrationInstance, namespace/mount and an opaque policy reference.
Denied/absent/expired/wrong actor/invalid page limit yields
scope_required, total_items=None and zero rows.

Independently verify enabled active ready Vault IntegrationInstance,
approved matching KV v2 namespace/mount, current complete ready 24-hour
collection and matching committed current-generation representations.
Stale, partial, conflicting counts, revoked mount, disabled provider,
oversized registry and missing schema yield source_unavailable without
a count or existence disclosure.

Outward rows include only canonical SecretIdentity UUID, material
version number/count, CAS policy flag, logical lifecycle and observation
time. SQL never selects Vault path, name or namespace into outward rows.
Historical not_observed representations are excluded, and version readbacks
must agree with the qualifying generation. Max 200 representations;
server-side page sizes are 5/10/25/50, with 100 observed versions per row
as a supported upper bound. Qualified empty is allowed only after a
complete committed zero snapshot.

## Remaining requirements before UI

1. Implement canonical persisted resource-policy evaluation under #724;
   do not infer scope from integrations.manage or a Vault administrator role.
2. Wire server-side permission and exact policy enforcement to direct
   route, HTMX, Registry, Detail, search, export, report and graph reads.
   Ensure policy checks happen before SQL counts or row materialization.
3. Adopt existing Violet table_registry macros, Fast Shell/lazy HTMX,
   default page size five, canonical loading/clear filter/empty/error,
   responsive light/dark and accessible action patterns.
4. Run exact-SHA pytest/Ruff/Pyright, PostgreSQL, RBAC-negative,
   DevContainer supported Vault metadata/403 and human Visual QA/UAT.
   Review source merge is not an acceptance result.

No raw Secret, SecretID, token, path, private key, value hash, dynamic
credential, sensitive provider error or raw response may be rendered,
persisted or logged. This read model does not prove rotation, consumer
cutover, Kubernetes materialization or delivered endpoint TLS.

Focused contract tests:
tests/integrations/test_scoped_secrets_pki_registry.py.

# Legacy Cutover Phase 6 — Destructive Readiness Audit

Phase 6 does not drop legacy tables. It adds a deterministic, read-only gate that must pass before a destructive Alembic migration is authored or applied.

## Command

```bash
flask --app run:app audit-integration-legacy
```

Machine-readable output:

```bash
flask --app run:app audit-integration-legacy --json-output --no-strict
```

The default strict mode exits non-zero when at least one destructive blocker remains. `--no-strict` is intended only for inspection and CI artifact collection.

## Gates

The audit verifies:

1. Active application modules do not query legacy provider configuration or provider-specific binding models.
2. Legacy tables are empty or absent.
3. Every Prometheus and Alertmanager provider record has a matching canonical `IntegrationInstance` of the correct provider type.
4. Every Kubernetes cluster has a canonical `KubernetesConnection`.
5. Canonical integration identities and bindings have no detected orphan records.

The report separately lists clusters that still retain data in `clusters.kubeconfig`. That data is not an active read authority, but it must be copied, verified, and removed by the final destructive migration.

## Removal rule

Do not create or apply the schema-removal migration until the command reports:

```text
Ready for schema removal: YES
```

The final destructive phase may then remove:

- `prometheus_configs`
- `prometheus_bindings`
- `alertmanager_configs`
- `alertmanager_bindings`
- `clusters.kubeconfig`
- legacy ORM relationships and exports

Historical Alembic migrations remain unchanged because they are required to reconstruct databases from an empty state.

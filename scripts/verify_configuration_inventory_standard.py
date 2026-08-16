from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []
    collector = read('app/inventory/kubernetes/collectors/configuration.py')
    persistence = read('app/inventory/kubernetes/persistence.py')
    model = read('app/models/inventory.py')
    semantics = read('app/inventory/kubernetes/resources/configuration_semantics.py')
    backend = read('app/inventory/kubernetes/resources/configuration.py')
    routes = read('app/inventory/kubernetes/routes.py')
    topology = read('app/inventory/kubernetes/topology/node_builder.py')
    payload = read('app/reports/export/payloads/inventory.py')
    xlsx = read('app/reports/export/xlsx/standard.py')
    workspace = read('app/templates/inventory/kubernetes/configuration/partials/_page_workspace.html')
    card = read('app/templates/inventory/kubernetes/configuration/partials/_table_card.html')
    table = read('app/templates/inventory/kubernetes/configuration/partials/_table_content.html')
    summary = read('app/templates/inventory/kubernetes/configuration/partials/_summary_cards.html')
    detail = read('app/templates/inventory/kubernetes/configuration/partials/_configuration_detail_content.html')
    metadata_component = read('app/templates/components/technical_metadata_collection.html')
    migration = read('migrations/versions/20260805_config_inventory_v2.py')
    quality_gate = read('scripts/quality_gate.sh')
    standard = read('docs/design/patterns/KUBERNETES_CONFIGURATION_INVENTORY.md')
    audit = read('docs/design/audits/KUBERNETES_CONFIGURATION_INVENTORY_ALIGNMENT_AUDIT_2026_08.md')

    for token in (
        "'inventory.configmaps': ADAPTER_NOT_SELECTED if not include_configmaps else COLLECTED",
        "'inventory.secrets': ADAPTER_NOT_SELECTED if not include_secrets else COLLECTED",
        "if getattr(exc, 'status', None) in {403, 404}:",
        "'key_names': key_names",
        "'immutable': bool(config_map.immutable)",
        "'immutable': bool(secret.immutable)",
    ):
        require(token in collector, f'Configuration collector missing canonical token: {token}', errors)
    require('base64.b64decode' not in collector, 'Configuration collector must never decode Secret values.', errors)
    require(
        "'key_count':" not in collector and "'payload_size_bytes':" not in collector,
        'Collector must not persist derived key counts or synthetic payload sizes.',
        errors,
    )
    require(
        'inventory.key_count' not in persistence and 'inventory.payload_size_bytes' not in persistence,
        'Persistence must not write removed Configuration columns.',
        errors,
    )

    configuration_class = model.split('class ConfigurationInventory', 1)[1].split('class ResourceQuotaInventory', 1)[0]
    require(
        'key_count:' not in configuration_class and 'payload_size_bytes:' not in configuration_class,
        'ConfigurationInventory must store only canonical key_names, not derived columns.',
        errors,
    )
    require(
        "op.drop_column('configuration_inventory', 'key_count')" in migration,
        'Configuration migration must drop key_count.',
        errors,
    )
    require(
        "op.drop_column('configuration_inventory', 'payload_size_bytes')" in migration,
        'Configuration migration must drop payload_size_bytes.',
        errors,
    )
    require(
        "down_revision = '20260805_ingress_inventory_v2'" in migration,
        'Configuration migration must extend the canonical Inventory head.',
        errors,
    )

    for token in (
        "POD_EVIDENCE_KEY = 'inventory.pods'",
        'pod_reference_presentation(',
        'aggregate_collection_states(',
        "return ('Immutable', 'info') if immutable else ('Mutable', 'brand')",
    ):
        require(token in semantics, f'Configuration semantics missing token: {token}', errors)
    require(
        'pod_operational_state(pod.phase, pod.ready)' in backend,
        'Related Pod previews must use canonical Pod posture.',
        errors,
    )
    require(
        'pod_collection_state != COLLECTED' in backend,
        'Pod reference counts must honor Pod collection evidence.',
        errors,
    )
    require(
        'KEY_PREVIEW_LIMIT = 100' in backend and 'key_entries_truncated' in backend,
        'Large key inventories must use a bounded detail preview.',
        errors,
    )
    require('def _pod_state(' not in backend, 'Legacy local Pod phase wrapper must be removed.', errors)

    canonical_tuple = "for resource in ('nodes', 'namespaces', 'configuration', 'workloads', 'pods', 'services', 'ingresses', 'storage')"
    require(
        canonical_tuple in routes,
        'Configuration must participate directly in canonical Inventory workspace routing.',
        errors,
    )
    require(
        not (ROOT / 'app/templates/inventory/kubernetes/configuration/partials/_inventory_scope.html').exists(),
        'Legacy Configuration inventory scope wrapper must be removed.',
        errors,
    )
    require(
        'id="configuration-page-workspace"' in workspace
        and 'inventory/kubernetes/components/_data_freshness.html' in workspace,
        'Configuration workspace must own Hero and Snapshot Context.',
        errors,
    )
    require(
        'hx-target="#configuration-page-workspace"' in card and 'name="partial_mode" value="page_workspace"' in card,
        'Configuration filters must refresh the complete workspace.',
        errors,
    )
    require(
        'aria-label="Configuration inventory filters"' in card,
        'Configuration filters require an accessible label.',
        errors,
    )
    require(
        '<caption class="sr-only">' in table and table.count('scope="col"') == 6,
        'Configuration table requires a caption and six scoped columns.',
        errors,
    )
    require(
        'hx-target="#configuration-table-content"' in table and 'name="partial_mode" value="table_content"' in table,
        'Configuration pagination must use the canonical table-content boundary.',
        errors,
    )
    require('Age ' not in table, 'Age must remain in Configuration detail rather than the compact table.', errors)
    require(
        'Reference Evidence Gaps' in summary and 'Pod Reference Collection' in summary,
        'Configuration summary must expose Pod reference evidence gaps.',
        errors,
    )

    for token in (
        'Values Not Persisted',
        'Pod Reference Collection',
        'Pod Reference Evidence Not Reported',
        'Not Reported',
        'key_entries_truncated',
        'Open ConfigMap Management',
        'Open Secret Management',
    ):
        require(token in detail, f'Configuration detail missing token: {token}', errors)
    require(
        'total_count=none, truncated=false' in metadata_component,
        'Shared metadata collection must support bounded previews with factual totals.',
        errors,
    )

    require(
        "'key_count': len(item.key_names or [])" in payload,
        'Configuration export must derive key count from canonical key_names.',
        errors,
    )
    require(
        "'metadata_boundary': 'Key Names Only'" in payload,
        'Configuration export must declare its metadata boundary.',
        errors,
    )
    require(
        "'value_persistence': 'None'" in payload,
        'Configuration export must declare that values are not persisted.',
        errors,
    )
    require(
        'payload_size_bytes' not in payload and 'Payload Size (bytes)' not in xlsx,
        'Synthetic payload size must be removed from export.',
        errors,
    )
    require(
        'Metadata Boundary' in xlsx and 'Value Persistence' in xlsx,
        'Configuration workbook must expose the protected metadata boundary.',
        errors,
    )
    require(
        "field('Keys', len(item.key_names or []), empty='0')" in topology,
        'Topology must derive key counts from canonical key_names.',
        errors,
    )
    require('Payload Bytes' not in topology, 'Topology must not expose the removed synthetic payload metric.', errors)

    require(
        'Kubernetes Configuration Inventory Standard' in standard,
        'Configuration Inventory standard documentation is missing.',
        errors,
    )
    require(
        'legacy `_inventory_scope.html` wrapper' in audit,
        'Configuration audit must record legacy wrapper removal.',
        errors,
    )
    require(
        'verify_configuration_inventory_standard.py' in quality_gate,
        'Configuration verifier must run in the quality gate.',
        errors,
    )

    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1
    print(
        'KAORI Configuration Inventory Standard audit passed: protected key-index collection, '
        'evidence-aware Pod references, canonical workspace, bounded detail preview, export boundary, '
        'topology, accessibility, migration, and legacy cleanup are aligned.'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

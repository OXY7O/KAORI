from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []
    collector = read('app/inventory/kubernetes/collectors/storage.py')
    persistence = read('app/inventory/kubernetes/persistence.py')
    backend = read('app/inventory/kubernetes/resources/storage.py')
    semantics = read('app/inventory/kubernetes/resources/storage_semantics.py')
    routes = read('app/inventory/kubernetes/routes.py')
    topology = read('app/inventory/kubernetes/topology/node_builder.py')
    payload = read('app/reports/export/payloads/inventory.py')
    xlsx = read('app/reports/export/xlsx/standard.py')
    workspace = read('app/templates/inventory/kubernetes/storage/partials/_page_workspace.html')
    card = read('app/templates/inventory/kubernetes/storage/partials/_table_card.html')
    table = read('app/templates/inventory/kubernetes/storage/partials/_table_content.html')
    summary = read('app/templates/inventory/kubernetes/storage/partials/_summary_cards.html')
    detail = read('app/templates/inventory/kubernetes/storage/partials/_storage_detail_content.html')
    standard = read('docs/design/patterns/KUBERNETES_STORAGE_INVENTORY.md')
    audit = read('docs/design/audits/KUBERNETES_STORAGE_INVENTORY_ALIGNMENT_AUDIT_2026_08.md')
    quality_gate = read('scripts/quality_gate.sh')

    for token in (
        "STORAGE_CLASS_EVIDENCE_KEY = 'inventory.storageclasses'",
        "PERSISTENT_VOLUME_EVIDENCE_KEY = 'inventory.persistentvolumes'",
        "PERSISTENT_VOLUME_CLAIM_EVIDENCE_KEY = 'inventory.persistentvolumeclaims'",
        'with_evidence: Literal[True]',
        "if getattr(exc, 'status', None) in {403, 404}:",
        "'allow_volume_expansion_reported': allow_expansion is not None",
        "'status_evidence_reported': status is not None",
        "'capacity_evidence_reported':",
        "'data_source_ref', 'dataSourceRef'",
        "'status': 'Configured'",
        "'status': lifecycle",
    ):
        require(token in collector, f'Storage collector missing canonical token: {token}', errors)
    require(
        "'capacity': '-'" not in collector,
        'Missing storage capacity must not be persisted as a presentation dash.',
        errors,
    )
    require(
        'raise' in collector and "status', None) in {403, 404}" in collector,
        'Unexpected storage API failures must not be hidden.',
        errors,
    )
    require(
        'except AttributeError' not in collector,
        'Unexpected generated-client AttributeError failures must not be hidden.',
        errors,
    )
    require(
        'items, collection_evidence = get_storage_inventory(' in persistence,
        'Storage persistence must request collection evidence.',
        errors,
    )
    require(
        'committed_evidence.update(collection_evidence)' in persistence,
        'Storage collection evidence must be committed.',
        errors,
    )

    for state in (
        'Configured',
        'Bound',
        'Available',
        'Pending',
        'Released',
        'Terminating',
        'Failed',
        'Lost',
        'Unknown',
        'Not Reported',
    ):
        require(state in semantics, f'Storage lifecycle semantic missing: {state}', errors)
    require(
        "'Not Allowed'" in semantics, 'StorageClass expansion=false must remain distinct from missing evidence.', errors
    )
    require("return 'Not Applicable'" in semantics, 'Non-StorageClass expansion must be Not Applicable.', errors)
    require(
        "NOT_CONFIGURED = 'Not Configured'" in semantics and "NOT_ASSIGNED = 'Not Assigned'" in semantics,
        'Storage presentation must distinguish classless/unassigned state from missing evidence.',
        errors,
    )
    require(
        'pod_operational_state(pod.phase, pod.ready)' in backend,
        'Mounted Pod previews must use canonical Pod posture.',
        errors,
    )
    require(
        "states['persistent_volume_claims'] != COLLECTED" in backend,
        'Claim relationships must honor PVC collection evidence.',
        errors,
    )
    require("states['pods'] == COLLECTED" in backend, 'Pod relationships must honor Pod collection evidence.', errors)
    require(
        "cast(PodInventory.persistent_volume_claims, JSONB).op('?|')" in backend,
        'Mounted-Pod relationships must use namespace-grouped JSONB overlap.',
        errors,
    )
    require(
        'claims[:200]' not in backend,
        'Mounted-Pod relationship evidence must not be silently capped at 200 claims.',
        errors,
    )

    require(
        "for resource in ('nodes', 'namespaces', 'configuration', 'workloads', 'pods', 'services', 'ingresses', 'storage')"
        in routes,
        'Storage must participate directly in canonical Inventory workspace mapping.',
        errors,
    )
    require(
        not (ROOT / 'app/templates/inventory/kubernetes/storage/partials/_inventory_scope.html').exists(),
        'Legacy Storage inventory scope wrapper must be removed.',
        errors,
    )
    require(
        'id="storage-page-workspace"' in workspace and 'inventory/kubernetes/components/_data_freshness.html' in workspace,
        'Storage workspace must own Hero and Snapshot Context.',
        errors,
    )
    require(
        'hx-target="#storage-page-workspace"' in card and 'name="partial_mode" value="page_workspace"' in card,
        'Storage filters must refresh the complete workspace.',
        errors,
    )
    require('aria-label="Storage inventory filters"' in card, 'Storage filters require an accessible label.', errors)
    require(
        '<caption class="sr-only">' in table and table.count('scope="col"') == 6,
        'Storage table requires caption and scoped columns.',
        errors,
    )
    require(
        'hx-target="#storage-table-content"' in table and 'name="partial_mode" value="table_content"' in table,
        'Storage pagination must use canonical table-content boundary.',
        errors,
    )
    require(' · Age ' not in table, 'Age must remain in Storage detail rather than the compact table.', errors)
    require(
        'Not Reported' in summary and 'inventory.collection' in summary,
        'Storage summary must expose collection evidence gaps.',
        errors,
    )
    for token in (
        'Requested Access Modes',
        'Reported Access Modes',
        'Bound Capacity',
        'Specification Evidence',
        'Status Evidence',
        'Volume Source Evidence',
        'Claim Evidence Not Reported',
        'Pod Mount Evidence Not Reported',
        'Not Allowed',
        'Not Applicable',
    ):
        require(
            token in detail or token in backend or token in semantics,
            f'Storage detail missing evidence token: {token}',
            errors,
        )

    require(
        'storage_lifecycle_presentation(item.storage_type, item.status, details)' in payload,
        'Storage export must use canonical lifecycle semantics.',
        errors,
    )
    for field in (
        'requested_capacity',
        'reported_capacity',
        'binding_reference',
        'volume_expansion',
        'specification_evidence',
        'status_evidence',
    ):
        require(f"'{field}'" in payload, f'Storage export missing field: {field}', errors)
    for column in (
        'Requested Capacity',
        'Reported Capacity',
        'Binding Reference',
        'Volume Expansion',
        'Specification Evidence',
        'Status Evidence',
    ):
        require(column in xlsx, f'Storage workbook missing column: {column}', errors)
    require(
        'storage_lifecycle_presentation(' in topology and "field('Binding Reference'" in topology,
        'Topology must consume canonical Storage lifecycle and binding evidence.',
        errors,
    )

    require('Kubernetes Storage Inventory Standard' in standard, 'Storage standard documentation is missing.', errors)
    require('legacy `_inventory_scope.html` wrapper' in audit, 'Storage audit must record legacy cleanup.', errors)
    require(
        'verify_storage_inventory_standard.py' in quality_gate, 'Storage verifier must run in the quality gate.', errors
    )

    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1
    print('PASS — KAORI Storage Inventory')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

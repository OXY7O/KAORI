from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_pod_workspace_refreshes_scope_and_snapshot_context() -> None:
    routes = read('app/inventory/routes.py')
    workspace = read('app/templates/inventory/pods/partials/_page_workspace.html')
    card = read('app/templates/inventory/pods/partials/_table_card.html')

    assert "for resource in ('nodes', 'namespaces', 'workloads', 'pods', 'services', 'ingresses')" in routes
    assert 'id="pods-page-workspace"' in workspace
    assert 'inventory/components/_data_freshness.html' in workspace
    assert 'hx-target="#pods-page-workspace"' in card
    assert 'name="partial_mode" value="page_workspace"' in card
    assert 'aria-label="Pod inventory filters"' in card


def test_pod_filters_preserve_unknown_and_unscheduled_evidence() -> None:
    service = read('app/inventory/resources/pods.py')
    routes = read('app/inventory/routes.py')
    card = read('app/templates/inventory/pods/partials/_table_card.html')

    assert "UNKNOWN_FILTER = '__unknown__'" in service
    assert "UNSCHEDULED_FILTER = '__unscheduled__'" in service
    assert "{'value': UNKNOWN_FILTER, 'label': 'Unknown'}" in service
    assert "{'value': UNSCHEDULED_FILTER, 'label': 'Not Scheduled'}" in service
    assert "valid_pod_statuses = {option['value'] for option in pod_statuses}" in routes
    assert "valid_nodes = {option['value'] for option in nodes}" in routes
    assert 'status_option.value' in card
    assert 'node_option.value' in card


def test_pod_collector_commits_runtime_and_owner_resolution_evidence() -> None:
    collector = read('app/inventory/collectors/pods.py')
    persistence = read('app/inventory/persistence.py')

    assert "ready = f'{ready_count}/{total_count}' if runtime_evidence_reported else 'Not Reported'" in collector
    assert "lifecycle_phase = 'Terminating' if deletion_timestamp is not None else kubernetes_phase" in collector
    assert "if getattr(exc, 'status', None) in {403, 404}:" in collector
    assert "'inventory.pods.owner-resolution.replicasets'" in collector
    assert "'inventory.pods.owner-resolution.jobs'" in collector
    assert "*container_inventory['ephemeral_specs']" in collector
    assert 'ephemeral_container_statuses' in collector
    assert 'pods, collection_evidence = get_pods(' in persistence
    assert 'committed_evidence.update(collection_evidence)' in persistence


def test_pod_detail_distinguishes_absence_from_unreported_evidence() -> None:
    detail = read('app/templates/inventory/pods/partials/_pod_detail_content.html')
    semantics = read('app/inventory/resources/pod_semantics.py')

    for token in (
        'Condition Evidence Not Reported',
        'Pod Specification Not Reported',
        'Volume Evidence Not Reported',
        'Configuration Reference Evidence Not Reported',
        'Owner Resolution Incomplete',
    ):
        assert token in detail
    assert 'pod.specification_evidence_reported' in detail
    assert 'pod.runtime_evidence_reported' in detail
    assert "'Unknown': (\n            'Validate Pod Runtime Evidence'" in semantics


def test_pod_tables_are_accessible_and_export_is_evidence_aware() -> None:
    table = read('app/templates/inventory/pods/partials/_table_content.html')
    detail = read('app/templates/inventory/pods/partials/_pod_detail_content.html')
    export_payload = read('app/reports/export/payloads/inventory.py')
    export_standard = read('app/reports/export/xlsx/standard.py')

    assert '<caption class="sr-only">' in table
    assert table.count('scope="col"') == 6
    assert '<caption class="sr-only">Volumes and mounts for Pod' in detail
    assert detail.count('scope="col"') >= 4
    assert "'restarts': item.restart_count if runtime_reported else None" in export_payload
    assert "'container_count': configured_container_count if specification_reported else None" in export_payload
    assert 'regular, init, and ephemeral image references' in export_standard


def test_pod_standard_is_documented_and_release_gated() -> None:
    standard = read('docs/design/patterns/KUBERNETES_POD_INVENTORY.md')
    audit = read('docs/design/audits/KUBERNETES_POD_INVENTORY_ALIGNMENT_AUDIT_2026_08.md')
    quality_gate = read('scripts/quality_gate.sh')

    assert 'Kubernetes Pod Inventory Standard' in standard
    assert 'Owner-resolution evidence' in audit
    assert 'verify_pod_inventory_standard.py' in quality_gate

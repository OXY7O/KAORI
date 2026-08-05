from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORKSPACE = ROOT / 'app/templates/inventory/storage/partials/_page_workspace.html'
SUMMARY = ROOT / 'app/templates/inventory/storage/partials/_summary_cards.html'
CARD = ROOT / 'app/templates/inventory/storage/partials/_table_card.html'
TABLE = ROOT / 'app/templates/inventory/storage/partials/_table_content.html'
DETAIL = ROOT / 'app/templates/inventory/storage/partials/_storage_detail_content.html'
COLLECTOR = ROOT / 'app/inventory/collectors/storage.py'
SERVICE = ROOT / 'app/inventory/resources/storage.py'
SEMANTICS = ROOT / 'app/inventory/resources/storage_semantics.py'
PERSISTENCE = ROOT / 'app/inventory/persistence.py'
PAYLOAD = ROOT / 'app/reports/export/payloads/inventory.py'
XLSX = ROOT / 'app/reports/export/xlsx/standard.py'


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_storage_inventory_uses_canonical_resource_page_pattern() -> None:
    workspace = read(WORKSPACE)
    summary = read(SUMMARY)
    card = read(CARD)
    table = read(TABLE)

    assert 'id="storage-page-workspace"' in workspace
    assert 'inventory/components/_data_freshness.html' in workspace
    assert 'Storage Lifecycle Posture' in summary
    assert 'posture_grid.render(metrics, columns=3)' in summary
    assert 'hx-target="#storage-page-workspace"' in card
    assert 'name="partial_mode" value="page_workspace"' in card
    assert 'aria-label="Storage inventory filters"' in card
    assert (
        'lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,0.9fr)'
        '_minmax(0,0.9fr)_minmax(16rem,1.35fr)]' in card
    )
    for control_id in (
        'storage-cluster-filter',
        'storage-namespace-filter',
        'storage-type-filter',
        'storage-lifecycle-filter',
        'storage-search',
    ):
        assert f'id="{control_id}"' in card or f"id='{control_id}'" in card
        assert f'for="{control_id}"' in card
    for column in ('Storage Object', 'Scope', 'Provisioning', 'Capacity & Access', 'Binding & Lifecycle', 'Details'):
        assert column in table
    assert '<caption class="sr-only">' in table
    assert table.count('scope="col"') == 6
    assert 'hx-target="#storage-table-content"' in table
    assert 'name="partial_mode" value="table_content"' in table
    assert ' · Age ' not in table


def test_storage_collector_and_persistence_preserve_explicit_collection_evidence() -> None:
    collector = read(COLLECTOR)
    persistence = read(PERSISTENCE)

    for token in (
        "STORAGE_CLASS_EVIDENCE_KEY = 'inventory.storageclasses'",
        "PERSISTENT_VOLUME_EVIDENCE_KEY = 'inventory.persistentvolumes'",
        "PERSISTENT_VOLUME_CLAIM_EVIDENCE_KEY = 'inventory.persistentvolumeclaims'",
        'with_evidence: Literal[True]',
        "if getattr(exc, 'status', None) in {403, 404}:",
        "'allow_volume_expansion_reported': allow_expansion is not None",
        "'status_evidence_reported': status is not None",
        "'capacity_evidence_reported':",
        "'status': 'Configured'",
    ):
        assert token in collector
    assert 'items, collection_evidence = get_storage_inventory(' in persistence
    assert 'committed_evidence.update(collection_evidence)' in persistence
    assert "'capacity': '-'" not in collector


def test_storage_detail_uses_adaptive_stacks_and_factual_configuration() -> None:
    detail = read(DETAIL)
    semantics = read(SEMANTICS)
    service = read(SERVICE)

    assert 'data-kaori-detail-density="adaptive-stacks"' in detail
    assert 'detail.expanded_workspace_shell_classes()' in detail
    for title in ('Storage Identity', 'Capacity & Access', 'Binding & Lifecycle', 'Provisioning Configuration'):
        assert f"detail.detail_card('{title}'" in detail
    assert 'related_collection.render(' in detail
    assert 'metadata_collection.render(' in detail
    assert 'Committed Snapshot Boundary' in detail
    assert 'live filesystem usage, pressure, growth, performance, durability' in detail
    for state in ('Configured', 'Terminating', 'Not Reported', 'Not Allowed', 'Not Applicable'):
        assert state in semantics
    assert "states['persistent_volume_claims'] != COLLECTED" in service
    assert "states['pods'] == COLLECTED" in service
    assert 'pod_operational_state(pod.phase, pod.ready)' in service


def test_storage_relationships_are_bounded_and_use_current_generation() -> None:
    service = read(SERVICE)
    assert 'filter_current_generation' in service
    assert '.limit(8)' in service
    assert "cast(PodInventory.persistent_volume_claims, JSONB).op('?|')" in service
    assert 'for namespace, names in names_by_namespace.items()' in service
    assert 'claims[:200]' not in service
    assert "'pods_truncated': pod_count > 8" in service
    assert "'claims_truncated': len(claims) > 8" in service
    assert "'pods_reported': pods_reported" in service
    assert "'claims_reported': claims_reported" in service


def test_storage_export_uses_canonical_evidence_columns() -> None:
    payload = read(PAYLOAD)
    xlsx = read(XLSX)

    assert 'storage_lifecycle_presentation(item.storage_type, item.status, details)' in payload
    assert "'requested_capacity': requested_capacity" in payload
    assert "'reported_capacity': reported_capacity" in payload
    assert "'volume_expansion': storage_expansion_presentation(item.storage_type, details)" in payload
    assert "'specification_evidence':" in payload
    assert "'status_evidence':" in payload
    for column in (
        'Requested Capacity',
        'Reported Capacity',
        'Requested Access Modes',
        'Reported Access Modes',
        'Binding Reference',
        'Volume Expansion',
        'Specification Evidence',
        'Status Evidence',
    ):
        assert column in xlsx

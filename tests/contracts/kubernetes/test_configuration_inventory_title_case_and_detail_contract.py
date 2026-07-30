from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SUMMARY = ROOT / 'app/templates/inventory/configuration/partials/_summary_cards.html'
TABLE = ROOT / 'app/templates/inventory/configuration/partials/_table_content.html'
DETAIL = ROOT / 'app/templates/inventory/configuration/partials/_configuration_detail_content.html'
SERVICE = ROOT / 'app/inventory/resources/configuration.py'
COLLECTOR = ROOT / 'app/inventory/collectors/configuration.py'
MODEL = ROOT / 'app/models/inventory.py'
PERSISTENCE = ROOT / 'app/inventory/persistence.py'
MIGRATION = ROOT / 'migrations/versions/20260730_inventory_collection_evidence.py'


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_configuration_inventory_uses_canonical_resource_page_pattern() -> None:
    summary = read(SUMMARY)
    table = read(TABLE)

    assert 'Configuration Reference Posture' in summary
    assert 'posture_grid.render(posture_metrics, columns=3)' in summary
    for column in ('Configuration Object', 'Scope', 'Object Type', 'Metadata & Mutation', 'Current References', 'Details'):
        assert column in table
    assert 'table_ui.namespaced_scope_identity(' in table
    assert "endpoint='inventory.configuration'" in table
    assert 'hx-target="#configuration-inventory-scope"' in table
    assert '>Rows</label>' in table
    assert 'status_label(item.type' not in table
    assert 'status_label(\'Immutable\'' not in table


def test_configuration_detail_uses_adaptive_stacks_and_protected_boundary() -> None:
    detail = read(DETAIL)

    assert 'data-kaori-detail-density="adaptive-stacks"' in detail
    assert 'detail.expanded_workspace_shell_classes()' in detail
    assert "detail.detail_card('Object Identity'" in detail
    assert "detail.detail_card('Protected Data Boundary'" in detail
    assert "mode='keys'" in detail
    assert "related_collection.render('Current Pod References'" in detail
    assert 'Committed Snapshot Boundary' in detail
    assert 'Values Not Persisted' in detail
    assert 'does not decode, log, persist, or display value content' in detail
    assert 'Open ConfigMap Management' in detail
    assert 'Open Secret Management' in detail


def test_configuration_collector_uses_key_index_mode_and_collection_evidence() -> None:
    collector = read(COLLECTOR)
    service = read(SERVICE)
    model = read(MODEL)
    persistence = read(PERSISTENCE)
    migration = read(MIGRATION)

    assert 'with_evidence: bool = False' in collector
    assert "'payload_size_bytes': 0" in collector
    assert 'base64.b64decode' not in collector
    assert "PERMISSION_UNAVAILABLE = 'Permission Unavailable'" in collector
    assert "ADAPTER_NOT_SELECTED = 'Adapter Not Selected'" in collector
    assert 'collection_state' in service
    assert 'row.collection_evidence' in service
    assert 'collection_evidence: Mapped[dict] = mapped_column(' in model
    assert 'cluster_inventory.collection_evidence = committed_evidence' in persistence
    assert "revision = '20260730_inventory_evidence'" in migration
    assert "down_revision = '20260729_report_delivery'" in migration
    assert "add_column(sa.Column('collection_evidence', sa.JSON()" in migration

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORKSPACE = ROOT / 'app/templates/inventory/kubernetes/configuration/partials/_page_workspace.html'
SUMMARY = ROOT / 'app/templates/inventory/kubernetes/configuration/partials/_summary_cards.html'
CARD = ROOT / 'app/templates/inventory/kubernetes/configuration/partials/_table_card.html'
TABLE = ROOT / 'app/templates/inventory/kubernetes/configuration/partials/_table_content.html'
DETAIL = ROOT / 'app/templates/inventory/kubernetes/configuration/partials/_configuration_detail_content.html'
SERVICE = ROOT / 'app/inventory/kubernetes/resources/configuration.py'
SEMANTICS = ROOT / 'app/inventory/kubernetes/resources/configuration_semantics.py'
COLLECTOR = ROOT / 'app/inventory/kubernetes/collectors/configuration.py'
MODEL = ROOT / 'app/models/inventory.py'
PERSISTENCE = ROOT / 'app/inventory/kubernetes/persistence.py'
ROUTES = ROOT / 'app/inventory/kubernetes/routes.py'
PAYLOAD = ROOT / 'app/reports/export/payloads/inventory.py'
XLSX = ROOT / 'app/reports/export/xlsx/standard.py'
MIGRATION = ROOT / 'migrations/versions/20260805_config_inventory_v2.py'


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_configuration_inventory_uses_canonical_workspace_pattern() -> None:
    workspace = read(WORKSPACE)
    summary = read(SUMMARY)
    card = read(CARD)
    table = read(TABLE)
    routes = read(ROUTES)

    assert 'id="configuration-page-workspace"' in workspace
    assert 'inventory/kubernetes/components/_data_freshness.html' in workspace
    assert 'Configuration Reference Posture' in summary
    assert 'Reference Evidence Gaps' in summary
    assert 'Pod Reference Collection' in summary
    assert 'hx-target="#configuration-page-workspace"' in card
    assert 'name="partial_mode" value="page_workspace"' in card
    assert 'aria-label="Configuration inventory filters"' in card
    assert '<caption class="sr-only">' in table
    assert table.count('scope="col"') == 6
    assert 'hx-target="#configuration-table-content"' in table
    assert 'name="partial_mode" value="table_content"' in table
    assert 'Age ' not in table
    assert (
        "for resource in ('nodes', 'namespaces', 'configuration', 'workloads', 'pods', 'services', 'ingresses', 'storage')"
        in routes
    )
    assert not (ROOT / 'app/templates/inventory/kubernetes/configuration/partials/_inventory_scope.html').exists()


def test_configuration_detail_uses_protected_and_evidence_aware_boundaries() -> None:
    detail = read(DETAIL)
    service = read(SERVICE)
    semantics = read(SEMANTICS)

    assert 'data-kaori-detail-density="adaptive-stacks"' in detail
    assert "detail.detail_card('Protected Data Boundary'" in detail
    assert 'Pod Reference Collection' in detail
    assert 'Pod Reference Evidence Not Reported' in detail
    assert 'Values Not Persisted' in detail
    assert 'does not decode, log, persist, or display value content' in detail
    assert 'total_count=item.key_count' in detail
    assert 'truncated=item.key_entries_truncated' in detail
    assert 'Open ConfigMap Management' in detail
    assert 'Open Secret Management' in detail
    assert 'pod_operational_state(pod.phase, pod.ready)' in service
    assert 'def _pod_state(' not in service
    assert "POD_EVIDENCE_KEY = 'inventory.pods'" in semantics
    assert 'pod_reference_presentation(' in semantics


def test_configuration_collector_and_schema_use_only_canonical_key_index_data() -> None:
    collector = read(COLLECTOR)
    model = read(MODEL)
    persistence = read(PERSISTENCE)
    migration = read(MIGRATION)

    configuration_class = model.split('class ConfigurationInventory', 1)[1].split('class ResourceQuotaInventory', 1)[0]
    assert 'with_evidence: bool = False' in collector
    assert 'base64.b64decode' not in collector
    assert "'key_names': key_names" in collector
    assert "'key_count':" not in collector
    assert "'payload_size_bytes':" not in collector
    assert 'key_count:' not in configuration_class
    assert 'payload_size_bytes:' not in configuration_class
    assert 'inventory.key_count' not in persistence
    assert 'inventory.payload_size_bytes' not in persistence
    assert "revision = '20260805_config_inventory_v2'" in migration
    assert "down_revision = '20260805_ingress_inventory_v2'" in migration
    assert "op.drop_column('configuration_inventory', 'key_count')" in migration
    assert "op.drop_column('configuration_inventory', 'payload_size_bytes')" in migration


def test_configuration_export_declares_protected_metadata_boundary() -> None:
    payload = read(PAYLOAD)
    xlsx = read(XLSX)

    assert "'key_count': len(item.key_names or [])" in payload
    assert "'metadata_boundary': 'Key Names Only'" in payload
    assert "'value_persistence': 'None'" in payload
    assert 'payload_size_bytes' not in payload
    assert 'Metadata Boundary' in xlsx
    assert 'Value Persistence' in xlsx
    assert 'Payload Size (bytes)' not in xlsx

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_service_collector_commits_backend_collection_evidence() -> None:
    collector = read('app/inventory/collectors/services.py')
    persistence = read('app/inventory/persistence.py')

    assert "'inventory.services.backend-registration': endpoint_state" in collector
    assert 'with_evidence: Literal[True]' in collector
    assert "if getattr(exc, 'status', None) in {403, 404}:" in collector
    assert 'except ApiException as exc:' in collector
    assert 'services, collection_evidence = get_services(' in persistence
    assert 'committed_evidence.update(collection_evidence)' in persistence


def test_service_collector_preserves_full_canonical_evidence_without_duplicate_columns() -> None:
    collector = read('app/inventory/collectors/services.py')

    assert 'LEGACY_TEXT_LIMIT' not in collector
    assert "'external_ip':" not in collector
    assert "'ports': _bounded" not in collector
    assert "'external_addresses': external_addresses" in collector
    assert "'load_balancer_ingress': load_balancer_ingress" in collector
    assert "'ports': port_details" in collector
    assert "if metadata is None or spec is None or not metadata.namespace or not metadata.name:" in collector
    assert "('ip', 'hostname', 'node_name', 'target_kind', 'target_name')" in collector
    assert "('name', 'port', 'protocol', 'app_protocol')" in collector


def test_service_backend_semantics_do_not_hide_missing_or_empty_manual_evidence() -> None:
    semantics = read('app/inventory/resources/service_semantics.py')

    assert "if not reported:" in semantics
    assert "'label': 'Not Reported'" in semantics
    assert "if not selector:" in semantics
    assert "'label': 'Manually Managed'" in semantics
    assert "'exception': bool(not_ready or total == 0)" in semantics
    assert "'Headless': 'Direct Pod Discovery'" in semantics


def test_service_page_filters_refresh_complete_committed_scope() -> None:
    routes = read('app/inventory/routes.py')
    workspace = read('app/templates/inventory/services/partials/_page_workspace.html')
    card = read('app/templates/inventory/services/partials/_table_card.html')
    table = read('app/templates/inventory/services/partials/_table_content.html')

    assert "for resource in ('nodes', 'namespaces', 'workloads', 'pods', 'services')" in routes
    assert 'id="services-page-workspace"' in workspace
    assert 'inventory/components/_data_freshness.html' in workspace
    assert 'hx-target="#services-page-workspace"' in card
    assert 'name="partial_mode" value="page_workspace"' in card
    assert 'aria-label="Service inventory filters"' in card
    assert 'hx-target="#services-table-content"' in table
    assert 'name="partial_mode" value="table_content"' in table


def test_service_table_uses_compact_access_and_accessible_structure() -> None:
    table = read('app/templates/inventory/services/partials/_table_content.html')

    assert '<caption class="sr-only">' in table
    assert table.count('scope="col"') == 6
    assert "service.service_type ~ ' · Age '" not in table
    assert 'service.access_supporting' in table
    assert 'resource_detail_modal.detail_button(service.id' in table


def test_service_detail_distinguishes_not_reported_not_configured_and_not_applicable() -> None:
    detail = read('app/templates/inventory/services/partials/_service_detail_content.html')

    for token in (
        'Endpoint Evidence Not Reported',
        'Pod Selection Not Applicable',
        'No Service Selector Configured',
        'No Ports Configured',
        'Not Applicable',
        'Not Reported',
        'Not Configured',
    ):
        assert token in detail
    assert '<caption class="sr-only">Declared port mappings for Service' in detail
    assert detail.count('scope="col"') >= 6
    assert "port.node_port or 'Not Configured'" in detail


def test_service_export_uses_canonical_backend_and_endpoint_fields() -> None:
    payload = read('app/reports/export/payloads/inventory.py')
    standard = read('app/reports/export/xlsx/standard.py')

    assert "registration = service_backend_registration(" in payload
    assert "details.get('load_balancer_ingress')" in payload
    assert "'ready_endpoints': registration['ready'] if endpoint_reported else None" in payload
    assert "'not_ready_endpoints': registration['not_ready'] if endpoint_reported else None" in payload
    for label in (
        'Access Model',
        'Backend Registration',
        'Ready Endpoints',
        'Not-Ready Endpoints',
        'Load Balancer Addresses',
    ):
        assert label in standard

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ROOT / 'app/templates/inventory/workloads/partials/_table_content.html'


def test_workload_table_uses_compact_operational_columns() -> None:
    content = TEMPLATE.read_text(encoding='utf-8')

    for heading in (
        'Workload',
        'Scope',
        'Operational State',
        'Runtime Footprint',
        'Delivery Model',
        'Details',
    ):
        assert f'>{heading}<' in content

    assert '>Update Strategy<' not in content
    assert '>Pods<' not in content
    assert 'resource_detail_modal.detail_button(' in content
    assert 'expandable.detail_row(' not in content


def test_workload_table_separates_posture_from_factual_evidence() -> None:
    content = TEMPLATE.read_text(encoding='utf-8')

    assert 'table_label.status_indicator_label(workload.operational_state_label, workload.operational_state_tone)' in content
    assert '{{ workload.state_display }}' in content
    assert 'table_label.status_label(workload.update_strategy' not in content
    assert '{{ workload.delivery_model }}' in content
    assert '{{ workload.delivery_supporting }}' in content


def test_workload_table_uses_shared_namespaced_scope_and_htmx_pagination() -> None:
    content = TEMPLATE.read_text(encoding='utf-8')

    assert 'table_ui.namespaced_scope_identity(' in content
    assert 'workload.cluster_name' in content
    assert 'workload.namespace' in content
    assert '>Rows<' in content
    assert "endpoint='inventory.workloads'" in content
    assert "hx_target='#workloads-table-content'" in content

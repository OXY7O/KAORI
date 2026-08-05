from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_workload_collector_uses_canonical_operational_posture() -> None:
    source = _read('app/inventory/collectors/workloads.py')

    assert "workload_status = 'Unknown'" in source
    assert "workload_status = 'Stable'" in source
    assert "workload_status = 'Progressing'" in source
    assert "job_status = 'Suspended'" in source
    assert "_deployment_progress_deadline_exceeded(status)" in source
    assert "_condition_is_true(status, 'ReplicaFailure')" in source
    assert 'observed_generation is not None and int(observed_generation) >= int(metadata_generation)' in source
    assert "_condition_is_true(status, 'Failed')" in source
    assert "_condition_is_true(status, 'Complete')" in source
    assert "job_status = 'Running'" not in source


def test_workload_collector_commits_flat_export_and_condition_evidence() -> None:
    source = _read('app/inventory/collectors/workloads.py')

    for token in (
        "'desired_replicas': desired",
        "'updated_replicas': updated",
        "'available_replicas': available",
        "'unavailable_replicas': unavailable",
        "'update_strategy': strategy_name",
        "'conditions': _condition_rows(status)",
        "'status_reported': status is not None",
    ):
        assert token in source

    payload = _read('app/reports/export/payloads/inventory.py')
    assert "update_strategy = details.get('update_strategy')" in payload
    assert "_optional_integer(details.get('desired_replicas'))" in payload
    assert "_optional_integer(details.get('available_replicas'))" in payload
    assert '_detail_row_value' not in payload
    assert '_detail_integer' not in payload


def test_workload_filters_refresh_complete_workspace_and_use_canonical_state() -> None:
    routes = _read('app/inventory/routes.py')
    table = _read('app/templates/inventory/workloads/partials/_table_card.html')
    workspace = _read('app/templates/inventory/workloads/partials/_page_workspace.html')
    service = _read('app/inventory/resources/workloads.py')

    assert "for resource in ('nodes', 'namespaces', 'configuration', 'workloads', 'pods', 'services', 'ingresses', 'storage')" in routes
    assert 'id="workloads-page-workspace"' in workspace
    assert 'inventory/components/_data_freshness.html' in workspace
    assert 'hx-target="#workloads-page-workspace"' in table
    assert 'name="partial_mode" value="page_workspace"' in table
    assert '>Operational State<' in table
    assert 'All Operational States' in table
    assert "'stable': ('Stable', 'normal')" in service
    assert "if normalized == 'unknown':" in service
    assert '~lowered.in_(_KNOWN_STATUS_VALUES)' in service


def test_workload_detail_distinguishes_missing_template_and_conditions() -> None:
    service = _read('app/inventory/resources/workloads.py')
    template = _read('app/templates/inventory/workloads/partials/_workload_detail_content.html')

    assert "return 'Not Configured' if not_configured else 'Not Reported'" in service
    assert "'placement_evidence_reported': pod_template_reported" in service
    assert "'conditions': conditions" in service
    assert "'title': 'Validate Workload Runtime Evidence'" in service
    assert 'Controller Conditions' in template
    assert 'Controller Conditions Not Reported' in template
    assert 'Placement Evidence Not Reported' in template
    assert 'workload.placement_evidence_reported' in template
    assert 'search=workload.name' in template


def test_workload_table_keeps_age_in_detail_and_update_strategy_in_row() -> None:
    table = _read('app/templates/inventory/workloads/partials/_table_content.html')
    service = _read('app/inventory/resources/workloads.py')

    assert '>Update Strategy<' in table
    assert '{{ workload.update_strategy }}' in table
    assert '{{ workload.age }}' not in table
    assert "'identity_supporting': current_type" in service
    assert "'identity_supporting': f'{current_type} · {format_age" not in service
    assert '<caption class="sr-only">' in table
    assert table.count('scope="col"') == 6

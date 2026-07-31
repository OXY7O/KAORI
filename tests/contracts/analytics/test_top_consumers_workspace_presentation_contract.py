from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_top_consumers_uses_canonical_tabs_and_native_hidden_fallback() -> None:
    section = read('app/templates/analytics/top_consumers/partials/_top_consumers_section.html')

    for tab in ('rankings', 'records', 'recommendations'):
        assert f'data-analytics-tab-panel="{tab}"' in section
        assert f'x-bind:hidden="activeTab !== \'{tab}\'"' in section
    assert 'data-analytics-tabset-id="top-consumers-content"' in section


def test_top_consumers_controls_own_only_snapshot_scope() -> None:
    controls = read('app/templates/analytics/top_consumers/partials/_controls_readiness.html')
    records = read('app/templates/analytics/top_consumers/partials/_consumer_detail_section.html')

    assert 'Cluster' in controls
    assert 'Namespace Snapshot' in controls
    assert '<select name="resource"' not in controls
    assert "record_filter.select_items('resource'" in records
    assert "record_filter.select_items('priority'" in records


def test_top_consumers_identity_and_pressure_are_structured() -> None:
    service = read('app/analytics/top_consumers/service.py')
    results = read('app/templates/analytics/top_consumers/partials/_consumer_detail_results.html')

    assert "'entity_type': 'container'" in service
    assert "'workload_owner': workload_owner" in service
    assert "'request_utilization'" in service
    assert "'limit_utilization'" in service
    assert "'contribution_percent'" in service
    assert "'pressure_percent'" in service
    assert 'card.label.split' not in read('app/templates/analytics/top_consumers/partials/_summary.html')
    assert 'identity.primary' in results
    assert 'Request Utilization' in results
    assert 'Limit Utilization' in results
    assert 'Contribution to Scope' in results
    assert 'blended usage ratio' in results


def test_top_consumers_mixed_resource_sort_is_unit_safe() -> None:
    service = read('app/analytics/top_consumers/service.py')

    assert "{'value': 'priority', 'label': 'Operational Priority'}" in service
    assert "{'value': 'contribution', 'label': 'Contribution to Scope'}" in service
    assert "{'value': 'absolute', 'label': 'Absolute Consumption'}" in service
    assert "if selected_sort == 'absolute' and selected_resource != 'all'" in service
    assert "selected_sort == 'absolute' and selected_resource == 'all'" not in service


def test_top_consumers_evidence_and_progress_semantics_are_canonical() -> None:
    service = read('app/analytics/top_consumers/service.py')
    results = read('app/templates/analytics/top_consumers/partials/_consumer_detail_results.html')
    ranked = read('app/templates/analytics/components/_ranked_evidence_panel.html')

    assert "evidence_state('complete')" in service
    assert "evidence_state('partial')" in service
    assert "evidence_state('unavailable')" in service
    assert "'label': 'Evidence Incomplete'" in service
    assert "fill_classes='h-full rounded-full bg-kaori-primary'" in results
    assert "fill_classes='h-full rounded-full bg-kaori-primary'" in ranked
    assert 'bg-status-critical' not in results
    assert 'bg-status-warning' not in results


def test_top_consumers_records_use_shared_pagination_and_safe_expandables() -> None:
    results = read('app/templates/analytics/top_consumers/partials/_consumer_detail_results.html')
    shared = read('app/templates/analytics/components/_record_pagination.html')

    assert 'analytics/components/_record_pagination.html' in results
    assert "'analytics.top_consumers_table'" in results
    assert "'analytics.top_consumers'" in results
    assert '@kaori:analytics-collapse-details.window="expanded = false"' in results
    assert 'x-bind:hidden="!expanded"' in results
    assert '\n                                 hidden\n                                 x-cloak' in results
    assert 'href_endpoint' in shared
    assert 'partial_endpoint' in shared


def test_top_consumers_design_contract_is_registered() -> None:
    guide = read('docs/design/KAORI_STYLING_GUIDE.md')
    design_readme = read('docs/design/README.md')
    contract = read('docs/design/components/ANALYTICS_TOP_CONSUMERS.md')
    analytics_readme = read('app/analytics/README.md')

    assert 'Analytics Top Consumers Standard' in guide
    assert 'components/ANALYTICS_TOP_CONSUMERS.md' in design_readme
    assert 'Canonical Consumer Identity' in contract
    assert 'Mixed-Resource Sort Contract' in contract
    assert 'Namespace Snapshot Ownership' in contract
    assert 'Top Consumers presentation and snapshot contract' in analytics_readme

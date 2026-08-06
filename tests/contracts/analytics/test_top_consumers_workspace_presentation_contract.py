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
    rows = read('app/analytics/top_consumers/rows.py')
    results = read('app/templates/analytics/top_consumers/partials/_consumer_detail_results.html')

    assert "'entity_type': 'container'" in rows
    assert "'workload_owner': spec.workload_owner" in rows
    assert "'request_utilization'" in rows
    assert "'limit_utilization'" in rows
    assert "'contribution_percent'" in rows
    assert "'pressure_percent'" in rows
    assert 'card.label.split' not in read('app/templates/analytics/top_consumers/partials/_summary.html')
    assert 'identity.primary' in results
    assert 'Request Utilization' in results
    assert 'Limit Utilization' in results
    assert 'Contribution to Scope' in results
    assert 'blended usage ratio' in results


def test_top_consumers_mixed_resource_sort_is_unit_safe() -> None:
    contracts = read('app/analytics/top_consumers/contracts.py')
    presentation = read('app/analytics/top_consumers/presentation.py')

    assert "{'value': 'priority', 'label': 'Operational Priority'}" in contracts
    assert "{'value': 'contribution', 'label': 'Contribution to Scope'}" in contracts
    assert "{'value': 'absolute', 'label': 'Absolute Consumption'}" in contracts
    assert "if selected_sort == 'absolute' and selected_resource != 'all'" in presentation
    assert "selected_sort == 'absolute' and selected_resource == 'all'" not in presentation


def test_top_consumers_evidence_and_progress_semantics_are_canonical() -> None:
    domain = read('app/analytics/top_consumers/domain.py')
    results = read('app/templates/analytics/top_consumers/partials/_consumer_detail_results.html')
    ranked = read('app/templates/analytics/components/_ranked_evidence_panel.html')

    assert "evidence_state('complete' if complete else 'partial')" in domain
    assert "evidence_state('unavailable')" in domain
    assert "'label': 'Limited Evidence'" in domain
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


def test_top_consumers_overview_records_and_summary_follow_inventory_density() -> None:
    section = read('app/templates/analytics/top_consumers/partials/_consumer_detail_section.html')
    results = read('app/templates/analytics/top_consumers/partials/_consumer_detail_results.html')
    summary = read('app/templates/analytics/top_consumers/partials/_summary.html')

    assert 'Consumer Records Overview' in section
    assert 'Consumer Records' in section
    assert section.count('analysis_surface.snapshot_shell_classes()') >= 2
    assert "evidence_list.shell('Consumer Records', embedded=true)" in results
    assert 'embedded=true' in results
    assert 'sm:grid-cols-2 xl:grid-cols-4' in summary
    assert '2xl:grid-cols-4' not in summary
    assert 'truncate text-xs text-content-secondary' in summary
    assert 'Top Consumer Snapshot' in summary
    for category in ('cpu', 'memory', 'pods', 'storage'):
        assert f'data-consumer-category="{{{{ cfg.key }}}}"' in summary
        assert f"'key': '{category}'" in summary
    assert "'accent_classes': 'bg-amber-500 dark:bg-amber-400'" in summary
    assert "'accent_classes': 'bg-cyan-500 dark:bg-cyan-400'" in summary
    assert "'accent_classes': 'bg-kaori-primary'" in summary
    assert "'accent_classes': 'bg-emerald-500 dark:bg-emerald-400'" in summary

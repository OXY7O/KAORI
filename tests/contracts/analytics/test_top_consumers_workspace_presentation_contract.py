from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_top_consumers_uses_canonical_tabs_and_native_hidden_fallback() -> None:
    section = read('app/templates/kubernetes/analytics/top_consumers/partials/_top_consumers_section.html')

    for tab in ('rankings', 'records', 'recommendations'):
        assert f'data-analytics-tab-panel="{tab}"' in section
    assert "analytics_workspace.tabbed(" in section
    assert "'top-consumers-content'," in section
    assert "detached=true" not in section
    assert "analytics_workspace.tabbed(" in section
    assert 'class="{{ analysis_surface.snapshot_shell_classes() }} space-y-5 p-5 sm:p-6"' not in section
    assert section.count('class="space-y-5"') >= 2
    assert "content_tabs.render_buttons('consumer-ranking-resource'" in section
    workspace = read('app/templates/kubernetes/analytics/components/_analysis_workspace.html')
    assert "class=\"{{ 'space-y-5' if detached else analysis_surface.snapshot_shell_classes() }}\"" in workspace
    assert "content_tabs.render_buttons(tabset_id, tabs" in workspace
    assert "data-top-consumers-tabset" in section
    assert "content_tabs.render_buttons('top-consumers-content'" not in section
    assert "content_tabs.render_buttons('consumer-ranking-resource'" in section
    assert 'x-show="activeTab' not in section
    assert 'x-bind:hidden="activeTab' not in section


def test_ranking_resource_tabs_use_one_embedded_evidence_surface() -> None:
    section = read('app/templates/kubernetes/analytics/top_consumers/partials/_top_consumers_section.html')
    ranked = read('app/templates/kubernetes/analytics/components/_ranked_evidence_panel.html')
    rows = read('app/kubernetes/analytics/top_consumers/rows.py')

    assert "('cpu', 'CPU', 'cpu'), ('memory', 'Memory', 'memory-stick'), ('pods', 'Pods', 'boxes'), ('pvc', 'PVC', 'database')" in section
    assert "content_tabs.render_buttons('consumer-ranking-resource'" in section
    assert "data-analytics-update-query=\"false\"" in section
    assert "ranked_evidence.render(selected_panel.value, embedded=true)" in section
    assert 'class="min-w-0"' in section

    assert 'macro render(panel, embedded=false)' in ranked
    assert "data-kaori-consumer-ranking=" in ranked
    assert "Selected-Scope Total" in ranked
    assert "panel.capacity_label" in ranked
    for heading in ('Consumer Identity', 'Consumption', 'Contribution to Scope', 'Status / Configuration', 'Pressure'):
        assert heading in ranked
    assert 'row.request_state.label' in ranked
    assert 'row.limit_state.label' in ranked
    assert 'row.denominator_evidence_available' in ranked
    assert 'row.risk.label' in ranked
    assert 'row.pressure_basis' in ranked
    assert 'title="{{ row.identity.primary }}"' in ranked
    assert "fill_classes='h-full rounded-full bg-kaori-primary'" in ranked
    assert "progress_bar.semantic_bar" not in ranked
    assert "'contribution_percent': rounded_percent(contribution)" in rows


def test_small_cpu_formatting_does_not_round_nonzero_evidence_to_zero() -> None:
    rows = read('app/kubernetes/analytics/top_consumers/rows.py')
    assert "if 0 < abs(value) < 0.01:" in rows
    assert "return f'{value:.3g} cores'" in rows
    assert "return f'{safe_round(value, 2)} cores'" in rows


def test_top_consumers_controls_own_only_snapshot_scope() -> None:
    controls = read('app/templates/kubernetes/analytics/top_consumers/partials/_controls_readiness.html')
    records = read('app/templates/kubernetes/analytics/top_consumers/partials/_consumer_detail_section.html')

    assert 'Cluster' in controls
    assert 'Namespace Snapshot' in controls
    assert '<select name="resource"' not in controls
    assert "record_filter.select_items('resource'" in records
    assert "record_filter.select_items('priority'" in records


def test_top_consumers_identity_and_pressure_are_structured() -> None:
    rows = read('app/kubernetes/analytics/top_consumers/rows.py')
    results = read('app/templates/kubernetes/analytics/top_consumers/partials/_consumer_detail_results.html')

    assert "'entity_type': 'container'" in rows
    assert "'workload_owner': spec.workload_owner" in rows
    assert "'request_utilization'" in rows
    assert "'limit_utilization'" in rows
    assert "'contribution_percent'" in rows
    assert "'pressure_percent'" in rows
    assert 'card.label.split' not in read('app/templates/kubernetes/analytics/top_consumers/partials/_summary.html')
    assert 'identity.primary' in results
    assert 'Request Utilization' in results
    assert 'Limit Utilization' in results
    assert 'Contribution to Scope' in results
    assert 'blended usage ratio' in results


def test_top_consumers_mixed_resource_sort_is_unit_safe() -> None:
    contracts = read('app/kubernetes/analytics/top_consumers/contracts.py')
    presentation = read('app/kubernetes/analytics/top_consumers/presentation.py')

    assert "{'value': 'priority', 'label': 'Operational Priority'}" in contracts
    assert "{'value': 'contribution', 'label': 'Contribution to Scope'}" in contracts
    assert "{'value': 'absolute', 'label': 'Absolute Consumption'}" in contracts
    assert "if selected_sort == 'absolute' and selected_resource != 'all'" in presentation
    assert "selected_sort == 'absolute' and selected_resource == 'all'" not in presentation


def test_top_consumers_evidence_and_progress_semantics_are_canonical() -> None:
    domain = read('app/kubernetes/analytics/top_consumers/domain.py')
    results = read('app/templates/kubernetes/analytics/top_consumers/partials/_consumer_detail_results.html')
    ranked = read('app/templates/kubernetes/analytics/components/_ranked_evidence_panel.html')

    assert "evidence_state('complete' if complete else 'partial')" in domain
    assert "evidence_state('unavailable')" in domain
    assert "'label': 'Limited Evidence'" in domain
    assert "fill_classes='h-full rounded-full bg-kaori-primary'" in results
    assert "fill_classes='h-full rounded-full bg-kaori-primary'" in ranked
    assert 'progress_bar.semantic_bar' not in results
    assert 'progress_bar.semantic_bar' not in ranked
    assert 'bg-status-critical' not in results
    assert 'bg-status-warning' not in results
    assert 'bg-status-critical' not in ranked
    assert 'bg-status-warning' not in ranked


def test_top_consumers_records_use_shared_pagination_and_modal_details() -> None:
    results = read('app/templates/kubernetes/analytics/top_consumers/partials/_consumer_detail_results.html')
    shared = read('app/templates/analytics/components/_record_pagination.html')

    assert 'analytics/components/_record_pagination.html' in results
    assert 'kubernetes/analytics/components/_record_detail_modal.html' in results
    assert "'analytics.top_consumers_table'" in results
    assert "'analytics.top_consumers'" in results
    assert '@kaori:analytics-collapse-details.window="detailOpen = false"' in results
    assert 'record_detail_modal.render(' in results
    assert 'aria-haspopup="dialog"' in results
    assert '<span>View Details</span>' in results
    assert 'panel-top-open' in results
    assert 'expanded = false' not in results
    assert 'x-bind:hidden="!expanded"' not in results
    assert 'View More' not in results
    assert 'Hide Details' not in results
    assert 'chevron-down' not in results
    assert 'href_endpoint' in shared
    assert 'partial_endpoint' in shared


def test_top_consumers_design_contract_is_registered() -> None:
    guide = read('docs/design/KAORI_STYLING_GUIDE.md')
    design_readme = read('docs/design/README.md')
    contract = read('docs/design/components/ANALYTICS_TOP_CONSUMERS.md')
    analytics_readme = read('app/kubernetes/analytics/README.md')

    assert 'Analytics Top Consumers Standard' in guide
    assert 'components/ANALYTICS_TOP_CONSUMERS.md' in design_readme
    assert 'Canonical Consumer Identity' in contract
    assert 'Mixed-Resource Sort Contract' in contract
    assert 'Namespace Snapshot Ownership' in contract
    assert 'Top Consumers presentation and snapshot contract' in analytics_readme


def test_top_consumers_overview_records_and_summary_follow_inventory_density() -> None:
    section = read('app/templates/kubernetes/analytics/top_consumers/partials/_consumer_detail_section.html')
    results = read('app/templates/kubernetes/analytics/top_consumers/partials/_consumer_detail_results.html')
    summary = read('app/templates/kubernetes/analytics/top_consumers/partials/_summary.html')

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
        assert 'data-consumer-category="{{ cfg.key }}"' in summary
        assert f"'key': '{category}'" in summary
    assert 'accent_classes' not in summary
    assert 'bg-amber-500' not in summary
    assert 'bg-cyan-500' not in summary
    assert 'bg-emerald-500' not in summary
    assert 'h-1.5 w-full' not in summary
    assert 'border border-outline-default bg-surface-card p-4 shadow-sm' in summary
    assert 'border-outline-subtle bg-surface-hover text-kaori-primary' in summary
    assert 'inline-flex min-h-6' not in summary
    assert 'table_label.status_indicator_label' in summary

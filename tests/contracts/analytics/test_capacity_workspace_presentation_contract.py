from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_capacity_removes_nonfunctional_composite_tracker_and_dead_chart_runtime() -> None:
    index = read('app/templates/analytics/capacity/index.html')

    assert 'capacity-load-tracker' not in index
    assert 'analytics/partials/_load_tracker.html' not in index
    assert 'chart.umd.min.js' not in index
    assert 'analytics_capacity.js' not in index
    assert not (ROOT / 'app/static/js/analytics_capacity.js').exists()


def test_capacity_uses_shared_surface_and_control_contracts() -> None:
    controls = read('app/templates/analytics/capacity/partials/_controls_readiness.html')
    overview = read('app/templates/analytics/capacity/partials/_overview.html')
    allocation = read('app/templates/analytics/capacity/partials/_allocation.html')
    worker = read('app/templates/analytics/capacity/partials/_worker_summary.html')

    assert 'analytics_workspace.control_select_classes()' in controls
    assert 'analytics_workspace.control_label_classes()' in controls
    assert 'data-analytics-preserve-tab' in controls
    assert 'analysis_surface.evidence_shell_classes()' in overview
    assert 'analysis_surface.metric_grid_classes(4)' in overview
    assert 'resource_pressure_lane.render(' in allocation
    assert 'analysis_surface.interpretation_grid_classes(' in allocation
    assert 'Worker Fleet Baseline' in worker
    assert 'bg-surface-hover' not in worker.split('<section', 1)[1].split('</section>', 1)[0]


def test_capacity_unavailable_state_is_unknown_na_and_suppresses_progress() -> None:
    presenter = read('app/analytics/capacity/presentation.py')
    domain = read('app/analytics/capacity/domain.py')
    lane = read('app/templates/analytics/components/_resource_pressure_lane.html')
    overview = read('app/templates/analytics/capacity/partials/_overview.html')
    contract = read('docs/design/components/ANALYTICS_CAPACITY_ANALYSIS.md')

    assert "'utilization_percent': utilization" in presenter
    assert "'headroom': normalized_headroom" in presenter
    assert "'capacity': converter(capacity.value) if capacity_available else None" in domain
    assert "if resolved_available" in lane
    assert 'Capacity evidence unavailable' in lane
    assert 'No committed capacity evidence' in overview
    assert 'Missing capacity evidence is not zero utilization' in contract


def test_capacity_semantic_status_is_owned_by_domain_not_css_or_jinja() -> None:
    domain = read('app/analytics/capacity/domain.py')
    service = read('app/analytics/capacity/service.py')
    payloads = read('app/analytics/common/payloads.py')
    allocation = read('app/templates/analytics/capacity/partials/_allocation.html')
    risk = read('app/templates/analytics/capacity/partials/_risk.html')

    for tone in ("'critical'", "'warning'", "'normal'", "'unknown'"):
        assert tone in domain
    assert "'class': 'bg-" not in domain
    assert "'icon_class':" not in domain
    assert 'bar_class' not in domain
    assert 'include_presentation_classes=False' in service
    capacity_payload = payloads.split('def get_empty_capacity_payload', 1)[1].split(
        'def get_empty_storage_payload', 1
    )[0]
    assert "'class': 'bg-" not in capacity_payload
    assert "'icon_class':" not in capacity_payload
    assert "'tone': 'unknown'" in capacity_payload
    assert "section_status['tone']" in allocation
    assert "allocation_item['available']" in allocation
    assert 'item.status.tone' in risk
    assert "'critical' in item.status.class" not in risk


def test_capacity_progress_remains_violet_and_primary_evidence_is_bright() -> None:
    overview = read('app/templates/analytics/capacity/partials/_overview.html')
    allocation = read('app/templates/analytics/capacity/partials/_allocation.html')
    risk = read('app/templates/analytics/capacity/partials/_risk.html')
    contract = read('docs/design/components/ANALYTICS_CAPACITY_ANALYSIS.md')

    for source in (overview, allocation, risk):
        assert 'bg-kaori-primary' in source
        assert 'bg-red-' not in source
        assert 'bg-amber-' not in source
        assert 'bg-emerald-' not in source
    assert 'progress bars remain KAORI Violet' in contract


def test_capacity_separates_findings_from_review_navigation_and_storage_actions() -> None:
    domain = read('app/analytics/capacity/domain.py')
    service = read('app/analytics/capacity/service.py')
    risk = read('app/templates/analytics/capacity/partials/_risk.html')

    governance_function = domain.split('def build_governance_findings', 1)[1]
    assert "for resource in ('cpu', 'memory', 'pods')" in governance_function
    assert 'Open Workload Analysis' not in governance_function
    assert 'Open Storage Analysis' not in governance_function
    assert "'review_paths': get_capacity_review_paths()" in service
    assert 'Governance Findings' in risk
    assert 'Recommended Review Path' in risk
    assert 'Continue in Storage Analysis' in risk
    assert 'analysis_surface.guidance_card_classes()' in risk


def test_capacity_is_cluster_level_and_recommendations_deep_link_to_tabs() -> None:
    routes = read('app/analytics/capacity/routes.py')
    index = read('app/templates/analytics/capacity/index.html')
    recommendations = read('app/templates/analytics/capacity/partials/_recommendations.html')
    contract = read('docs/design/components/ANALYTICS_CAPACITY_ANALYSIS.md')

    assert "_ALLOWED_TABS = {'summary', 'allocation', 'risk', 'recommendations'}" in routes
    assert "context['initial_tab'] = _initial_tab()" in routes
    assert "parameters.pop('tab', None)" in routes
    assert "initial_tab|default('summary')" in index
    assert "tab=item.target_tab|default('summary')" in recommendations
    assert 'does not expose a node selector' in contract
    assert 'node-level pressure belongs to Resource Utilization' in contract


def test_capacity_templates_remove_local_micro_typography_debt() -> None:
    paths = [
        'app/templates/analytics/capacity/partials/_hero.html',
        'app/templates/analytics/capacity/partials/_overview.html',
        'app/templates/analytics/capacity/partials/_worker_summary.html',
        'app/templates/analytics/capacity/partials/_allocation.html',
        'app/templates/analytics/capacity/partials/_risk.html',
        'app/templates/analytics/capacity/partials/_recommendations.html',
    ]
    for path in paths:
        source = read(path)
        assert 'text-[10px]' not in source, path
        assert 'tracking-[' not in source, path

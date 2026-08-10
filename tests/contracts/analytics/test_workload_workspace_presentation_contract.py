from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WORKLOAD_TEMPLATES = ROOT / 'app/templates/analytics/workload'


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_workload_workspace_uses_local_loading_ownership_and_lazy_mapping() -> None:
    index = read('app/templates/analytics/workload/index.html')

    assert 'workload-load-tracker' not in index
    assert 'analytics/partials/_load_tracker.html' not in index
    assert 'kaori:analytics-tab-activated once' in index
    assert 'workload-mapping-lazy-indicator' in index
    assert 'hx-swap="outerHTML"' in index
    assert 'Workload Resource Mapping' in index


def test_workload_hero_uses_canonical_context_card() -> None:
    hero = read('app/templates/analytics/workload/partials/_hero.html')

    assert 'page_hero.context_card(' in hero
    assert "('shield-alert', 'Findings'" in hero
    assert "('calendar-range', 'Time Range'" in hero
    assert "'Manage Clusters'" in hero
    assert 'context_posture_header' not in hero
    assert 'context_posture_note' not in hero
    assert 'context_bottom_notice' not in hero


def test_workload_mapping_uses_extended_filters_closed_by_default() -> None:
    component = read('app/templates/analytics/components/_record_filter_bar.html')
    mapping = read('app/templates/analytics/workload/partials/_workload_mapping_section.html')

    assert 'macro extended_form' in component
    assert 'macro advanced_toggle' in component
    assert 'macro advanced_grid' in component
    assert 'x-data="{ advancedOpen:' in component
    assert 'x-show="advancedOpen"' in component
    assert 'Advanced Filters' in component
    assert 'record_filter.extended_form' in mapping
    assert 'record_filter.primary_grid' in mapping
    assert 'record_filter.advanced_toggle' in mapping
    assert 'record_filter.advanced_grid' in mapping
    assert 'Resource Configuration' in mapping
    assert 'QoS' in mapping
    assert 'record_filter.reset_link' in mapping


def test_workload_sections_use_inventory_aligned_overview_and_record_cards() -> None:
    page = read('app/templates/analytics/workload/index.html')
    for relative in (
        'app/templates/analytics/workload/partials/_overview.html',
        'app/templates/analytics/workload/partials/_tenant_quota_section.html',
        'app/templates/analytics/workload/partials/_workload_mapping_section.html',
    ):
        source = read(relative)
        assert 'analytics/components/_analysis_surfaces.html' in source
        assert (
            'analysis_surface.snapshot_shell_classes' in source or 'analysis_surface.evidence_shell_classes' in source
        )
        assert 'text-[' not in source
        assert 'tracking-[' not in source

    tenant = read('app/templates/analytics/workload/partials/_tenant_quota_section.html')
    mapping = read('app/templates/analytics/workload/partials/_workload_mapping_section.html')
    assert 'analytics/components/_evidence_record_list.html' in tenant
    assert 'analytics/components/_record_filter_bar.html' in tenant
    assert 'analytics/components/_evidence_record_list.html' in mapping
    assert 'analytics/components/_record_filter_bar.html' in mapping
    assert tenant.count('analysis_surface.snapshot_shell_classes') >= 1
    assert mapping.count('analysis_surface.snapshot_shell_classes') >= 1
    assert 'border-b border-outline-subtle pb-5' in tenant
    assert 'border-b border-outline-subtle pb-5' in mapping
    assert 'analysis_surface.evidence_shell_classes()' in tenant
    assert 'analysis_surface.evidence_shell_classes()' in mapping
    assert "evidence_list.shell('Tenant Quota Records', embedded=true)" in tenant
    assert "evidence_list.shell('Workload Resource Mapping Records', embedded=true)" in mapping
    assert 'embedded=true' in tenant
    assert 'embedded=true' in mapping
    assert 'Runtime Demand Interpretation' in tenant
    assert 'Request Fit Interpretation' in mapping
    assert 'Demand basis in View More' in tenant
    assert 'Interpretation in View More' in mapping
    assert (
        '{{ row.recommendation }}</p>'
        not in tenant.split("evidence_list.mobile_label('Risk')", 1)[1].split("evidence_list.cell(2, 'right')", 1)[0]
    )
    assert (
        '{{ row.metrics_coverage.description }}</p>'
        not in mapping.split("evidence_list.mobile_label('Evidence & QoS')", 1)[1].split(
            "evidence_list.cell(2, 'right')", 1
        )[0]
    )
    assert 'card=true' in tenant
    assert 'card=true' in mapping
    assert 'record_detail_modal.render' in tenant
    assert 'record_detail_modal.render' in mapping
    assert 'detached=true' not in page
    assert "['quotas', 'mapping', 'recommendations']" in page

    recommendations = read('app/templates/analytics/workload/partials/_recommendations.html')
    assert 'analysis_surface.evidence_shell_classes()' in recommendations
    assert 'analysis_surface.snapshot_shell_classes()' not in recommendations
    assert 'analysis_surface.snapshot_header_classes()' not in recommendations
    assert 'bg-surface-card px-4 py-4 sm:px-5' in recommendations
    assert 'overflow-hidden rounded-lg border border-outline-subtle' not in recommendations


def test_workload_workspace_matches_storage_integrated_tabbed_composition() -> None:
    workload = read('app/templates/analytics/workload/index.html')
    storage = read('app/templates/analytics/storage/partials/_storage_section.html')

    assert 'analytics_workspace.tabbed(' in workload
    assert 'analytics_workspace.tabbed(' in storage
    assert 'detached=true' not in workload
    assert "'Workload Analysis Workspace'" in workload
    assert "'Storage Analysis Workspace'" in storage
    assert "['quotas', 'mapping', 'recommendations']" in workload


def test_workload_summary_is_top_level_scope_owned() -> None:
    service = read('app/analytics/workload/presentation.py')
    pagination = read('app/templates/analytics/components/_record_pagination.html')
    tenant = read('app/templates/analytics/workload/partials/_tenant_quota_section.html')
    mapping = read('app/templates/analytics/workload/partials/_workload_mapping_section.html')

    assert 'tenant_summary = {' in service
    assert '**build_tenant_scope_summary(tenant_scope_rows)' in service
    assert 'workload_scope_summary = build_workload_scope_summary(workload_scope_rows)' in service
    assert 'tenant_filtered = filter_tenant_quota_rows(' in service
    assert 'workload_filtered = filter_workload_rows(' in service
    assert 'Showing' in pagination
    assert 'Rows Per Page' in pagination
    assert "'Mapped Workloads'" in mapping
    assert "'Namespaces'" in tenant


def test_workload_public_contract_removes_retired_aliases() -> None:
    files = [
        read('app/analytics/workload/service.py'),
        read('app/analytics/common/payloads.py'),
        read('app/templates/analytics/components/_record_pagination.html'),
    ]
    retired = (
        'selected_workload_resource_status',
        'resource_status_options',
        'workload_resource_status',
        'efficiency_display',
        'missing_cpu_limits',
        'missing_memory_limits',
    )
    for source in files:
        for token in retired:
            assert token not in source


def test_workload_design_contract_is_registered() -> None:
    guide = read('docs/design/KAORI_STYLING_GUIDE.md')
    design_readme = read('docs/design/README.md')
    contract = read('docs/design/components/ANALYTICS_WORKLOAD_ANALYSIS.md')
    analytics_readme = read('app/analytics/README.md')

    assert 'Analytics Workload Analysis Standard' in guide
    assert 'components/ANALYTICS_WORKLOAD_ANALYSIS.md' in guide
    assert 'components/ANALYTICS_WORKLOAD_ANALYSIS.md' in design_readme
    assert 'Analytics Evidence Coverage' in contract
    assert 'CPU Limit Unset' in contract
    assert 'Selected-Window Pod Peak Sum' in contract
    assert 'Workload Analysis presentation contract' in analytics_readme

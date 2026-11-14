"""Keep focused Tenant drift workflows at the primary Operations tab level."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PARTIALS = ROOT / 'app/templates/kubernetes/tenant/partials'


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_drift_workflows_keep_five_primary_tabs_and_use_server_owned_child_views() -> None:
    operations = read('app/templates/kubernetes/tenant/operations.html')
    routes = read('app/kubernetes/tenant/routes.py')
    tab_helper = read('app/kubernetes/tenant/route_common.py')

    for key, label in (
        ('allocation-drift', 'Allocation Drift'),
        ('operational-reconcile', 'Operational Reconcile'),
    ):
        assert f"('{key}', '{label}'" in operations
        assert f"url_for('tenant.operations', tab='{key}')" in operations
        assert f"active_tab == '{key}'" in operations or f"active_tab in {{'{key}'" in routes
        assert f"'{key}'" in tab_helper

    assert operations.count('content_tabs.render_links(') == 1
    assert "'tenant-operations'" in operations
    assert operations.count('workspace_tabs.render_query_tabs(') == 2
    assert 'components/workspace_tabs.html' in operations
    assert operations.count("hx_target='#tenant-operations-workspace'") == 3
    assert operations.count('hx-select="#tenant-operations-workspace"') == 2
    assert operations.count("hx_sync='#tenant-operations-workspace:replace'") == 2
    assert "hx_push_url='true'" in operations
    # Keep the same attached tab/header/table surface as Membership Registry.
    membership = read('app/templates/kubernetes/tenant/partials/_tenant_memberships_workspace.html')
    assert 'workspace_tabs.render_query_tabs(' in membership
    assert 'min-w-0 overflow-hidden rounded-2xl border border-outline-default' in membership
    assert 'hx-select="#tenant-admin-workspace"' in membership
    assert "'tenant-drift-views'" not in operations
    assert 'data-tenant-drift-view' not in operations
    assert 'drift_view=drift_view' not in routes
    assert "active_tab in {'allocation-drift', 'operational-reconcile'}" in routes
    assert 'active_view = _operations_active_view(active_tab)' in routes
    assert 'active_view=active_view' in routes


def test_operations_titles_follow_shared_indicator_and_guide_contract() -> None:
    from jinja2 import Environment

    operations = read('app/templates/kubernetes/tenant/operations.html')
    registry = read('app/templates/kubernetes/tenant/partials/_operations_namespace_registry.html')
    for source in (operations, registry):
        Environment(autoescape=True).parse(source)

    assert "table_label.metadata_label((operations_metrics|length) ~ ' Indicators', icon='layout-grid')" in operations
    assert "resource_posture_grid.render(operations_metrics, columns=4)" in operations
    assert "info_tip.render('tenant-operational-control-guide'" in operations
    assert operations.count("'tenant-operational-control-guide'") == 1
    assert "placement='right', variant='guide'" in operations
    assert operations.index("'tenant-operational-control-guide'") < operations.index(
        "id='tenant-operations-workspace'"
    )
    assert "id='tenant-operations-workspace'" in operations
    assert "content_tabs.render_links('tenant-operations'" in operations

    assert "info_tip.render('tenant-operations-namespace-registry-guide'" in registry
    assert registry.count("'tenant-operations-namespace-registry-guide'") == 1
    assert "title_extra=title_info" in registry
    assert "result_count=operations_namespace_pagination.total_items" in registry
    assert "header_actions=header_actions" in registry
    assert "Provision Namespace" in registry
    assert "registry_ui.filter_form(" in registry
    assert "registry_ui.footer('tenant.operations'" in registry


def test_operations_evidence_and_drift_guides_keep_results_filters_and_ownership() -> None:
    from jinja2 import Environment

    for name, guide_id, total, tab in (
        (
            '_operations_evidence_registry.html',
            'tenant-operations-evidence-registry-guide',
            'operations_evidence_pagination.total_items',
            'runs-evidence',
        ),
        (
            '_operations_drift_registry.html',
            'tenant-operations-drift-registry-guide',
            'operations_drift_pagination.total_items',
            'operational-reconcile',
        ),
    ):
        source = (PARTIALS / name).read_text(encoding='utf-8')
        Environment(autoescape=True).parse(source)
        assert source.count(f"'{guide_id}'") == 1
        assert "variant='guide'" in source
        assert 'title_extra=title_info' in source
        assert f'result_count={total}' in source
        assert 'header_actions=header_actions' in source
        assert 'registry_ui.filter_form(' in source
        assert "registry_ui.footer('tenant.operations'" in source
        assert f"'tab': '{tab}'" in source
        assert f'name="tab" value="{tab}"' in source
        assert 'operations-' in source

    evidence = read('app/templates/kubernetes/tenant/partials/_operations_evidence_registry.html')
    drift = read('app/templates/kubernetes/tenant/partials/_operations_drift_registry.html')
    assert "operations_evidence_filters.evidence_type" in evidence
    assert "operations_evidence_pagination.allowed_per_page" in evidence
    assert "operations_drift_pagination.allowed_per_page" in drift
    assert "url_for('tenant." in drift
    assert 'explicit recovery decision' in drift


def test_activity_directory_uses_three_canonical_link_rows_not_nested_cards() -> None:
    from jinja2 import Environment

    page = read('app/templates/kubernetes/tenant/operations.html')
    Environment(autoescape=True).parse(page)
    assert 'data-tenant-activity-destinations' in page
    activity = page.split('data-tenant-activity-destinations', 1)[1].split(
        '                {% endif %}', 1
    )[0]

    assert 'Canonical Workspaces</h3>' in activity
    assert "table_label.metadata_label('3 Destinations', icon='layout-grid')" in activity
    assert activity.count('class="{{ table_ui.block_icon_classes() }}"') == 3
    assert activity.count('<li class="border-b border-outline-subtle last:border-b-0">') == 3
    assert activity.count('class="group flex min-w-0 items-center justify-between') == 3
    assert activity.count('focus-visible:ring-inset focus-visible:ring-outline-focus') == 3
    assert activity.count('Open Workspace') == 3
    assert activity.count('table_label.metadata_label(') == 4
    assert activity.count('aria-label="Open ') == 3
    assert activity.count('<section') == 0
    assert 'lg:grid-cols-3' not in activity
    assert 'mt-auto border-t' not in activity
    assert "action_button.classes('soft')" not in activity

    for title, detail, route in (
        (
            'Activity Audit',
            'Trace Tenant mutations and their outcomes in the canonical audit history.',
            "url_for('access.activity_audit.index')",
        ),
        (
            'Intelligence',
            'Review operational findings and recommendations in KAORI Intelligence.',
            "url_for('intelligence.recommendations')",
        ),
        (
            'Reports',
            'Build and review published evidence through the canonical Reports workflow.',
            "url_for('reports.generate_report')",
        ),
    ):
        assert title in activity
        assert detail in activity
        assert activity.count(route) == 1

    assert 'hx-post' not in activity
    assert 'hx-delete' not in activity


def test_existing_drift_urls_still_map_to_primary_tabs() -> None:
    route_common = read('app/kubernetes/tenant/route_common.py')
    assert "if active_tab == 'drift-reconcile':" in route_common
    assert "request.args.get('drift_view') == 'operations'" in route_common
    assert "return 'operational-reconcile' if" in route_common
    assert "else 'allocation-drift'" in route_common


def test_drift_sections_have_context_before_child_tabs_and_one_active_registry() -> None:
    from jinja2 import Environment

    operations = read('app/templates/kubernetes/tenant/operations.html')
    Environment(autoescape=True).parse(operations)
    allocation = operations.split("{% elif active_tab == 'allocation-drift' %}", 1)[1].split(
        "{% elif active_tab == 'operational-reconcile' %}", 1
    )[0]
    operational = operations.split("{% elif active_tab == 'operational-reconcile' %}", 1)[1].split(
        '{% else %}\n                    <section', 1
    )[0]

    for source, section, expected_count in (
        (allocation, 'allocation', 2),
        (operational, 'operations', 3),
    ):
        assert 'data-tenant-operations-review-intro' in source
        assert source.index('data-tenant-operations-review-intro') < source.index(
            f'id="tenant-drift-{section}-registry"'
        )
        assert source.index(f'id="tenant-drift-{section}-registry"') < source.index(
            'workspace_tabs.render_query_tabs('
        )
        assert source.index('workspace_tabs.render_query_tabs(') < source.index(
            '{% include "kubernetes/tenant/partials/'
        )
        assert source.count('{% include "kubernetes/tenant/partials/') == expected_count
        assert source.count(
            'class="min-w-0 overflow-hidden rounded-2xl border border-outline-default '
            'bg-surface-card shadow-sm"'
        ) == 1
        assert source.count('class="min-w-0 p-4 sm:p-5"') == 1
        assert 'hx-select="#tenant-operations-workspace"' in source
        assert "hx_sync='#tenant-operations-workspace:replace'" in source
        assert 'active_view,' in source
        assert 'workspace_tabs.render_navigation(' not in source
        assert 'sm:grid-cols-' not in source
        # The introductory copy is not its own large nested card.
        assert 'data-capsule-allocation-scope-guide' in source if section == 'allocation' else True

    assert "ops_view='tenant-quota'" in allocation
    assert "ops_view='shared-allocation'" in allocation
    assert "active_view == 'shared-allocation'" in allocation
    assert '_capsule_tenant_quota_drift.html' in allocation
    assert '_capsule_shared_allocation_drift.html' in allocation
    assert "ops_view='namespace-drift'" in operational
    assert "ops_view='access-reconciliation'" in operational
    assert "ops_view='provider-authority'" in operational
    assert "active_view == 'access-reconciliation'" in operational
    assert "active_view == 'provider-authority'" in operational
    assert '_operations_drift_registry.html' in operational
    assert '_operations_access_reconciliation_registry.html' in operational
    assert '_operations_provider_registry.html' in operational
    assert 'data-tenant-provider-authority-disclosure' not in operational
    assert '{% set provider_authority_embedded = true %}' not in operational
    assert 'read-only ownership context, not a drift finding' in operational


def test_integrated_child_registry_tab_shell_matches_membership_reference() -> None:
    from jinja2 import Environment

    operations = read('app/templates/kubernetes/tenant/operations.html')
    membership = read('app/templates/kubernetes/tenant/partials/_tenant_memberships_workspace.html')
    tabs = read('app/templates/components/workspace_tabs.html')
    for source in (operations, membership, tabs):
        Environment(autoescape=True).parse(source)
    for source in (operations, membership):
        assert 'workspace_tabs.render_query_tabs(' in source
        assert 'hx-select="#tenant-' in source
        assert 'min-w-0 overflow-hidden rounded-2xl border border-outline-default' in source
    assert 'data-kaori-tab-variant="query-backed-htmx"' in tabs
    assert 'rounded-t-xl border px-4 py-2.5' in tabs
    assert 'workspace_tabs.render_navigation(' not in operations
    assert operations.count('workspace_tabs.render_query_tabs(') == 2
    assert operations.count('class="min-w-0 p-4 sm:p-5"') == 2
    assert operations.count('data-tenant-operations-review-intro') == 2
    assert operations.count('data-capsule-allocation-scope-guide') == 1


def test_each_registry_retains_child_view_during_filter_clear_and_pagination() -> None:
    specs = (
        ('_capsule_tenant_quota_drift.html', 'allocation-drift', 'tenant-quota'),
        ('_capsule_shared_allocation_drift.html', 'allocation-drift', 'shared-allocation'),
        ('_operations_drift_registry.html', 'operational-reconcile', 'namespace-drift'),
        ('_operations_access_reconciliation_registry.html', 'operational-reconcile', 'access-reconciliation'),
        ('_operations_provider_registry.html', 'operational-reconcile', 'provider-authority'),
    )
    for name, tab, view in specs:
        source = (PARTIALS / name).read_text(encoding='utf-8')
        assert f"'tab': '{tab}'" in source, name
        assert f"'ops_view': '{view}'" in source, name
        assert f'name="tab" value="{tab}"' in source
        assert f'name="ops_view" value="{view}"' in source
        assert f"query_params={{'tab': '{tab}', 'ops_view': '{view}'}}" in source
        assert 'registry_ui.clear_filters_link(' in source
        assert 'registry_ui.footer(' in source
        assert '.total_items > 0' not in source, name
        assert "'drift_view':" not in source, name

    common = read('app/kubernetes/tenant/route_common.py')
    assert "def _operations_active_view(active_tab: str)" in common
    assert "requested = str(request.args.get('ops_view') or '').strip()" in common
    for view in ('tenant-quota', 'shared-allocation', 'namespace-drift', 'access-reconciliation', 'provider-authority'):
        assert f"'{view}'" in common
    assert "'ops_capsule_shared_page'" in common
    assert "'ops_access_page'" in common
    assert "'ops_provider_page'" in common
    assert "return 'tenant-quota'" in common
    assert "return 'namespace-drift'" in common


def test_both_capsule_drift_registries_use_full_kaori_table_contract() -> None:
    """#2931: canonical header/filter/columns/detail/empty/footer for both Capsule authorities."""
    from jinja2 import Environment

    specs = (
        (
            '_capsule_tenant_quota_drift.html',
            'capsule-tenant-quota-drift',
            'capsule_tenant_quota_drifted',
            'capsule_tenant_quota_filters',
            'ops_capsule_tenant_quota',
            'tenant.reapply_capsule_tenant_quota_route',
            'tenant.accept_capsule_tenant_provider_state_route',
        ),
        (
            '_capsule_shared_allocation_drift.html',
            'capsule-shared-allocation-drift',
            'capsule_shared_drift_intents',
            'capsule_shared_drift_filters',
            'ops_capsule_shared',
            'tenant.reapply_capsule_shared_allocation_route',
            'tenant.accept_capsule_shared_provider_allocation_route',
        ),
    )
    for filename, registry_id, rows, filters, query_key, reapply, accept in specs:
        source = read('app/templates/kubernetes/tenant/partials/' + filename)
        Environment().parse(source)
        assert 'components/table.html' in source
        assert 'components/table_registry.html' in source
        assert 'table_ui.inventory_block_header(' in source
        assert 'result_count=' in source
        assert 'header_actions=header_actions' in source
        assert 'registry_ui.clear_filters_link(' in source
        assert 'registry_ui.filter_form(' in source
        assert "aria_label='Filter " in source
        assert 'table_ui.inventory_filter_bar_classes()' in source
        assert 'table_ui.filter_select_classes()' in source
        assert 'table_ui.search_field(' in source
        assert query_key + '_tenant_id' in source
        assert query_key + '_search' in source
        assert filters + '.tenant_id' in source
        assert filters + '.search' in source
        assert 'name="tab" value="allocation-drift"' in source
        assert "min-w-[840px] !table-fixed' if " + rows + " else '!table-fixed'" in source
        assert 'min-w-[1450px]' not in source
        for header in ('Tenant', 'Provider / Authority', 'Status', 'Allocation Difference', 'Details'):
            assert '>' + header + '</th>' in source
        assert 'colspan="5"' in source
        assert "table_label.status_label('Drifted', 'warning')" in source
        assert 'first.kaori_value' in source and 'first.provider_value' in source
        assert 'data-kaori-native-dialog' in source
        assert 'data-kaori-dialog-open' in source
        assert 'data-dialog-target="{{ dialog_id }}"' in source
        assert 'aria-haspopup="dialog"' in source
        assert 'data-kaori-dialog-close' in source
        assert 'View More' in source
        assert 'Provider Evidence' in source
        assert 'Reconciliation Decision' in source
        assert 'difference.kaori_value' in source
        assert 'difference.provider_value' in source
        assert 'source.get("uid")' in source
        assert 'source.get("resource_version")' in source
        assert 'drift.get("observed_at")' in source
        assert 'state.get("blocked_reason")' in source
        assert "table_label.special_label('Control Unavailable'" in source
        assert "can_manage and state.get('reapply_supported') and state.get('accept_supported')" in source
        assert source.count('<form method="post"') == 2
        assert source.count('name="csrf_token" value="{{ csrf_token() }}"') == 2
        assert "url_for('" + reapply + "'" in source
        assert "url_for('" + accept + "'" in source
        assert source.count('data-kaori-dialog-close') == 2
        assert "registry_ui.footer('tenant.operations'" in source
        assert "'tab': 'allocation-drift'" in source
        assert 'components/states/_empty_state.html' in source
        assert '§rid§' not in source


def test_capsule_drift_filters_are_committed_and_independently_paginated() -> None:
    routes = read('app/kubernetes/tenant/routes.py')
    quota = read('app/kubernetes/tenant/capsule_tenant_quota_governance.py')
    shared = read('app/kubernetes/tenant/capsule_allocation_governance.py')
    for name in (
        'ops_capsule_tenant_quota_tenant_id',
        'ops_capsule_tenant_quota_search',
        'ops_capsule_shared_tenant_id',
        'ops_capsule_shared_search',
    ):
        assert "request.args.get('" + name + "')" in routes
    assert "'capsule_tenant_quota_filters':" in quota
    assert "'capsule_shared_drift_filters':" in shared
    for source in (quota, shared):
        assert "str(drift_tenant_id or '').strip()" in source
        assert "str(drift_search or '').strip()[:160]" in source
        assert 'normalized_search.casefold()' in source
        assert 'paginate_sequence(' in source
    assert 'tenant.provider_reference' in quota
    assert 'intent.resource_name' in shared
    # UI gets already-committed rows, no new request-time direct provider read.
    for template in ('_capsule_tenant_quota_drift.html', '_capsule_shared_allocation_drift.html'):
        source = read('app/templates/kubernetes/tenant/partials/' + template)
        assert 'build_client(' not in source
        assert 'requests.get(' not in source


def test_capsule_drift_provider_lineage_jinja_compiles_and_renders() -> None:
    """#2931 UAT: guard against invalid, unquoted Tenant lineage in evidence modal."""
    from types import SimpleNamespace

    from jinja2 import Environment

    tenant_source = read('app/templates/kubernetes/tenant/partials/_capsule_tenant_quota_drift.html')
    shared_source = read('app/templates/kubernetes/tenant/partials/_capsule_shared_allocation_drift.html')

    # Parsing complete templates is mandatory: balanced HTML/Jinja directives
    # alone did not detect the original TemplateSyntaxError in DevContainer.
    for source in (tenant_source, shared_source):
        Environment(autoescape=True).parse(source)
        assert 'data-kaori-native-dialog' in source
        assert 'Provider Evidence' in source

    expected_expressions = (
        (tenant_source, "{{ 'Tenant · ' ~ record.name }}", 'kaori-capsule-uat-01'),
        (shared_source, "{{ 'Intent ' ~ record.public_id }}", 'intent-uat-01'),
    )
    for source, expression, expected in expected_expressions:
        assert expression in source
        assert "{{ Tenant · ' ~ record.name }}" not in source
        record = SimpleNamespace(name='kaori-capsule-uat-01', public_id='intent-uat-01')
        result = Environment(autoescape=True).from_string(expression).render(record=record)
        assert expected in result


def test_capsule_allocation_scope_intro_precedes_attached_tabs_and_wide_modals() -> None:
    """#4718 correction: match the existing Membership Registry tab surface."""
    from jinja2 import Environment

    page = read('app/templates/kubernetes/tenant/operations.html')
    allocation = page.split("{% elif active_tab == 'allocation-drift' %}", 1)[1].split(
        "{% elif active_tab == 'operational-reconcile' %}", 1
    )[0]
    primary = '{% include "kubernetes/tenant/partials/_capsule_tenant_quota_drift.html" %}'
    shared = '{% include "kubernetes/tenant/partials/_capsule_shared_allocation_drift.html" %}'
    assert primary in allocation and shared in allocation
    assert allocation.index('data-capsule-allocation-scope-guide') < allocation.index(
        'workspace_tabs.render_query_tabs('
    )
    assert allocation.index('workspace_tabs.render_query_tabs(') < allocation.index(primary)
    assert 'Capsule Allocation Authority' in allocation
    assert 'Capsule authoritative' in allocation
    assert 'Tenant.spec.resourceQuotas governs Namespace quotas' in allocation
    assert 'GlobalResourceQuota governs shared allocation' in allocation
    assert 'Sync observes drift; recovery requires an explicit decision.' in allocation
    assert 'hx-select="#tenant-operations-workspace"' in allocation
    assert 'min-w-0 overflow-hidden rounded-2xl border border-outline-default' in allocation
    assert 'workspace_tabs.render_navigation(' not in allocation
    assert 'data-kaori-native-dialog' not in allocation
    assert '<form method="post"' not in allocation
    Environment(autoescape=True).parse(page)

    for name in ('_capsule_tenant_quota_drift.html', '_capsule_shared_allocation_drift.html'):
        source = read('app/templates/kubernetes/tenant/partials/' + name)
        Environment(autoescape=True).parse(source)
        assert 'max-w-5xl overflow-hidden rounded-2xl' in source
        assert 'max-w-3xl overflow-hidden rounded-2xl' not in source
        assert 'mt-3 grid grid-cols-1 gap-x-4 gap-y-3 sm:grid-cols-2 lg:grid-cols-3' in source
        assert 'mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2' in source
        assert source.count('data-kaori-native-dialog') == 1
        assert source.count('<form method="post"') == 2
        assert source.count('name="csrf_token" value="{{ csrf_token() }}"') == 2
        assert 'data-kaori-dialog-close' in source
        assert 'Provider Evidence' in source
        assert 'Reconciliation Decision' in source


def test_capsule_drift_info_tip_and_reconciliation_decision_cards() -> None:
    """#2931: title-adjacent canonical Guide + independent explicit choices, in both dialogs."""
    from jinja2 import Environment

    expected = (
        ('_capsule_tenant_quota_drift.html', 'capsule-tenant-quota-drift-guide'),
        ('_capsule_shared_allocation_drift.html', 'capsule-shared-allocation-drift-guide'),
    )
    for name, info_id in expected:
        source = read('app/templates/kubernetes/tenant/partials/' + name)
        Environment(autoescape=True).parse(source)
        assert '{% import "components/info_tip.html" as info_tip %}' in source
        assert 'table_ui.block_classes(allow_overflow=true)' in source
        assert '{% set title_info %}' in source
        assert 'info_tip.render(' in source
        assert info_id in source
        assert "variant='guide'" in source
        assert 'title_extra=title_info' in source
        assert 'result_count=' in source
        assert source.index('title_extra=title_info') < source.index('result_count=')
        assert 'data-kaori-native-dialog' in source
        assert "table_label.metadata_label('Provider Write', icon='server-cog')" in source
        assert "table_label.metadata_label('Commit Only', icon='file-check-2')" in source
        assert 'mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2' in source
        assert (
            source.count('flex min-w-0 flex-col gap-2.5 rounded-lg border border-outline-subtle bg-surface-hover') == 2
        )
        assert 'Reapply KAORI quota via Capsule after validation.' in source
        assert 'Commit verified provider quota as KAORI intent. No provider write.' in source
        # Separate scoped POST actions are still protected by the original gate and CSRF.
        assert "can_manage and state.get('reapply_supported') and state.get('accept_supported')" in source
        assert source.count('<form method="post"') == 2
        assert source.count('name="csrf_token" value="{{ csrf_token() }}"') == 2
        assert 'data-kaori-dialog-close' in source
        assert 'table_ui.action_classes()' in source

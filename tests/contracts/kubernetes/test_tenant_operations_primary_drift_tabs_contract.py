"""Keep focused Tenant drift workflows at the primary Operations tab level."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PARTIALS = ROOT / 'app/templates/kubernetes/tenant/partials'


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_drift_workflows_use_canonical_primary_tabs_not_nested_tabs() -> None:
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
    assert "hx_target='#tenant-operations-workspace'" in operations
    assert "hx_push_url='true'" in operations
    assert "'tenant-drift-views'" not in operations
    assert 'data-tenant-drift-view' not in operations
    assert 'drift_view=drift_view' not in routes
    assert "active_tab in {'allocation-drift', 'operational-reconcile'}" in routes


def test_existing_drift_urls_still_map_to_primary_tabs() -> None:
    route_common = read('app/kubernetes/tenant/route_common.py')
    assert "if active_tab == 'drift-reconcile':" in route_common
    assert "request.args.get('drift_view') == 'operations'" in route_common
    assert "return 'operational-reconcile' if" in route_common
    assert "else 'allocation-drift'" in route_common


def test_each_primary_tab_has_two_tables_with_provider_details_preserved() -> None:
    operations = read('app/templates/kubernetes/tenant/operations.html')
    allocation = operations.split("{% elif active_tab == 'allocation-drift' %}", 1)[1].split(
        "{% elif active_tab == 'operational-reconcile' %}", 1
    )[0]
    operational = operations.split("{% elif active_tab == 'operational-reconcile' %}", 1)[1].split('{% else %}', 1)[0]

    assert allocation.count('{% include "kubernetes/tenant/partials/') == 2
    for name in ('_capsule_tenant_quota_drift.html', '_capsule_shared_allocation_drift.html'):
        assert name in allocation
    assert operational.count('{% include "kubernetes/tenant/partials/') == 3
    assert '_operations_drift_registry.html' in operational
    assert '_operations_access_reconciliation_registry.html' in operational
    assert '<details class="group' in operational
    assert 'data-tenant-provider-authority-disclosure' in operational
    assert '_operations_provider_registry.html' in operational


def test_each_registry_keeps_primary_tab_through_pagination_filter_and_clear() -> None:
    for name, tab in (
        ('_capsule_tenant_quota_drift.html', 'allocation-drift'),
        ('_capsule_shared_allocation_drift.html', 'allocation-drift'),
        ('_operations_drift_registry.html', 'operational-reconcile'),
        ('_operations_access_reconciliation_registry.html', 'operational-reconcile'),
        ('_operations_provider_registry.html', 'operational-reconcile'),
    ):
        source = (PARTIALS / name).read_text(encoding='utf-8')
        assert "'tab': '" + tab + "'" in source, name
        assert 'registry_ui.footer(' in source, name
        assert '.total_items > 0' not in source, name
        assert "'drift_view':" not in source, name
        if tab == 'operational-reconcile':
            assert f'name="tab" value="{tab}"' in source
            assert f"query_params={{'tab': '{tab}'}}" in source


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
        assert "table_ui.inventory_block_header(" in source
        assert 'result_count=' in source
        assert "header_actions=header_actions" in source
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
        assert "name=\"tab\" value=\"allocation-drift\"" in source
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
        assert "source.get('uid')" in source
        assert "source.get('resource_version')" in source
        assert "drift.get('observed_at')" in source
        assert "state.get('blocked_reason')" in source
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
        assert "normalized_search.casefold()" in source
        assert "paginate_sequence(" in source
    assert "tenant.provider_reference" in quota
    assert "intent.resource_name" in shared
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


def test_capsule_allocation_scope_guide_between_registries_and_wide_modals() -> None:
    """#2931 DevContainer UX follow-up: contextual bridge and readable evidence modal."""
    from jinja2 import Environment

    page = read('app/templates/kubernetes/tenant/operations.html')
    primary = '{% include "kubernetes/tenant/partials/_capsule_tenant_quota_drift.html" %}'
    shared = '{% include "kubernetes/tenant/partials/_capsule_shared_allocation_drift.html" %}'
    assert primary in page and shared in page
    scope = page.split(primary, 1)[1].split(shared, 1)[0]
    assert 'data-capsule-allocation-scope-guide' in scope
    assert '{{ table_ui.block_classes() }}' in scope
    assert 'Capsule Allocation Authority' in scope
    assert 'Two distinct quota scopes, one provider authority.' in scope
    assert 'Sync observes drift; recovery requires a decision.' in scope
    assert 'Tenant Resource Quotas' in scope
    assert 'Shared Allocation' in scope
    assert 'Tenant CR' in scope
    assert 'Namespace ResourceQuota' in scope
    assert 'GlobalResourceQuota' in scope
    assert 'Shared Tenant allocation' in scope
    assert 'Capsule reconciles generated Namespace ResourceQuota' in scope
    assert 'GlobalResourceQuota governs shared Tenant allocation' in scope
    # The scopes use two equal peer cards, not the rejected flat 3-column text strip.
    assert scope.count('<article class="min-w-0 rounded-lg border border-brand-outline bg-kaori-soft') == 2
    assert scope.count('bg-surface-card px-3 py-2 text-xs') == 2
    assert scope.count('data-lucide="arrow-right"') == 2
    assert 'grid gap-3 p-3 sm:grid-cols-2 sm:p-4' in scope
    assert 'lg:grid-cols-3' not in scope
    assert 'aria-labelledby="capsule-allocation-scope-guide-title"' in scope
    # Read-only guidance is not a third reconciliation registry.
    assert '<table' not in scope
    assert 'method="post"' not in scope
    assert 'data-kaori-native-dialog' not in scope
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
        assert "info_tip.render(" in source
        assert info_id in source
        assert "variant='guide'" in source
        assert "title_extra=title_info" in source
        assert "result_count=" in source
        assert source.index("title_extra=title_info") < source.index("result_count=")
        assert 'data-kaori-native-dialog' in source
        assert "table_label.metadata_label('Provider Write', icon='server-cog')" in source
        assert "table_label.metadata_label('Commit Only', icon='file-check-2')" in source
        assert 'mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2' in source
        assert source.count('flex min-w-0 flex-col gap-2.5 rounded-lg border border-outline-subtle bg-surface-hover') == 2
        assert 'Write committed KAORI quota via Capsule after admission and read-back checks.' in source
        assert 'Commit verified provider quota as KAORI intent. No provider write.' in source
        # Separate scoped POST actions are still protected by the original gate and CSRF.
        assert "can_manage and state.get('reapply_supported') and state.get('accept_supported')" in source
        assert source.count('<form method="post"') == 2
        assert source.count('name="csrf_token" value="{{ csrf_token() }}"') == 2
        assert 'data-kaori-dialog-close' in source
        assert "table_ui.action_classes()" in source

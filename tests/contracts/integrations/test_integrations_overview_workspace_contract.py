from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_overview_uses_canonical_accessible_workspace_tabs() -> None:
    overview = read('app/templates/integrations/overview.html')

    assert 'components/framed_workspace_tabs.html' in overview
    assert 'framed_workspace_tabs.render(' in overview
    assert "data-kaori-tab-variant=\"framed-workspace-v2\"" in read('app/templates/components/framed_workspace_tabs.html')
    assert "prefix='integration-overview'" in overview
    assert "allowedTabs: ['catalog', 'runtime', 'coverage']" in overview
    assert 'moveTab(currentTab, direction, prefix)' in overview
    for key in ('catalog', 'runtime', 'coverage'):
        assert f'id="integration-overview-panel-{key}"' in overview
        assert f'aria-labelledby="integration-overview-tab-{key}"' in overview
    assert 'rounded-xl border border-kaori-primary/20 bg-kaori-soft p-1.5' not in overview


def test_runtime_summary_uses_filtered_scope_and_runtime_health_is_not_inferred() -> None:
    service = read('app/integrations/service.py')

    assert 'runtime_global_stats = _runtime_stats(runtime_rows)' in service
    assert 'runtime_stats = _runtime_stats(filtered_runtime_rows)' in service
    assert "'runtime_scope_label': runtime_scope_label" in service
    assert "else ('healthy' if cluster.status == 'connected' else 'not_observed')" not in service
    assert "'health_status': observation.health_status if observation else 'not_observed'" in service
    assert "'observed_at': observation.observed_at if observation else None" in service


def test_runtime_observation_lookup_is_latest_per_target_in_database() -> None:
    service = read('app/integrations/service.py')

    assert 'func.row_number().over(' in service
    assert 'IntegrationRuntimeObservation.provider' in service
    assert 'IntegrationRuntimeObservation.instance_id' in service
    assert '.where(ranked.c.row_number == 1)' in service
    assert 'IntegrationRuntimeObservation.query.order_by(' not in service


def test_runtime_filters_auto_refresh_in_one_row_without_action_buttons() -> None:
    runtime = read('app/templates/integrations/partials/_runtime_overview.html')

    assert 'hx-trigger="change delay:100ms"' in runtime
    assert 'class="grid gap-4 md:grid-cols-3 md:items-end"' in runtime
    assert runtime.count('table_ui.filter_select_classes()') == 3
    assert 'Apply Filters' not in runtime
    assert '>Reset<' not in runtime


def test_runtime_records_use_inventory_table_and_expandable_details() -> None:
    runtime = read('app/templates/integrations/partials/_runtime_overview.html')
    detail = read('app/templates/integrations/partials/_runtime_detail_content.html')
    overview = read('app/templates/integrations/overview.html')

    assert 'components/table.html' in runtime
    assert "table_ui.table_classes('min-w-[78rem]')" in runtime
    assert "integration_ui.palette_icon(row.provider_icon, 'brand', size='lg', rounded='md')" in runtime
    assert 'table_ui.row_classes()' in runtime
    assert 'components/details/_expandable_row.html' in runtime
    assert 'expandable_row.toggle_button(' in runtime
    assert "open_label='View More'" in runtime
    assert 'expandable_row.detail_row(' in runtime
    assert 'resource_detail_modal' not in runtime
    assert 'resource_detail_modal' not in overview
    assert 'data-kaori-detail-variant="inline-expansion"' in detail
    assert 'Runtime Evidence' in detail
    assert 'Connection & Validation' in detail
    assert 'Capability & Diagnostic' in detail


def test_runtime_footer_uses_standard_showing_and_rows_copy() -> None:
    runtime = read('app/templates/integrations/partials/_runtime_overview.html')
    registry = read('app/templates/integrations/components/_provider_registry.html')

    assert "item_label='Integration'" in runtime
    assert 'provider_registry.pagination_footer(' in runtime
    assert '>Rows</span>' in registry
    assert 'pagination.start_item' in registry
    assert 'pagination.end_item' in registry
    assert 'pagination.total_items' in registry


def test_runtime_htmx_route_is_limited_to_its_own_target() -> None:
    routes = read('app/integrations/routes.py')

    assert "htmx_target() == 'integration-runtime-overview'" in routes
    assert "and context['active_tab'] == 'runtime'" in routes
    assert "@integrations_bp.get('/runtime/<string:detail_key>/details')" in routes


def test_portfolio_and_domain_coverage_use_neutral_card_semantics() -> None:
    overview = read('app/templates/integrations/overview.html')
    service = read('app/integrations/service.py')

    for label in ('Configured Targets', 'Ready for Use', 'Validation Required', 'Not Configured'):
        assert label in overview
    assert 'Connection and Authority Boundary' in overview
    assert 'Integration Portfolio Overview' not in overview
    assert 'Integration Domain Coverage' in overview
    assert 'Operational Domains' in overview
    assert 'Planned Domains' in overview
    assert 'Provider Workspaces' in overview
    assert 'Operational Readiness' in overview
    assert 'Planned Provider Ownership' in overview
    assert 'Coverage Boundary' in overview
    assert "coverage|selectattr('lifecycle', 'equalto', 'available')|list" in overview
    assert "coverage|rejectattr('lifecycle', 'equalto', 'available')|list" in overview
    assert 'coverage_stats.available_domains' in overview
    assert "table_ui.table_classes('min-w-[56rem]')" not in overview
    assert "'description': 'Metrics, alert routing, runtime validation, and capability evidence.'" in service
    assert "'providers': 'Prometheus · Alertmanager'" in service
    assert "'providers': 'Vault · OpenBao'" in service
    assert "'readiness_percent'" in service
    assert "'attention_targets'" in service


def test_zero_capability_attention_has_human_readable_copy() -> None:
    service = read('app/integrations/service.py')

    assert "return 'No Capability Attention'" in service
    assert "f'{count} Items Need Attention'" in service
    assert "f'{attention} items need attention'" not in service


def test_integration_overview_uses_violet_identity_icons_and_semantic_status_badges() -> None:
    workspace = read('app/templates/integrations/components/_workspace.html')
    overview = read('app/templates/integrations/overview.html')
    runtime = read('app/templates/integrations/partials/_runtime_overview.html')

    assert 'macro palette_icon_classes' in workspace
    assert 'macro palette_icon(' in workspace
    assert 'border-brand-outline bg-kaori-soft text-kaori-primary' in workspace
    assert 'data-kaori-integration-overview-violet-icons' in overview
    assert 'data-kaori-runtime-overview-violet-icons' in runtime

    # Identity and navigation icons stay in the KAORI violet family.
    assert "palette_icon(item.icon, 'brand', size='lg')" in overview
    assert "palette_icon(item.icon, 'brand')" in overview
    assert "palette_icon('layout-grid', 'brand', size='lg')" in overview
    assert "palette_icon('shield-check', 'brand', size='sm')" in overview
    assert "palette_icon(row.provider_icon, 'brand', size='lg', rounded='md')" in runtime
    assert 'provider_icon_tone' not in overview
    assert 'provider_icon_tone' not in runtime
    assert 'domain_icon_tone' not in overview

    # Summary cards use violet identity icons; condition meaning remains in semantic labels.
    assert "metric_card('Ready for Use'" in overview and "'badge-check', 'brand')" in overview
    assert "metric_card('Validation Required'" in overview and "'scan-search', 'brand')" in overview
    assert "metric_card('Not Configured'" in overview and "'circle-dashed', 'brand')" in overview
    for label in ('Healthy', 'Degraded', 'Unhealthy', 'Not Observed', 'Capability Attention'):
        assert f"('{label}', runtime_stats." in runtime
    assert runtime.count("'brand')") >= 5

    # Semantic status adapter remains responsible for ready/warning/error meaning.
    assert 'integration_status(' in overview
    assert "integration_status(row.health_status, display='indicator')" in runtime


def test_integration_overview_uses_canonical_label_roles() -> None:
    overview = read('app/templates/integrations/overview.html')
    runtime = read('app/templates/integrations/partials/_runtime_overview.html')
    adapter = read('app/templates/integrations/components/_semantic_status.html')

    assert 'components/table_label.html' in overview
    assert 'components/table_label.html' in runtime

    # Context and count metadata use the shared metadata label. Only scope gets an icon.
    assert "table_label.metadata_label(available_provider_count ~ ' Available · ' ~ planned_provider_count ~ ' Planned'" in overview
    assert "table_label.metadata_label(planned_provider_count ~ ' Planned'" in overview
    assert "table_label.metadata_label(provider_name, size='compact')" in overview
    assert "table_label.metadata_label(runtime_scope_label, 'filter'" in runtime
    assert "table_label.metadata_label(runtime_stats.total ~ ' of ' ~ runtime_global_stats.total ~ ' Targets'" in runtime

    # Repeated lifecycle/readiness states use a semantic dot instead of a Lucide icon.
    assert "integration_status('ready', 'Available', display='indicator')" in overview
    assert "integration_status(row.health_status, display='indicator')" in runtime
    assert "integration_status(row.readiness, display='indicator')" in runtime

    # Planned lifecycle is text-first and page-local compact-label bundles are removed.
    assert "table_label.status_label('Planned', 'unknown'" in overview
    assert 'kaori-context-label inline-flex min-h-6' not in overview
    assert 'rounded-md bg-status-unknown-soft px-2 py-1 text-xs' not in overview

    # Adapter exposes explicit label roles while preserving audited legacy callers.
    assert "display='icon'" in adapter
    assert "display == 'indicator'" in adapter
    assert "display == 'text'" in adapter
    assert "display == 'special'" in adapter

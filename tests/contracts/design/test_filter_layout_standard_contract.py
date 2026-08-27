from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_shared_filter_geometry_fills_each_visible_row() -> None:
    primitives = read('app/templates/components/table_primitives.html')
    table = read('app/templates/components/table.html')
    registry = read('app/templates/components/table_registry.html')

    for token in (
        'macro filter_layout_classes',
        'flex w-full flex-wrap items-end gap-3',
        '[&>label]:flex-1',
        '[&>div]:flex-1',
        'sm:[&>label]:basis-56',
        'sm:[&>div]:basis-56',
        '[&>[data-kaori-filter-action]]:flex-none',
        '[&>[data-kaori-filter-action]]:basis-auto',
    ):
        assert token in primitives

    assert 'table_primitives.filter_layout_classes()' in table
    assert 'class="{{ table_primitives.filter_layout_classes() }} {{ classes }}"' in registry


def test_provider_registry_and_reviewed_filter_surfaces_do_not_leave_orphan_columns() -> None:
    domain = read('app/templates/integrations/partials/_domain_workspace.html')
    coverage = read('app/templates/components/integration_coverage.html')
    namespace = read('app/templates/platform_operations/kubernetes/secret_reveal/_namespace_policy_section.html')
    alerts = read('app/templates/kubernetes/analytics/alerts/partials/_table_filters.html')
    topology = read('app/templates/kubernetes/inventory/topology/partials/_workspace.html')

    assert domain.count('registry_ui.filter_form(') == 2
    assert 'xl:grid-cols-3' not in domain

    assert 'table_ui.filter_layout_classes()' in coverage
    assert 'xl:grid-cols-12' not in coverage
    assert 'xl:col-span-' not in coverage

    assert 'table_ui.filter_bar_classes()' in namespace
    assert namespace.count('table_ui.filter_label_classes()') >= 2
    assert 'table_ui.filter_input_classes()' in namespace
    assert 'table_ui.filter_select_classes()' in namespace
    assert 'bg-surface-card px-6 py-4' not in namespace
    assert 'md:grid-cols-[minmax(0,1fr)_18rem]' not in namespace

    assert 'analytics_workspace.filter_layout_classes()' in alerts
    assert 'lg:grid-cols-4' not in alerts
    assert 'lg:grid-cols-3' not in alerts

    assert 'table_ui.filter_layout_classes()' in topology
    assert 'xl:grid-cols-12' not in topology
    assert 'xl:col-span-' not in topology


def test_action_aware_filter_keeps_actions_compact_and_search_fills_remainder() -> None:
    bucket = read('app/templates/storage/object_storage/analytics/partials/_bucket_table.html')
    forecast = read('app/templates/storage/object_storage/analytics/partials/_bucket_forecast_table.html')

    assert 'class="block min-w-0 flex-1" for="object-storage-bucket-search"' in bucket
    assert 'class="flex flex-none flex-wrap items-center gap-2"' in bucket
    assert "keyup[event.target.name === 'bucket_q'] changed delay:450ms" in bucket
    assert "search[event.target.name === 'bucket_q']" in bucket
    assert 'clear_filters_action(' in bucket
    assert 'Apply Filter' not in bucket
    assert 'sm:max-w-md' not in bucket

    assert 'table_ui.filter_layout_classes()' in forecast
    assert 'registry_ui.clear_filters_action(' in forecast
    assert 'data-kaori-table-header-actions' in forecast
    assert 'forecast_watch' in forecast
    assert 'forecast_history_state' in forecast
    assert "table_ui.table_classes('min-w-[840px]')" in forecast
    assert 'record_pagination.render(' in forecast


def test_filter_standard_is_documented_and_release_gated() -> None:
    standard = read('docs/design/components/TABLE_AND_LABEL.md')
    engineering = read('docs/standards/KAORI_ENGINEERING_STANDARD_V1.md')
    quality_gate = read('scripts/quality_gate.sh')

    assert 'full-width and content-aware' in standard
    assert 'orphan empty column' in standard
    assert 'filters never use `max-w-*`' in standard
    assert 'canonical filter rows use the shared full-width wrapping geometry' in engineering
    assert 'python scripts/verify_filter_layout_standard.py' in quality_gate


def test_inherited_filter_bars_share_width_and_legacy_integration_grid_helper_is_retired() -> None:
    lifecycle = read('app/templates/platform_operations/data_lifecycle/partials/_history.html')
    notifications = read('app/templates/platform_operations/notifications/partials/_center_page_content.html')
    integration_workspace = read('app/templates/integrations/components/_workspace.html')

    assert 'table_ui.filter_bar_classes()' in lifecycle
    assert 'table_ui.filter_bar_classes()' in notifications
    assert 'lg:w-48' not in notifications
    assert 'lg:min-w-[20rem]' not in notifications
    assert 'macro filter_grid_classes' not in integration_workspace

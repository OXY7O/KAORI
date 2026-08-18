from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = ROOT / 'app/templates'
REGISTRY_COMPONENT = TEMPLATES / 'components/table_registry.html'


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_clear_filters_is_owned_by_the_shared_registry_component() -> None:
    component = read(REGISTRY_COMPONENT)

    assert "label='Clear Filters'" in component
    assert 'data-kaori-clear-filters' in component
    assert 'data-kaori-canonical-registry-clear' in component
    assert 'data-lucide="x"' in component
    assert '{page_param: 1, per_page_param: per_page}' in component
    assert "sync='closest section:replace'" in component


def test_legacy_reset_filter_copy_is_not_used_by_kaori_templates() -> None:
    for template in TEMPLATES.rglob('*.html'):
        source = read(template)
        assert 'Reset Filter' not in source, template
        assert 'Reset Filters' not in source, template


def test_shared_kaori_filter_surfaces_expose_clear_filters() -> None:
    excluded = {
        TEMPLATES / 'components/table.html',
        TEMPLATES / 'components/table_primitives.html',
        TEMPLATES / 'integrations/components/_workspace.html',
    }
    candidates: set[Path] = set()
    for template in TEMPLATES.rglob('*.html'):
        source = read(template)
        if 'inventory_filter_bar_classes()' in source or 'filter_region_classes()' in source:
            candidates.add(template)

    for template in sorted(candidates - excluded):
        assert 'clear_filters' in read(template), template


def test_specialized_filtered_tables_follow_the_same_clear_contract() -> None:
    specialized = (
        'kubernetes/analytics/alerts/partials/_alerts_table.html',
        'kubernetes/analytics/alerts/partials/_anomalies_table.html',
        'platform_operations/data_lifecycle/partials/_history.html',
        'platform_operations/kubernetes/secret_reveal/_namespace_policy_section.html',
        'reports/report_templates/index.html',
        'reports/schedules/index.html',
        'access/users/partials/_content.html',
    )
    for relative in specialized:
        source = read(TEMPLATES / relative)
        assert 'clear_filters' in source, relative
        assert 'per_page' in source, relative


def test_headered_inventory_surfaces_place_clear_filters_with_header_actions() -> None:
    headered = (
        'kubernetes/inventory/nodes/partials/_table_card.html',
        'kubernetes/inventory/namespaces/partials/_table_card.html',
        'kubernetes/inventory/workloads/partials/_table_card.html',
        'kubernetes/inventory/pods/partials/_table_card.html',
        'kubernetes/inventory/services/partials/_table_card.html',
        'kubernetes/inventory/ingresses/partials/_table_card.html',
        'kubernetes/inventory/storage/partials/_table_card.html',
        'kubernetes/inventory/configuration/partials/_table_card.html',
        'kubernetes/governance/tls_certificates/partials/_table.html',
        'kubernetes/operations/secrets/_bulk_target_table.html',
        'storage/object_storage/inventory/systems/partials/_table_card.html',
        'storage/object_storage/inventory/buckets/partials/_table_card.html',
    )
    table = read(TEMPLATES / 'components/table.html')

    assert 'data-kaori-table-header-actions' in table
    assert "header_actions=''" in table
    for relative in headered:
        source = read(TEMPLATES / relative)
        assert 'header_actions=inventory_header_actions' in source, relative
        assert 'clear_filters_action(' in source, relative
        assert 'mb-3 flex justify-end' not in source, relative


def test_topology_reuses_clear_filters_and_distinguishes_snapshot_reload() -> None:
    workspace = read(TEMPLATES / 'kubernetes/inventory/topology/partials/_workspace.html')
    script = read(ROOT / 'app/static/js/kubernetes/inventory/topology.js')
    pattern = read(ROOT / 'docs/design/patterns/KUBERNETES_TOPOLOGY.md')

    assert 'components/table_registry.html' in workspace
    assert 'topology-clear-filters-button' in workspace
    assert "marker='topology-filter-form'" in workspace
    assert "action_label='Reload Snapshot'" in workspace
    assert 'Refresh Graph' not in workspace
    assert "$('topology-reload-button')?.addEventListener('click', fetchGraph)" in script
    assert "clearFiltersButton?.addEventListener('click'" in script
    assert "scopeSelect.value = 'all'" in script
    assert "depthSelect.value = '1'" in script
    assert "searchInput.value = ''" in script
    assert script.count("searchInput.value = ''") == 1
    assert 'It is a JavaScript data fetch, not an HTMX page refresh.' in pattern

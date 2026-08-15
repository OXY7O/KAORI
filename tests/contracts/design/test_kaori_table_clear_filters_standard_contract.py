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
    assert 'data-kaori-canonical-registry-clear' in component
    assert 'data-lucide="x"' in component
    assert "{page_param: 1, per_page_param: per_page}" in component
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
        'analytics/kubernetes/alerts/partials/_alerts_table.html',
        'analytics/kubernetes/alerts/partials/_anomalies_table.html',
        'platform_operations/data_lifecycle/partials/_history.html',
        'platform_operations/kubernetes/secret_reveal/_namespace_policy_section.html',
        'reports/report_templates/index.html',
        'reports/schedules/index.html',
        'users/partials/_content.html',
    )
    for relative in specialized:
        source = read(TEMPLATES / relative)
        assert 'clear_filters' in source, relative
        assert 'per_page' in source, relative

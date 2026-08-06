from pathlib import Path
import re


SURFACE = Path('app/templates/analytics/components/_analysis_surfaces.html')
OVERVIEW_ROOT = Path('app/templates/analytics/overview')
HEALTH = OVERVIEW_ROOT / 'partials/_health_summary.html'
RESOURCE = OVERVIEW_ROOT / 'partials/_resource_snapshot.html'
STORAGE = OVERVIEW_ROOT / 'partials/_storage_snapshot.html'
STYLES = Path('frontend/styles.css')
FORECAST_INDEX = Path('app/templates/analytics/forecast/index.html')


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_shared_analysis_surface_uses_neutral_guidance_composition() -> None:
    source = read(SURFACE)

    assert "macro attention_strip_classes(tone=none)" in source
    assert "macro interpretation_grid_classes(extra='', cards=false)" in source
    assert "macro guidance_icon_classes(role='brand', tone='info', size='default')" in source
    assert "macro interpretation_callout(" in source
    assert 'bg-surface-card' in source
    assert 'divide-y divide-outline-subtle' in source
    assert 'text-content-secondary' in source
    assert "macro role_label_classes(role='brand', tone='info')" in source
    assert 'table_label.tone_surface_classes(resolved_tone)' in source
    assert 'table_label.tone_dot_classes(resolved_tone)' not in source
    assert 'block h-1' not in source


def test_analytics_scope_replaces_violet_tinted_supporting_surfaces_with_slate_neutrals() -> None:
    source = read(STYLES)
    analytics_block = source.split('.kaori-analytics-page {', 1)[1].split('@theme inline', 1)[0]

    for expected in (
        '--kaori-surface-muted: #f8fafc;',
        '--kaori-surface-hover: #f1f5f9;',
        '--kaori-content-secondary: #475569;',
        '--kaori-content-muted: #64748b;',
        '--kaori-outline-subtle: #e2e8f0;',
        '--kaori-surface-card: #181b22;',
        '--kaori-content-secondary: #cbd5e1;',
        '--kaori-content-muted: #94a3b8;',
    ):
        assert expected in analytics_block

    assert '#f8f5fc' not in analytics_block
    assert '#ded6e8' not in analytics_block
    assert '#26212f' not in analytics_block
    assert 'class="kaori-analytics-page space-y-6"' in read(FORECAST_INDEX)


def test_overview_boxes_do_not_use_semantic_soft_background_accents() -> None:
    violations: list[str] = []
    semantic_soft = re.compile(r'bg-status-(?:normal|warning|critical|unknown|info|pending|maintenance)-soft')

    for template in OVERVIEW_ROOT.rglob('*.html'):
        source = read(template)
        if semantic_soft.search(source):
            violations.append(str(template))
        assert 'card=true' not in source, template
        assert 'tone_dot_classes(' not in source, template
        assert 'tone_surface_classes(' not in source, template

    assert violations == []


def test_operational_health_uses_neutral_signal_cards_and_status_badges() -> None:
    source = read(HEALTH)

    assert 'overview_surface.attention_strip_classes()' in source
    assert "'Needs' if issue_count == 1 else 'Need'" in source
    assert "table_label.status_label('Refresh Required', 'warning'" in source
    assert 'grid gap-px bg-outline-subtle sm:grid-cols-2 lg:grid-cols-3' in source
    assert 'overview_surface.semantic_icon_classes(semantic_tone)' in source
    assert 'table_label.status_label(item.status' in source
    assert 'overview_surface.interpretation_grid_classes()' in source
    assert "role='status'" in source
    assert "role='brand'" in source
    assert '2xl:grid-cols-6' not in source


def test_resource_pressure_keeps_semantic_bars_without_colored_guidance_icons() -> None:
    source = read(RESOURCE)

    assert 'progress_bar.semantic_bar(percent, semantic_tone' in source
    assert 'overview_surface.resource_icon_classes(item.label)' in source
    assert "bar_class =" not in source
    assert "else 'bg-kaori-primary'" not in source
    assert 'overview_surface.interpretation_grid_classes()' in source
    assert "tone='info'" in source
    assert 'semantic=true' not in source


def test_storage_pressure_uses_status_bar_and_neutral_values() -> None:
    source = read(STORAGE)

    assert 'progress_bar.pressure_tone(used_percent, pressure_available)' in source
    assert 'progress_bar.semantic_bar(used_percent, pressure_tone' in source
    assert 'overview_surface.resource_icon_classes(metric.label)' in source
    assert 'text-status-normal' not in source
    assert 'bar_class' not in source

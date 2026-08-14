from pathlib import Path

from jinja2 import Environment, meta

OVERVIEW_PARTIALS = Path('app/templates/analytics/kubernetes/overview/partials')
ACCIDENTAL_SCOPE_NAMES = {
    'analysis_surface',
    'overview_surface',
    'item',
    'metric',
    'signal',
    'row',
}


def _undeclared(path: Path) -> set[str]:
    environment = Environment()
    parsed = environment.parse(path.read_text(encoding='utf-8'))
    return set(meta.find_undeclared_variables(parsed))


def test_overview_partials_do_not_reference_unbound_macro_aliases_or_loop_variables() -> None:
    violations: dict[str, list[str]] = {}

    for template in sorted(OVERVIEW_PARTIALS.glob('*.html')):
        unresolved = sorted(_undeclared(template) & ACCIDENTAL_SCOPE_NAMES)
        if unresolved:
            violations[str(template)] = unresolved

    assert violations == {}


def test_health_summary_uses_its_declared_surface_alias() -> None:
    source = (OVERVIEW_PARTIALS / '_health_summary.html').read_text(encoding='utf-8')

    assert 'as overview_surface' in source
    assert 'analysis_surface.' not in source
    assert 'overview_surface.snapshot_header_icon_classes()' in source
    assert 'overview_surface.metric_icon_classes()' in source


def test_workload_metric_loop_uses_the_bound_metric_record() -> None:
    source = (OVERVIEW_PARTIALS / '_workload_snapshot.html').read_text(encoding='utf-8')

    assert '{% for metric in metrics %}' in source
    assert 'overview_surface.resource_icon_classes(metric.label)' in source
    assert 'overview_surface.resource_icon_classes(item.label)' not in source

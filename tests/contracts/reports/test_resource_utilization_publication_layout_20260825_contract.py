from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_resource_utilization_uses_canonical_post_chart_spacing() -> None:
    template = read('app/templates/reports/pdf/resource_utilization.html')
    css = read('app/static/reports/pdf/resource_utilization.css')

    assert template.count('chart-legend chart-to-section-gap') == 3
    assert '.chart-to-section-gap' in css
    assert 'margin-bottom:' in css.split('.chart-to-section-gap', 1)[1].split('}', 1)[0]


def test_node_participation_card_keeps_labels_and_values_inside_card() -> None:
    css = read('app/static/reports/pdf/resource_utilization.css')
    compact = ''.join(css.split())

    assert 'grid-template-columns:31mmminmax(0,1fr)' in compact
    assert '.node-legend{min-width:0' in compact
    assert 'grid-template-columns:3mmminmax(0,1fr)9mm' in compact
    assert '.node-legendspan{white-space:nowrap' in compact
    assert '.page-pod-node.source-note{margin-bottom:' in compact


def test_memory_concentration_center_value_is_owned_by_svg() -> None:
    template = read('app/templates/reports/pdf/resource_utilization.html')
    renderer = read('app/reports/export/html_pdf/resource_utilization.py')
    css = read('app/static/reports/pdf/resource_utilization.css')

    assert 'donut-center' not in template
    assert '.donut-center' not in css
    assert "'memory_donut_svg': _donut_svg(memory_consumers[:3])" in renderer
    assert 'def _donut_svg(items: list[dict[str, Any]]) -> str:' in renderer
    assert '>{total:.2f}</text>' in renderer
    assert '>GiB displayed</text>' in renderer


def test_cpu_concentration_uses_reference_codes_without_utilization_threshold_markers() -> None:
    template = read('app/templates/reports/pdf/resource_utilization.html')
    distribution = template.split("ui.section('Figure 5 - CPU Concentration'", 1)[1].split(
        "ui.section('Consumer Reference Register'", 1
    )[0]

    assert '<strong>C{{ loop.index }}</strong>' in distribution
    assert 'item.namespace' not in distribution
    assert 'warning-marker' not in distribution
    assert 'critical-marker' not in distribution
    assert 'Figure 5 - Displayed CPU Concentration' not in template


def test_reports_overview_copy_is_compact_without_losing_publication_boundary() -> None:
    estate = read('app/templates/reports/overview/partials/_reporting_estate_capability.html')

    assert (
        'Published formats stay family-owned; candidates remain blocked until contract and renderer are registered.'
        in estate
    )
    assert 'Published contracts, templates, and schedules approved for governed generation.' in estate
    assert 'candidate domains stay non-executable' not in estate
    assert 'recurring schedules that are admitted to the governed generation workflow' not in estate

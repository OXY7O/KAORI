from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_capacity_scheduling_summary_cards_use_publication_box_layout() -> None:
    template = read('app/templates/reports/pdf/capacity_analysis.html')
    css = read('app/static/reports/pdf/capacity_analysis.css')
    compact = ''.join(css.split())

    scheduling = (
        template.split("ui.section('Pod Scheduling Position'", 1)[1]
        .split("ui.section('Node Participation'", 1)[0]
    )

    assert 'class="summary-box-grid"' in scheduling
    assert scheduling.count('class="summary-box"') == 2
    assert '.summary-box-grid{display:grid;grid-template-columns:1fr1fr' in compact
    assert '.summary-box{min-height:' in compact
    assert '.summary-boxspan{display:block' in compact
    assert '.summary-boxstrong{display:block' in compact
    assert '.summary-boxsmall{display:block' in compact


def test_capacity_node_participation_keeps_legend_values_inside_card() -> None:
    css = read('app/static/reports/pdf/capacity_analysis.css')
    compact = ''.join(css.split())

    assert 'grid-template-columns:31mmminmax(0,1fr)' in compact
    assert '.node-legend{min-width:0' in compact
    assert 'grid-template-columns:3mmminmax(0,1fr)9mm' in compact
    assert '.node-legendspan{white-space:normal;overflow-wrap:normal' in compact
    assert '.node-legendstrong{text-align:right;white-space:nowrap' in compact


def test_capacity_forecast_legend_uses_canonical_spacing_and_swatch_layout() -> None:
    template = read('app/templates/reports/pdf/capacity_analysis.html')
    css = read('app/static/reports/pdf/capacity_analysis.css')
    compact = ''.join(css.split())

    assert 'class="chart-legend chart-to-section-gap"' in template
    assert '.chart-legend{display:flex;' in compact
    assert '.chart-to-section-gap{margin-bottom:' in compact
    assert '.chart-legendspan::before{content:"";display:inline-block;' in compact
    for selector in (
        'legend-cpu',
        'legend-memory',
        'legend-pods',
        'legend-warning',
        'legend-critical',
    ):
        assert f'.{selector}' in css

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
    distribution = template.split("ui.section('Figure 7 - CPU Concentration'", 1)[1].split(
        "ui.section('Consumer Reference Register'", 1
    )[0]

    assert '<strong>C{{ loop.index }}</strong>' in distribution
    assert 'item.namespace' not in distribution
    assert 'warning-marker' not in distribution
    assert 'critical-marker' not in distribution
    assert 'Figure 7 - Displayed CPU Concentration' not in template


def test_reports_overview_copy_is_compact_without_losing_publication_boundary() -> None:
    estate = read('app/templates/reports/overview/partials/_reporting_estate_capability.html')

    assert (
        'Published formats stay family-owned; candidates remain blocked until contract and renderer are registered.'
        in estate
    )
    assert 'Published contracts, templates, and schedules approved for governed generation.' in estate
    assert 'candidate domains stay non-executable' not in estate
    assert 'recurring schedules that are admitted to the governed generation workflow' not in estate


def test_resource_utilization_balances_visual_pairs_and_stacks_dense_followups() -> None:
    template = read('app/templates/reports/pdf/resource_utilization.html')
    css = read('app/static/reports/pdf/resource_utilization.css')
    shared_css = read('app/static/reports/pdf/analytics_publication.css')
    compact = ''.join(css.split())
    shared_compact = ''.join(shared_css.split())

    assert template.count('publication-pair') >= 5
    assert '.publication-pair{' in shared_compact
    pair_block = shared_compact.split('.publication-pair{', 1)[1].split('}', 1)[0]
    assert 'grid-template-columns:minmax(0,1fr)minmax(0,1fr)!important' in pair_block
    assert '.publication-pair.is-stacked{' in shared_compact

    assert '.trend-interpretation-stack' in shared_css
    assert '.trend-interpretation-stack{display:grid' in shared_compact

    distribution_pair = template.split('class="two-column publication-pair distribution-split"', 1)[1].split(
        "ui.section('Consumer Reference Register'", 1
    )[0]
    assert 'distribution-note' not in distribution_pair
    assert 'cpu-concentration-card' in distribution_pair
    assert 'distribution-boundary-note' in template
    assert '.memory-concentration-card' in shared_css
    assert '.cpu-concentration-card' in shared_css
    assert 'height:var(--analytics-visual-distribution-height)!important' in shared_compact


def test_resource_utilization_figure_numbering_is_contiguous_for_visuals_only() -> None:
    template = read('app/templates/reports/pdf/resource_utilization.html')

    expected = [
        'Figure 1 - Shared Resource Utilization',
        'Figure 2 - CPU Direction',
        'Figure 3 - Memory Direction and Projection',
        'Figure 4 - Pod Scheduling Position',
        'Figure 5 - Node Participation',
        'Figure 6 - Displayed Memory Concentration',
        'Figure 7 - CPU Concentration',
        'Figure 8 - Resource Trend Outlook',
    ]
    for title in expected:
        assert title in template

    assert "ui.section('Pod Scheduling Position'" not in template
    assert "ui.section('Node Participation'" not in template
    assert 'Figure 4 - Displayed Memory Concentration' not in template
    assert 'Figure 5 - CPU Concentration' not in template
    assert 'Figure 6 - Resource Trend Outlook' not in template


def test_resource_utilization_reference_blocks_follow_title_description_content_hierarchy() -> None:
    template = read('app/templates/reports/pdf/resource_utilization.html')

    assert '<h3>Priority Finding References</h3>' in template
    assert (
        '<p class="reference-helper">Reference notes expand the fixed findings without widening the comparison table.</p>'
        in template
    )
    assert '<h3>CPU Consumer References</h3>' in template
    assert (
        '<p class="identity-register-subtitle">Stable reference codes map to complete CPU consumer identities and observed values.</p>'
        in template
    )
    assert '<h3>Memory Consumer References</h3>' in template
    assert (
        '<p class="identity-register-subtitle">Stable reference codes map to complete memory consumer identities and observed values.</p>'
        in template
    )
    assert '<h3>Complete Consumer Identities</h3>' in template
    assert (
        '<p class="identity-register-subtitle">Stable reference codes map to complete technical identities without widening the comparison register.</p>'
        in template
    )

    shared_css = read('app/static/reports/pdf/analytics_publication.css')
    compact = ''.join(shared_css.split())
    assert '.reference-helper,' in compact
    helper_block = compact.split('.reference-helper,', 1)[1].split('}', 1)[0]
    assert 'color:var(--analytics-muted)' in helper_block
    assert 'font-size:6.4pt' in helper_block


def test_resource_utilization_sections_after_paired_content_use_explicit_vertical_rhythm() -> None:
    template = read('app/templates/reports/pdf/resource_utilization.html')
    css = read('app/static/reports/pdf/resource_utilization.css')
    compact = ''.join(css.split())

    assert "ui.section('Leading CPU Consumers', 'Concise comparison fields map to full CPU identities by reference.', 'section-after-pair')" in template
    assert "ui.section('Leading Memory Consumers', 'Concise comparison fields map to full memory identities by reference.', 'section-after-pair')" in template
    assert "ui.section('Utilization Register', 'Comparison fields stay in-table; interpretation follows below.', 'section-after-pair')" in template
    assert "ui.section('Consumer Reference Register', 'Chart references map to complete consumer identities.', 'section-after-pair')" in template

    block = compact.split('.section-after-pair{', 1)[1].split('}', 1)[0]
    assert 'margin-top:' in block

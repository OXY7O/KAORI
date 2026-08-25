from __future__ import annotations

from pathlib import Path

from weasyprint import CSS, HTML
from weasyprint.text.fonts import FontConfiguration

ROOT = Path(__file__).resolve().parents[3]
SHARED_CSS = ROOT / 'app/static/reports/pdf/analytics_publication.css'
MM_TO_PX = 96 / 25.4


def _element_box(page: object, element_id: str) -> object:
    def walk(box: object) -> object | None:
        element = getattr(box, 'element', None)
        if element is not None and element.get('id') == element_id:
            return box
        for child in getattr(box, 'children', ()):
            found = walk(child)
            if found is not None:
                return found
        return None

    found = walk(page._page_box)  # type: ignore[attr-defined]
    assert found is not None, f'Unable to locate rendered element: {element_id}'
    return found


def _render(html: str, family_css: str | None = None) -> object:
    font_config = FontConfiguration()
    stylesheets = []
    if family_css:
        stylesheets.append(
            CSS(
                filename=str(ROOT / 'app/static/reports/pdf' / family_css),
                font_config=font_config,
            )
        )
    stylesheets.append(CSS(filename=str(SHARED_CSS), font_config=font_config))
    document = HTML(string=html, base_url=str(ROOT)).render(
        stylesheets=stylesheets,
        font_config=font_config,
    )
    return document.pages[0]


def test_first_top_level_section_after_pair_keeps_canonical_section_gap() -> None:
    page = _render(
        '''
        <html><body class="kaori-analytics-publication kaori-reporting-v3">
          <article class="page"><div class="page-content">
            <div class="metric-strip"></div>
            <div id="pair" class="two-column paired-sections publication-pair">
              <section class="content-section">
                <h2>Left</h2><p class="section-subtitle">Helper.</p>
                <div class="section-body"><div style="height:30mm">Left body</div></div>
              </section>
              <section class="content-section">
                <h2>Right</h2><p class="section-subtitle">Helper.</p>
                <div class="section-body"><div style="height:10mm">Right body</div></div>
              </section>
            </div>
            <section id="next" class="content-section">
              <h2>Next Register</h2><p class="section-subtitle">Helper.</p>
              <div class="section-body"><p>Body</p></div>
            </section>
          </div></article>
        </body></html>
        '''
    )
    pair = _element_box(page, 'pair')
    next_section = _element_box(page, 'next')
    gap = float(next_section.border_box_y()) - (float(pair.border_box_y()) + float(pair.border_height()))

    assert gap >= 5.4 * MM_TO_PX


def test_first_section_after_non_section_block_is_not_zeroed_by_first_of_type() -> None:
    page = _render(
        '''
        <html><body class="kaori-analytics-publication kaori-reporting-v3">
          <article class="page"><div class="page-content">
            <div class="metric-strip"></div>
            <div id="visual" style="height:20mm">Visual block</div>
            <section id="next" class="content-section">
              <h2>Next Section</h2><p class="section-subtitle">Helper.</p>
              <div class="section-body"><p>Body</p></div>
            </section>
          </div></article>
        </body></html>
        '''
    )
    visual = _element_box(page, 'visual')
    next_section = _element_box(page, 'next')
    gap = float(next_section.border_box_y()) - (float(visual.border_box_y()) + float(visual.border_height()))

    assert gap >= 5.4 * MM_TO_PX


def test_shared_publication_owns_summary_cards_and_chart_legends() -> None:
    compact = ''.join(SHARED_CSS.read_text(encoding='utf-8').split())

    for token in (
        '.summary-box-grid{display:grid;',
        '.summary-box{',
        '.summary-boxspan{display:block;',
        '.summary-boxstrong{display:block;',
        '.summary-boxsmall{display:block;',
        '.chart-legend{display:flex;',
        '.chart-legendspan::before{',
        '.legend-memory{--legend-color:#7C3AED;',
        '.legend-pods{--legend-color:#15803D;',
        '.legend-cpu{--legend-color:#2563EB;',
        '.legend-warning{--legend-color:#D97706;',
        '.legend-critical{--legend-color:#DC2626;',
    ):
        assert token in compact


def test_capacity_scheduling_uses_shared_summary_card_structure() -> None:
    template = (ROOT / 'app/templates/reports/pdf/capacity_analysis.html').read_text(encoding='utf-8')

    assert 'class="summary-box-grid"' in template
    assert '<span>Reported Capacity</span><strong>' in template
    assert '<span>Reported Remaining</span><strong>' in template
    assert 'class="chart-legend chart-to-section-gap"' in template


def test_reusable_summary_and_legend_primitives_are_not_redefined_by_family_css() -> None:
    offenders: list[str] = []
    for name in ('resource_utilization.css', 'capacity_analysis.css', 'storage_analysis.css'):
        source = (ROOT / 'app/static/reports/pdf' / name).read_text(encoding='utf-8')
        if '.summary-box-grid' in source or '.summary-box {' in source:
            offenders.append(f'{name}: summary-box')
        if '.chart-legend {' in source or '.legend-memory {' in source:
            offenders.append(f'{name}: chart-legend')

    assert not offenders, 'Shared publication primitives redefined locally:\n' + '\n'.join(offenders)

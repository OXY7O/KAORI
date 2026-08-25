from __future__ import annotations

from pathlib import Path

import pytest
from weasyprint import CSS, HTML
from weasyprint.text.fonts import FontConfiguration

ROOT = Path(__file__).resolve().parents[3]
SHARED_CSS = ROOT / 'app/static/reports/pdf/analytics_publication.css'


def _find_text_box_y(page: object, text: str) -> float:
    def walk(box: object) -> float | None:
        if str(getattr(box, 'text', '')).startswith(text):
            return float(getattr(box, 'position_y'))
        for child in getattr(box, 'children', ()):
            found = walk(child)
            if found is not None:
                return found
        return None

    found = walk(page._page_box)  # type: ignore[attr-defined]
    assert found is not None, f'Unable to locate rendered text: {text}'
    return found


def _render_peer_alignment_fixture() -> object:
    html = '''
    <html>
      <body class="kaori-analytics-publication kaori-reporting-v3">
        <article class="page">
          <div class="page-content">
            <div class="metric-strip"></div>
            <div class="two-column paired-sections publication-pair is-split">
              <section class="content-section">
                <h2>Left Peer Title</h2>
                <p class="section-subtitle">Short helper.</p>
                <div class="section-rule"><span></span></div>
                <div class="section-body"><p>LEFT BODY MARKER</p></div>
              </section>
              <section class="content-section">
                <h2>Right Peer Title</h2>
                <p class="section-subtitle">Longer helper text intentionally wraps onto a second line in a half-width peer and still keeps the peer content aligned.</p>
                <div class="section-rule"><span></span></div>
                <div class="section-body"><p>RIGHT BODY MARKER</p></div>
              </section>
            </div>
          </div>
        </article>
      </body>
    </html>
    '''
    font_config = FontConfiguration()
    document = HTML(string=html, base_url=str(ROOT)).render(
        stylesheets=[CSS(filename=str(SHARED_CSS), font_config=font_config)],
        font_config=font_config,
    )
    return document.pages[0]


def test_split_peer_titles_and_content_start_on_shared_rows() -> None:
    page = _render_peer_alignment_fixture()

    left_title = _find_text_box_y(page, 'Left Peer Title')
    right_title = _find_text_box_y(page, 'Right Peer Title')
    left_helper = _find_text_box_y(page, 'Short helper.')
    right_helper = _find_text_box_y(page, 'Longer helper text intentionally wraps')
    left_body = _find_text_box_y(page, 'LEFT BODY MARKER')
    right_body = _find_text_box_y(page, 'RIGHT BODY MARKER')

    assert abs(left_title - right_title) < 0.25
    assert abs(left_helper - right_helper) < 0.25
    assert abs(left_body - right_body) < 0.25


def test_pair_contract_neutralizes_first_of_type_spacing_and_reserves_helper_slot() -> None:
    compact = ''.join(SHARED_CSS.read_text(encoding='utf-8').split())

    assert '.publication-pair>.content-section:first-of-type{margin-top:0!important;' in compact
    assert '--analytics-pair-subtitle-slot:7mm' in compact
    assert '.publication-pair>.content-section>.section-subtitle{min-height:var(--analytics-pair-subtitle-slot)!important' in compact


@pytest.mark.parametrize(
    ('stylesheet_name', 'body_class'),
    [
        ('analytics_overview.css', ''),
        ('resource_utilization.css', 'kaori-resource-utilization-report'),
        ('capacity_analysis.css', 'kaori-capacity-analysis-report'),
        ('storage_analysis.css', 'kaori-storage-analysis-report'),
        ('workload_analysis.css', 'kaori-workload-analysis-report'),
        ('forecast_analysis.css', 'kaori-forecast-analysis-report'),
        ('top_consumers_analysis.css', 'kaori-top-consumers-report'),
        ('alerts_anomalies.css', 'kaori-alerts-anomalies-report'),
        ('object_storage_analysis.css', 'kaori-object-storage-analysis-report'),
        ('analytics_unavailable.css', 'kaori-analytics-unavailable-report'),
    ],
)
def test_every_analytics_family_stylesheet_preserves_peer_row_alignment(
    stylesheet_name: str,
    body_class: str,
) -> None:
    html = f'''
    <html>
      <body class="kaori-analytics-publication kaori-reporting-v3 {body_class}">
        <article class="page">
          <div class="page-content">
            <div class="metric-strip"></div>
            <div class="two-column paired-sections publication-pair is-split">
              <section class="content-section">
                <h2>LEFT TITLE</h2>
                <p class="section-subtitle">Short helper.</p>
                <div class="section-body"><p>LEFT BODY</p></div>
              </section>
              <section class="content-section">
                <h2>RIGHT TITLE</h2>
                <p class="section-subtitle">Long helper copy that can occupy a second line without moving the evidence row.</p>
                <div class="section-body"><p>RIGHT BODY</p></div>
              </section>
            </div>
          </div>
        </article>
      </body>
    </html>
    '''
    font_config = FontConfiguration()
    family_css = ROOT / 'app/static/reports/pdf' / stylesheet_name
    document = HTML(string=html, base_url=str(ROOT)).render(
        stylesheets=[
            CSS(filename=str(family_css), font_config=font_config),
            CSS(filename=str(SHARED_CSS), font_config=font_config),
        ],
        font_config=font_config,
    )
    page = document.pages[0]

    assert abs(_find_text_box_y(page, 'LEFT TITLE') - _find_text_box_y(page, 'RIGHT TITLE')) < 0.25
    assert abs(_find_text_box_y(page, 'Short helper.') - _find_text_box_y(page, 'Long helper copy')) < 0.25
    assert abs(_find_text_box_y(page, 'LEFT BODY') - _find_text_box_y(page, 'RIGHT BODY')) < 0.25

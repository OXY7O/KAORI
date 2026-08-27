from __future__ import annotations

from app.reports.export.html_pdf.builder import _build_section


class _AnalyticsOverviewReport:
    report_type = 'analytics_overview'


def test_overview_sections_materialize_committed_resource_and_forecast_evidence() -> None:
    payload = {
        'resource_snapshot': {
            'cpu': {'percent': 22.4, 'status': 'Normal'},
            'memory': {'percent': 61.4, 'status': 'Warning'},
        },
        'forecast_snapshot': {
            'available': True,
            'highest_projected_resource': 'Memory',
            'highest_projected_percent': 67.7,
            'series': [
                {
                    'key': 'memory',
                    'label': 'Memory',
                    'latest_percent': 61.4,
                    'projected_percent': 67.7,
                    'trend': 'Increasing',
                    'confidence': 'High',
                }
            ],
        },
    }

    resource = _build_section(_AnalyticsOverviewReport(), payload, 'resource_posture', 1)
    forecast = _build_section(_AnalyticsOverviewReport(), payload, 'trend_forecast', 2)

    assert resource.status_label == 'Included'
    assert {metric.label: metric.value for metric in resource.metrics} == {
        'Cpu': '22.4',
        'Memory': '61.4',
    }
    assert forecast.status_label == 'Included'
    assert forecast.note == ''
    series = next(table for table in forecast.tables if table.title == 'Series')
    assert series.columns == (
        'Label',
        'Key',
        'Latest Percent',
        'Projected Percent',
        'Trend',
        'Confidence',
    )
    assert series.rows == (('Memory', 'memory', '61.4', '67.7', 'Increasing', 'High'),)


def test_overview_section_without_structured_evidence_is_not_marked_included() -> None:
    section = _build_section(_AnalyticsOverviewReport(), {}, 'alerts_anomalies', 1)

    assert section.status_label == 'No Evidence'
    assert section.status_tone == 'warning'
    assert section.note == ('No structured evidence was returned for this section in the current reporting snapshot.')


def test_overview_unavailable_committed_source_is_explicit() -> None:
    payload = {
        'forecast_snapshot': {
            'available': False,
            'risk_note': 'Forecast data is not available yet.',
            'series': [],
        }
    }

    section = _build_section(_AnalyticsOverviewReport(), payload, 'trend_forecast', 1)

    assert section.status_label == 'Unavailable'
    assert section.status_tone == 'warning'

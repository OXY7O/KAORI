from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_analytics_overview_csv_sections_are_bound_to_committed_payload_sources() -> None:
    builder = read('app/reports/export/html_pdf/builder.py')

    expected_bindings = (
        "'executive_brief': ('snapshot_summary', 'health_summary')",
        "'resource_posture': ('resource_snapshot',)",
        "'trend_forecast': ('forecast_snapshot',)",
        "'top_consumers': ('top_consumers',)",
        "'capacity_pressure': ('capacity_snapshot', 'resource_snapshot')",
        "'alerts_anomalies': ('alert_detail', 'alerts_snapshot')",
        "'reporting_summary': ('reporting_summary',)",
        "'inventory_snapshot': ('inventory_snapshot',)",
        "'data_freshness_reliability': ('data_freshness',)",
        "'recommendation_plan': ('actionable_recommendations',)",
    )
    for binding in expected_bindings:
        assert binding in builder


def test_empty_structured_section_cannot_be_published_as_included() -> None:
    builder = read('app/reports/export/html_pdf/builder.py')

    assert "status_label, status_tone = 'No Evidence', 'warning'" in builder
    assert "if value.get('available') is False:" in builder
    assert "return 'Unavailable', 'warning'" in builder

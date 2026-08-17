from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVICE = (ROOT / 'app/kubernetes/analytics/forecast/service.py').read_text(encoding='utf-8')
RESOURCE = (ROOT / 'app/kubernetes/analytics/forecast/resource.py').read_text(encoding='utf-8')
CALCULATION = (ROOT / 'app/kubernetes/analytics/forecast/calculation.py').read_text(encoding='utf-8')
PRESENTATION = (ROOT / 'app/kubernetes/analytics/forecast/presentation.py').read_text(encoding='utf-8')
TEMPLATE = (ROOT / 'app/templates/kubernetes/analytics/forecast/partials/_forecast_section.html').read_text(encoding='utf-8')


def test_unavailable_forecast_is_unknown_and_uses_na() -> None:
    assert "else 'unknown'" in RESOURCE
    assert "if capacity > 0 else 'N/A'" in RESOURCE
    assert "'peak_projected_percent':" in RESOURCE
    assert 'item.peak_projected_percent is not none' in TEMPLATE
    assert "else 'N/A'" in TEMPLATE


def test_namespace_scope_semantics_are_explicit() -> None:
    assert 'Namespace Demand vs Cluster Capacity' in SERVICE
    assert 'Namespace PVC Usage vs Namespace Observed Capacity' in SERVICE
    assert 'Scope Boundary' in TEMPLATE
    assert 'item.comparison_label' in TEMPLATE
    assert 'item.capacity_label' in TEMPLATE


def test_summary_ignores_unavailable_and_marks_limited_evidence() -> None:
    assert "if item.get('has_data') and item.get('peak_projected_percent') is not None" in CALCULATION
    assert "'unavailable_resources': len(unavailable_items)" in CALCULATION
    assert "'limited_resources':" in CALCULATION
    assert "'posture_label': posture_label" in CALCULATION


def test_overview_snapshot_preserves_unavailable_forecast_semantics() -> None:
    overview = (ROOT / 'app/templates/kubernetes/analytics/overview/partials/_forecast_snapshot.html').read_text(encoding='utf-8')
    assert "'highest_projected_percent': None" in PRESENTATION
    assert "return 'Low' if has_forecast_evidence else 'Unknown'" in PRESENTATION
    assert "if forecast_risk == 'Unknown'" in PRESENTATION
    assert 'highest_percent is not none' in overview
    assert "'Unknown' if not has_forecast_evidence" in overview
    assert 'Latest Daily Average' in overview


def test_chart_payload_aligns_dates_and_preserves_projection_boundary() -> None:
    assert 'all_dates = sorted(' in CALCULATION
    assert 'forecast_map.setdefault(boundary_date, historical_map[boundary_date])' in CALCULATION
    assert "'labels': all_dates" in CALCULATION

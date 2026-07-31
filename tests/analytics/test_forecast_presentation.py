from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVICE = (ROOT / 'app/analytics/forecast/service.py').read_text(encoding='utf-8')
TEMPLATE = (ROOT / 'app/templates/analytics/forecast/partials/_forecast_section.html').read_text(encoding='utf-8')


def test_unavailable_forecast_is_unknown_and_uses_na() -> None:
    assert "status = _resolve_status(projected_percent) if projected_percent is not None else 'unknown'" in SERVICE
    assert "'capacity_display': _format_value(capacity, definition.unit) if capacity > 0 else 'N/A'" in SERVICE
    assert "'projected_percent': round(projected_percent, 2) if projected_percent is not None else None" in SERVICE
    assert "if item.projected_percent is not none" in TEMPLATE
    assert "else 'N/A'" in TEMPLATE


def test_namespace_scope_semantics_are_explicit() -> None:
    assert 'Namespace Demand vs Cluster Capacity' in SERVICE
    assert 'Namespace PVC Usage vs Namespace Claim Capacity' in SERVICE
    assert 'Scope Boundary' in TEMPLATE
    assert 'item.comparison_label' in TEMPLATE
    assert 'item.capacity_label' in TEMPLATE


def test_summary_ignores_unavailable_resources() -> None:
    assert "available_items = [item for item in items if item.get('has_data')" in SERVICE
    assert "'unavailable_resources': len(unavailable_items)" in SERVICE
    assert "'highest_projected_percent': highest_projected['projected_percent'] if highest_projected else None" in SERVICE


def test_overview_snapshot_preserves_unavailable_forecast_semantics() -> None:
    overview = (ROOT / 'app/templates/analytics/overview/partials/_forecast_snapshot.html').read_text(
        encoding='utf-8'
    )
    assert "'highest_projected_percent': None" in SERVICE
    assert "'forecast_risk': 'Unknown'" in SERVICE
    assert "return 'Low' if has_forecast_evidence else 'Unknown'" in SERVICE
    assert 'highest_percent is not none' in overview
    assert "'Unknown' if not has_forecast_evidence" in overview
    assert 'Latest Daily Average' in overview

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ROOT / 'app/templates/kubernetes/analytics/alerts/partials/_cluster_signal_overview.html'


def test_operator_first_signal_evidence_sections_keep_original_semantics() -> None:
    source = TEMPLATE.read_text(encoding='utf-8')
    for label in (
        'Operator Decision', 'Evidence Boundary', 'Signal Posture',
        'Alert Lifecycle', 'Alert Severity Profile', 'Investigation Focus',
    ):
        assert label in source
    for field in (
        'overview.total_signals', 'overview.active_alerts', 'overview.anomalies',
        'overview.pending_alerts', 'overview.resolved_alerts',
        'overview.critical_alerts', 'overview.warning_alerts', 'overview.info_alerts',
        'overview.fallback_used', 'overview.fallback_reason', 'overview.evidence_complete',
        'overview.insight.dominant_signal', 'overview.insight.dominant_anomaly',
        'overview.insight.action_hint',
    ):
        assert field in source


def test_signal_summary_uses_shared_surfaces_and_responsive_grids() -> None:
    source = TEMPLATE.read_text(encoding='utf-8')
    assert 'analytics/components/_analysis_surfaces.html' in source
    assert 'analysis_surface.snapshot_shell_classes()' in source
    assert 'analysis_surface.guidance_card_classes(' in source
    assert 'md:grid-cols-3' in source
    assert 'xl:grid-cols-2' in source
    assert 'aria-label="Alert severity profile"' in source
    assert 'xl:border-l xl:border-t-0' not in source

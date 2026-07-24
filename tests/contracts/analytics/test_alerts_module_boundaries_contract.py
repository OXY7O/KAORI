from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ALERTS = ROOT / 'app' / 'analytics' / 'alerts'
QUALITY_GATE = ROOT / 'scripts' / 'quality_gate.sh'

REQUIRED_MODULES = {
    '__init__.py',
    'anomalies.py',
    'application.py',
    'contracts.py',
    'health.py',
    'inhibition.py',
    'metrics.py',
    'ownership.py',
    'readiness.py',
    'routing.py',
    'selection.py',
    'signals.py',
    'silences.py',
    'snapshots.py',
    'sources.py',
}


def test_alerts_compatibility_facade_is_removed() -> None:
    assert not (ALERTS / 'service.py').exists()
    assert not (ALERTS / 'queries.py').exists()


def test_alerts_domain_has_explicit_responsibility_modules() -> None:
    existing = {path.name for path in ALERTS.glob('*.py')}
    assert REQUIRED_MODULES <= existing


def test_internal_consumers_use_canonical_alert_modules() -> None:
    offenders: list[str] = []
    for path in (ROOT / 'app').rglob('*.py'):
        source = path.read_text(encoding='utf-8')
        if 'app.analytics.alerts.service' in source or 'app.analytics.alerts.queries' in source:
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []


def test_provider_io_is_kept_out_of_application_and_snapshot_orchestrators() -> None:
    application = (ALERTS / 'application.py').read_text(encoding='utf-8')
    snapshots = (ALERTS / 'snapshots.py').read_text(encoding='utf-8')
    forbidden = (
        'PrometheusService',
        'get_alertmanager_alerts',
        'get_alertmanager_silences',
        'instant_query(',
    )
    for token in forbidden:
        assert token not in application
        assert token not in snapshots


def test_source_and_snapshot_public_boundaries_remain_available() -> None:
    sources = (ALERTS / 'sources.py').read_text(encoding='utf-8')
    snapshots = (ALERTS / 'snapshots.py').read_text(encoding='utf-8')
    assert 'def load_alerts_by_source(' in sources
    assert 'def normalize_alertmanager_item(' in sources
    assert 'def normalize_prometheus_alert(' in sources
    assert 'def get_alerts_snapshot(' in snapshots


def test_provider_failure_characterization_is_an_explicit_release_gate() -> None:
    source = QUALITY_GATE.read_text(encoding='utf-8')
    assert 'tests/analytics/test_alerts_source_fallback_characterization.py' in source

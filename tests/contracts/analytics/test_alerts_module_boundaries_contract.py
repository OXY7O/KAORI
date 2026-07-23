from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ALERTS = ROOT / 'app' / 'analytics' / 'alerts'
SERVICE = ALERTS / 'service.py'

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


def test_alerts_service_is_a_thin_compatibility_facade() -> None:
    source = SERVICE.read_text(encoding='utf-8')
    tree = ast.parse(source)

    assert len(source.splitlines()) < 220
    assert not [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))]
    assert '__all__' in source
    assert 'get_alerts_context' in source
    assert 'get_alerts_snapshot' in source
    assert 'load_alerts_by_source' in source


def test_alerts_domain_has_explicit_responsibility_modules() -> None:
    existing = {path.name for path in ALERTS.glob('*.py')}

    assert REQUIRED_MODULES <= existing


def test_internal_consumers_use_canonical_alert_modules() -> None:
    offenders: list[str] = []

    for path in (ROOT / 'app').rglob('*.py'):
        if path == SERVICE:
            continue

        source = path.read_text(encoding='utf-8')
        if 'app.analytics.alerts.service' in source:
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

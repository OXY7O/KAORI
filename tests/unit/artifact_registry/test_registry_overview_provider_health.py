from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.artifact_registry.presentation_overview import _provider_health_status, _security_freshness_status


@pytest.mark.parametrize(
    ('readiness', 'status', 'critical', 'high', 'artifacts', 'scanned', 'label'),
    [
        ('ready', 'ready', 0, 0, 10, 0, 'Warning'),
        ('ready', 'ready', 0, 0, 10, 3, 'Warning'),
        ('ready', 'ready', 0, 0, 10, 10, 'Healthy'),
        ('ready', 'ready', 0, 0, 0, 0, 'Healthy'),
        ('ready', 'ready', 1, 0, 10, 10, 'Critical'),
        ('ready', 'ready', 0, 2, 10, 10, 'Warning'),
        ('degraded', 'ready', 0, 0, 10, 10, 'Warning'),
        ('validation_required', 'ready', 0, 0, 10, 10, 'Warning'),
        ('blocked', 'ready', 0, 0, 10, 10, 'Critical'),
    ],
)
def test_provider_composite_health_does_not_hide_unassessed_artifacts(
    readiness: str, status: str, critical: int, high: int,
    artifacts: int, scanned: int, label: str,
) -> None:
    state = SimpleNamespace(status=status, last_error=None)
    actual, tone, reason = _provider_health_status(
        readiness=readiness,
        state=state,
        snapshot={'is_stale': False},
        security={
            'critical': critical, 'high': high,
            'artifacts': artifacts, 'scanned': scanned,
        },
        inventory_ready=True,
    )
    assert actual == label
    assert tone == {'Healthy': 'normal', 'Warning': 'warning', 'Critical': 'critical'}[label]
    assert reason
    if artifacts and scanned < artifacts and not critical and readiness == 'ready':
        assert 'Security scans incomplete' in reason


@pytest.mark.parametrize(
    ('total', 'scanned', 'label'),
    [(0, 0, 'No Artifacts'), (10, 0, 'Required'), (10, 2, 'Partial'), (10, 10, 'Available')],
)
def test_selected_provider_security_freshness_tracks_coverage(
    total: int, scanned: int, label: str,
) -> None:
    from datetime import UTC, datetime

    status, tone, _value = _security_freshness_status(
        artifact_total=total, scanned_count=scanned,
        committed_at=datetime.now(UTC), latest_security_at=datetime.now(UTC) if scanned else None,
    )
    assert status == label
    if label == 'Partial':
        assert tone == 'warning'


def test_security_aggregation_only_counts_successfully_scanned_vulnerabilities() -> None:
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[3] /
        'app/artifact_registry/presentation_overview.py'
    ).read_text(encoding='utf-8')
    grouped = source.split('security_counts_query = (', 1)[1].split('scoped_provider_ids =', 1)[0]
    assert grouped.count("func.lower(RegistryArtifact.scan_status).in_(SUCCESSFUL_REGISTRY_SCAN_STATUSES)") >= 3
    assert "RegistryArtifact.vulnerability_summary['critical'].as_integer()" in grouped
    assert "RegistryArtifact.vulnerability_summary['high'].as_integer()" in grouped

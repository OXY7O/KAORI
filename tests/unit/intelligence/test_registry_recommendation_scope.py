from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from app.intelligence.registry_recommendations import _artifact_evidence, _identity


def _identity_row(*, enabled=True):
    return SimpleNamespace(id=17, name='Registry A', enabled=enabled, lifecycle_status='active', provider_key='harbor', metadata_json={})


def _project():
    return SimpleNamespace(id=10, integration_instance_id=17, name='team-a', public=False)


def _artifact(scan_status: str):
    repository = SimpleNamespace(project=_project(), name='image')
    return SimpleNamespace(
        id=10, repository=repository, digest='sha256:abc',
        tags=[SimpleNamespace(name='stable')],
        scan_status=scan_status,
        vulnerability_summary={'critical': 8, 'high': 15},
        observed_at=datetime(2026, 10, 12, tzinfo=UTC),
    )


def test_unusable_scan_does_not_reuse_old_critical_vulnerability_summary() -> None:
    row = _artifact('failed')
    evidence = _artifact_evidence(
        row, identity=_identity_row(), provider_key='harbor',
        provider_label='Harbor', bindings=[SimpleNamespace(namespace='prod', workload_name='web', pod_name='web-1')],
    )
    assert evidence['critical_count'] == 0
    assert evidence['high_count'] == 0
    assert evidence['runtime_binding_count'] == 1


def test_usable_scan_preserves_normalized_findings() -> None:
    row = _artifact('success')
    evidence = _artifact_evidence(
        row, identity=_identity_row(), provider_key='harbor',
        provider_label='Harbor', bindings=[],
    )
    assert evidence['critical_count'] == 8


def test_unknown_or_disabled_provider_does_not_widen_registry_finding_scope() -> None:
    project = _project()
    assert _identity(project, {})[0] is None
    assert _identity(project, {17: _identity_row(enabled=False)})[0] is None
    provider = _identity_row()
    assert _identity(project, {17: provider})[0] is provider

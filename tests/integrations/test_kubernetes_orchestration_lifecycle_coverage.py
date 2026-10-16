"""Orchestration Registry and Coverage reject inactive canonical sources."""

from types import SimpleNamespace

import pytest

from app.integrations.orchestration.container_orchestrator.frontpage import (
    _build_registry_row,
    _provider_posture,
)
from app.integrations.readiness import resolve_cluster_coverage, source_operational_enabled


def _source(*, active=True, enabled=True, canonical_enabled=True):
    return SimpleNamespace(
        enabled=enabled,
        readiness_status='ready',
        id=14,
        name='Observability',
        integration_instance=SimpleNamespace(
            enabled=canonical_enabled,
            lifecycle_status='active' if active else 'deleting',
        ),
    )


@pytest.mark.parametrize(
    ('active', 'enabled', 'canonical_enabled', 'allowed'),
    [
        (True, True, True, True),
        (False, True, True, False),
        (True, False, True, False),
        (True, True, False, False),
    ],
)
def test_source_operational_gate(active, enabled, canonical_enabled, allowed):
    assert (
        source_operational_enabled(_source(active=active, enabled=enabled, canonical_enabled=canonical_enabled))
        is allowed
    )


def test_downstream_ready_binding_never_overrides_inactive_source():
    binding = SimpleNamespace(enabled=True, validation_status='ready')
    source = _source(active=False)
    assert _provider_posture(source, binding)['status'] != 'ready'
    assert resolve_cluster_coverage(kubernetes_readiness='ready', source=source, binding=binding)['status'] != 'ready'


@pytest.mark.parametrize(
    ('enabled', 'lifecycle', 'expected'),
    [
        (True, 'active', 'ready'),
        (False, 'active', 'blocked'),
        (True, 'deleting', 'blocked'),
        (True, 'disabled', 'blocked'),
    ],
)
def test_registry_api_readiness_checks_canonical_lifecycle(enabled, lifecycle, expected):
    cluster = SimpleNamespace(id='cluster-1', name='one', environment='production')
    canonical = SimpleNamespace(enabled=enabled, lifecycle_status=lifecycle)
    connection = SimpleNamespace(
        id=3,
        integration_instance_id=7,
        integration_instance=canonical,
        cluster=cluster,
        server='https://kube.invalid',
        readiness_status='ready',
        detected_version='v1.31.0',
        compatibility_profile='kubernetes-core-v1',
        last_validated_at=None,
    )
    row = _build_registry_row(connection, bound_sources={})
    assert row['readiness'] == expected
    assert row['inventory_coverage']['status'] == expected
    if expected == 'blocked':
        assert row['coverage_summary']['status'] == 'blocked'

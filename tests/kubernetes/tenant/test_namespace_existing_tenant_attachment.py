from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.kubernetes.tenant.discovery_adoption import (
    validate_existing_tenant_attachment_target,
    validate_namespace_attachment_uid,
)


def _tenant(**changes):
    values = {
        'cluster_id': 'cluster-a',
        'lifecycle_status': 'ready',
        'provider_key': 'native_kubernetes',
        'provider_state': 'native',
        'reconciliation_authority': 'native_kubernetes',
    }
    values.update(changes)
    return SimpleNamespace(**values)


def test_attaching_native_namespace_preserves_existing_cluster_and_authority():
    validate_existing_tenant_attachment_target(
        _tenant(), cluster_id='cluster-a', namespace='sandbox'
    )


@pytest.mark.parametrize(
    ('changes', 'cluster_id', 'namespace'),
    [
        ({'cluster_id': 'cluster-a'}, 'cluster-b', 'sandbox'),
        ({'provider_key': 'capsule'}, 'cluster-a', 'sandbox'),
        ({'provider_state': 'capsule_degraded'}, 'cluster-a', 'sandbox'),
        ({'reconciliation_authority': 'capsule'}, 'cluster-a', 'sandbox'),
        ({'lifecycle_status': 'decommissioning'}, 'cluster-a', 'sandbox'),
        ({}, 'cluster-a', ''),
    ],
)
def test_attachment_fails_closed_on_wrong_tenant_or_cluster(changes, cluster_id, namespace):
    with pytest.raises(ValueError):
        validate_existing_tenant_attachment_target(
            _tenant(**changes), cluster_id=cluster_id, namespace=namespace
        )


@pytest.mark.parametrize(
    ('observed', 'expected'),
    [
        ('new-uid', 'old-uid'),
        ('', 'old-uid'),
        ('uid', ''),
    ],
)
def test_namespace_uid_replacement_is_never_silent(observed, expected):
    with pytest.raises(ValueError, match='UID changed'):
        validate_namespace_attachment_uid(observed_uid=observed, expected_uid=expected)


def test_matching_namespace_uid_is_accepted():
    validate_namespace_attachment_uid(observed_uid='stable-uid', expected_uid='stable-uid')

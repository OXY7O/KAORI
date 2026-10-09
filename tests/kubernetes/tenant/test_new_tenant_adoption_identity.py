from __future__ import annotations

import pytest

from app.kubernetes.tenant.discovery_adoption import validate_adoption_provider_identity


def test_native_and_capsule_adoption_pins_exact_uid_and_version_from_preflight():
    assert validate_adoption_provider_identity(
        expected_uid='provider-generation-1',
        observed_uid='provider-generation-1',
        expected_resource_version='123',
        observed_resource_version='123',
    ) is None


@pytest.mark.parametrize(
    'expected_uid,observed_uid,expected_version,observed_version',
    [
        ('', 'live-uid', '123', '123'),
        ('expected-uid', '', '123', '123'),
        ('expected-uid', 'expected-uid', '', '123'),
        ('expected-uid', 'expected-uid', '123', ''),
        ('previous-generation', 'recreated-generation', '123', '124'),
        ('expected-uid', 'expected-uid', '123', '124'),
    ],
)
def test_new_tenant_adoption_rejects_missing_or_changed_provider_identity(
    expected_uid: str, observed_uid: str,
    expected_version: str, observed_version: str,
):
    with pytest.raises(ValueError, match='UID|resourceVersion'):
        validate_adoption_provider_identity(
            expected_uid=expected_uid,
            observed_uid=observed_uid,
            expected_resource_version=expected_version,
            observed_resource_version=observed_version,
        )


def test_new_tenant_adoption_rolls_back_pending_governance_after_provider_error(monkeypatch):
    from types import SimpleNamespace

    from app.kubernetes.tenant import discovery_adoption as module

    events = []
    session = SimpleNamespace(
        commit=lambda: events.append('commit'),
        rollback=lambda: events.append('rollback'),
    )
    monkeypatch.setattr(module, 'db', SimpleNamespace(session=session))
    monkeypatch.setattr(
        module, '_prepare_adoption',
        lambda _source: SimpleNamespace(provider_key='native_kubernetes'),
    )

    def provider_failure(_context):
        raise ValueError('Provider read-back failed after potential mutation.')

    monkeypatch.setattr(module, '_adopt_native', provider_failure)
    with pytest.raises(ValueError, match='Provider read-back failed'):
        module.adopt_discovered_tenant_committed({'provider_key': 'native_kubernetes'})
    assert events == ['rollback']


def test_new_tenant_adoption_rolls_back_when_database_commit_fails(monkeypatch):
    from types import SimpleNamespace

    from sqlalchemy.exc import IntegrityError

    from app.kubernetes.tenant import discovery_adoption as module

    calls = []

    def failed_commit():
        calls.append('commit')
        raise IntegrityError('INSERT', {}, Exception('conflicting generation'))

    session = SimpleNamespace(
        commit=failed_commit,
        rollback=lambda: calls.append('rollback'),
    )
    monkeypatch.setattr(module, 'db', SimpleNamespace(session=session))
    context = SimpleNamespace(provider_key='capsule', tenant=SimpleNamespace())
    monkeypatch.setattr(module, '_prepare_adoption', lambda _source: context)
    monkeypatch.setattr(
        module, '_adopt_capsule',
        lambda _context: (SimpleNamespace(), None),
    )
    with pytest.raises(ValueError, match='conflicted with committed KAORI state'):
        module.adopt_discovered_tenant_committed({'provider_key': 'capsule'})
    assert calls == ['commit', 'rollback']


@pytest.mark.parametrize(
    ('correlations', 'reason'),
    [
        (None, 'missing or malformed'),
        ([None], 'malformed entries'),
        ([{'name': 'sandbox', 'uid': '', 'resource_version': '7'}], 'name/UID/resourceVersion'),
        ([{'name': 'sandbox', 'uid': 'uid-1', 'resource_version': ''}], 'name/UID/resourceVersion'),
        ([
            {'name': 'sandbox', 'uid': 'uid-1', 'resource_version': '7'},
            {'name': 'sandbox', 'uid': 'uid-2', 'resource_version': '8'},
        ], 'duplicate Namespace correlation'),
    ],
)
def test_capsule_new_tenant_adoption_rejects_incomplete_inventory_before_db_records(
    monkeypatch, correlations, reason,
):
    from types import SimpleNamespace

    from app.kubernetes.tenant import discovery_adoption as module

    def unexpected_creation():
        pytest.fail('Malformed Capsule inventory must fail before constructing any governance record.')

    monkeypatch.setattr(module, 'TenantNamespace', unexpected_creation)
    with pytest.raises(ValueError, match=reason):
        module._capsule_namespace_records(
            SimpleNamespace(), SimpleNamespace(),
            {'correlated_namespaces': correlations},
        )


def test_capsule_new_tenant_adoption_rejects_namespace_owned_by_another_tenant(monkeypatch):
    from types import SimpleNamespace

    from app.kubernetes.tenant import discovery_adoption as module

    cluster = SimpleNamespace(id='cluster-a')
    context = SimpleNamespace(
        cluster=cluster, client=SimpleNamespace(), resource_name='capsule-a',
        expected_provider_uid='tenant-uid', expected_provider_resource_version='5',
    )
    monkeypatch.setattr(module, '_read_capsule_tenant', lambda *_: (
        'v1beta2', {'metadata': {'name': 'capsule-a', 'uid': 'tenant-uid', 'resourceVersion': '5'}},
    ))
    monkeypatch.setattr(module, '_managed_capsule_map', lambda _: {})
    monkeypatch.setattr(
        module, 'observe_capsule_tenant_allocation',
        lambda *_args, **_kwargs: {'correlated_namespaces': [{'name': 'claimed-ns'}]},
    )
    monkeypatch.setattr(
        module, 'qualify_capsule_tenant_adoption',
        lambda **_kwargs: ('capsule', {}),
    )
    monkeypatch.setattr(module, '_apply_capsule_allocation_capability_state', lambda *a, **kw: None)
    monkeypatch.setattr(
        module, '_managed_namespace_map',
        lambda _: {('cluster-a', 'claimed-ns'): object()},
    )

    with pytest.raises(ValueError, match='already belongs to a governed KAORI Tenant'):
        module._adopt_capsule(context)


@pytest.mark.parametrize(
    ('labels', 'reason'),
    [
        ({'app.kubernetes.io/managed-by': 'kaori'}, 'ownership markers'),
        ({'app.kubernetes.io/managed-by': 'KAORI', 'kaori.io/tenant-id': 'old'}, 'ownership markers'),
        ({'kaori.io/tenant-id': 'orphaned-tenant'}, 'ownership markers'),
        ({'kaori.io/environment': 'production'}, 'ownership markers'),
        ({'kaori.io/resource-profile': 'profile-standard'}, 'ownership markers'),
        ({'kaori.io/tenant-id': ''}, 'ownership markers'),
        ({'app.kubernetes.io/managed-by': 'external-controller'}, 'external manager'),
    ],
)
def test_native_discovery_blocks_orphaned_or_foreign_ownership_before_adoption(labels, reason):
    from app.kubernetes.tenant.discovery_service import _native_management

    state, explanation = _native_management(
        namespace='sandbox', labels=labels, managed_record=None,
    )
    assert state == 'Blocked'
    assert reason in explanation


def test_native_discovery_without_claims_remains_a_review_candidate():
    from app.kubernetes.tenant.discovery_service import _native_management

    state, _ = _native_management(namespace='sandbox', labels={}, managed_record=None)
    assert state == 'Discovered'


@pytest.mark.parametrize('labels', [
    {'app.kubernetes.io/managed-by': 'kaori'},
    {'kaori.io/tenant-id': 'former-tenant'},
    {'kaori.io/resource-profile': 'old-profile'},
    {'app.kubernetes.io/managed-by': 'external-controller'},
])
def test_capsule_new_tenant_adoption_blocks_orphaned_or_foreign_cr_before_provider_work(
    monkeypatch, labels,
):
    from types import SimpleNamespace

    from app.kubernetes.tenant import discovery_adoption as module

    context = SimpleNamespace(
        cluster=SimpleNamespace(id='cluster-a'), resource_name='capsule-a',
        client=SimpleNamespace(),
    )
    monkeypatch.setattr(module, '_managed_capsule_map', lambda _: {})
    monkeypatch.setattr(module, '_read_capsule_tenant', lambda *_: (
        'v1beta2',
        {'metadata': {
            'name': 'capsule-a', 'uid': 'capsule-uid', 'resourceVersion': '5',
            'labels': labels,
        }},
    ))

    def forbidden_observation(*args, **kwargs):
        pytest.fail('Blocked Capsule CR must not proceed into provider allocation observation.')

    monkeypatch.setattr(module, 'observe_capsule_tenant_allocation', forbidden_observation)
    with pytest.raises(ValueError, match='ownership markers|external manager'):
        module._adopt_capsule(context)

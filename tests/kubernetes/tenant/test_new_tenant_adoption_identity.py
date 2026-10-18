from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.kubernetes.tenant.discovery_adoption import validate_adoption_provider_identity


def test_native_and_capsule_adoption_pins_exact_uid_and_version_from_preflight():
    assert (
        validate_adoption_provider_identity(
            expected_uid='provider-generation-1',
            observed_uid='provider-generation-1',
            expected_resource_version='123',
            observed_resource_version='123',
        )
        is None
    )


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
    expected_uid: str,
    observed_uid: str,
    expected_version: str,
    observed_version: str,
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
        module,
        '_prepare_adoption',
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
        module,
        '_adopt_capsule',
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
        (
            [
                {'name': 'sandbox', 'uid': 'uid-1', 'resource_version': '7'},
                {'name': 'sandbox', 'uid': 'uid-2', 'resource_version': '8'},
            ],
            'duplicate Namespace correlation',
        ),
    ],
)
def test_capsule_new_tenant_adoption_rejects_incomplete_inventory_before_db_records(
    monkeypatch,
    correlations,
    reason,
):
    from types import SimpleNamespace

    from app.kubernetes.tenant import discovery_adoption as module

    def unexpected_creation():
        pytest.fail('Malformed Capsule inventory must fail before constructing any governance record.')

    monkeypatch.setattr(module, 'TenantNamespace', unexpected_creation)
    with pytest.raises(ValueError, match=reason):
        module._capsule_namespace_records(
            SimpleNamespace(),
            SimpleNamespace(),
            {'correlated_namespaces': correlations},
        )


def test_capsule_new_tenant_adoption_rejects_namespace_owned_by_another_tenant(monkeypatch):
    from types import SimpleNamespace

    from app.kubernetes.tenant import discovery_adoption as module

    cluster = SimpleNamespace(id='cluster-a')
    context = SimpleNamespace(
        cluster=cluster,
        client=SimpleNamespace(),
        resource_name='capsule-a',
        expected_provider_uid='tenant-uid',
        expected_provider_resource_version='5',
    )
    monkeypatch.setattr(
        module,
        '_read_capsule_tenant',
        lambda *_: (
            'v1beta2',
            {'metadata': {'name': 'capsule-a', 'uid': 'tenant-uid', 'resourceVersion': '5'}},
        ),
    )
    monkeypatch.setattr(module, '_managed_capsule_map', lambda _: {})
    monkeypatch.setattr(
        module,
        'observe_capsule_tenant_allocation',
        lambda *_args, **_kwargs: {'correlated_namespaces': [{'name': 'claimed-ns'}]},
    )
    monkeypatch.setattr(
        module,
        'qualify_capsule_tenant_adoption',
        lambda **_kwargs: ('capsule', {}),
    )
    monkeypatch.setattr(module, '_apply_capsule_allocation_capability_state', lambda *a, **kw: None)
    monkeypatch.setattr(
        module,
        '_managed_namespace_map',
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
        ({'kaori.io/tenant-generation': '3'}, 'ownership markers'),
        ({'kaori.io/tenant-id': ''}, 'ownership markers'),
        ({'app.kubernetes.io/managed-by': 'external-controller'}, 'external manager'),
    ],
)
def test_native_discovery_blocks_orphaned_or_foreign_ownership_before_adoption(labels, reason):
    from app.kubernetes.tenant.discovery_service import _native_management

    state, explanation = _native_management(
        namespace='sandbox',
        labels=labels,
        managed_record=None,
    )
    assert state == 'Blocked'
    assert reason in explanation


def test_post_handback_discovery_requires_resource_profile_marker_absent():
    from app.kubernetes.tenant.discovery_service import _native_management

    # Handback removes the successor owner, but orphaned KAORI profile
    # governance still blocks Discovery until separately verified.
    status, reason = _native_management(
        namespace='tenant-uat-demo',
        labels={
            'environment': 'uat',
            'kaori.io/resource-profile': 'profile-v4',
        },
        managed_record=None,
    )
    assert status == 'Blocked'
    assert 'ownership markers' in reason
    status, _ = _native_management(
        namespace='tenant-uat-demo',
        labels={
            'environment': 'uat',
            'kubernetes.io/metadata.name': 'tenant-uat-demo',
        },
        managed_record=None,
    )
    assert status == 'Discovered'


def test_native_discovery_without_claims_remains_a_review_candidate():
    from app.kubernetes.tenant.discovery_service import _native_management

    state, _ = _native_management(namespace='sandbox', labels={}, managed_record=None)
    assert state == 'Discovered'


@pytest.mark.parametrize(
    'labels',
    [
        {'app.kubernetes.io/managed-by': 'kaori'},
        {'kaori.io/tenant-id': 'former-tenant'},
        {'kaori.io/resource-profile': 'old-profile'},
        {'kaori.io/tenant-generation': '2'},
        {'app.kubernetes.io/managed-by': 'external-controller'},
    ],
)
def test_capsule_new_tenant_adoption_blocks_orphaned_or_foreign_cr_before_provider_work(
    monkeypatch,
    labels,
):
    from types import SimpleNamespace

    from app.kubernetes.tenant import discovery_adoption as module

    context = SimpleNamespace(
        cluster=SimpleNamespace(id='cluster-a'),
        resource_name='capsule-a',
        client=SimpleNamespace(),
    )
    monkeypatch.setattr(module, '_managed_capsule_map', lambda _: {})
    monkeypatch.setattr(
        module,
        '_read_capsule_tenant',
        lambda *_: (
            'v1beta2',
            {
                'metadata': {
                    'name': 'capsule-a',
                    'uid': 'capsule-uid',
                    'resourceVersion': '5',
                    'labels': labels,
                }
            },
        ),
    )

    def forbidden_observation(*args, **kwargs):
        pytest.fail('Blocked Capsule CR must not proceed into provider allocation observation.')

    monkeypatch.setattr(module, 'observe_capsule_tenant_allocation', forbidden_observation)
    with pytest.raises(ValueError, match='ownership markers|external manager'):
        module._adopt_capsule(context)


@pytest.mark.parametrize(
    ('labels', 'references'),
    [
        ({'capsule.clastix.io/tenant': 'capsule-a'}, None),
        ({'projectcapsule.dev/tenant': ''}, None),
        ({}, [SimpleNamespace(kind='Tenant', api_version='capsule.clastix.io/v1beta2')]),
        ({}, [SimpleNamespace(kind='Tenant', api_version='capsule.clastix.io/v1beta1')]),
        ({}, {'malformed': 'references'}),
    ],
)
def test_native_discovery_blocks_capsule_owned_namespaces(labels, references):
    from app.kubernetes.tenant.discovery_service import _native_management

    status, reason = _native_management(
        namespace='capsule-owned',
        labels=labels,
        managed_record=None,
        owner_references=references,
    )
    assert status == 'Blocked'
    assert 'Capsule Tenant authority' in reason


def test_native_discovery_accepts_namespaces_without_capsule_authority():
    from types import SimpleNamespace

    from app.kubernetes.tenant.discovery_service import _native_management

    state, _ = _native_management(
        namespace='native-only',
        labels={},
        managed_record=None,
        owner_references=[SimpleNamespace(kind='ReplicaSet', api_version='apps/v1')],
    )
    assert state == 'Discovered'


@pytest.mark.parametrize(
    ('authority', 'capability', 'preview_only', 'eligible'),
    [
        ('none_observed', None, True, True),
        ('none_observed', None, False, True),
        ('native_namespaced', None, True, False),
        ('native_namespaced', None, False, False),
        ('ambiguous', None, True, False),
        ('capsule_tenant_resource_quotas', 'tenant_resource_quotas', True, True),
        ('capsule_tenant_resource_quotas', 'tenant_resource_quotas', False, True),
        ('capsule_global_resource_quota', 'shared_global_quota', True, True),
        ('capsule_global_resource_quota', 'shared_global_quota', False, True),
        ('capsule_global_resource_quota', None, True, False),
        ('capsule_tenant_resource_quotas', None, False, False),
        ('capsule_tenant_resource_quotas', 'shared_global_quota', False, False),
    ],
)
def test_capsule_managed_adoption_requires_the_correct_quota_capability(
    authority: str, capability: str | None, preview_only: bool, eligible: bool
):
    from app.kubernetes.tenant.discovery_service import capsule_managed_adoption_blocker

    allocation = {
        'allocation_authority': authority,
        'control_state': 'observed',
        'shared_quota': {} if authority == 'none_observed' else {'limits.cpu': '4'},
        'authority_unsupported_dimensions': [],
        'authority_ambiguous_dimensions': [],
        'capability_preview': capability if preview_only else None,
        'admitted_capability': capability if not preview_only else None,
    }
    reason = capsule_managed_adoption_blocker(allocation, preview_only=preview_only)
    assert (reason is None) is eligible
    if authority == 'native_namespaced':
        assert 'Native quota cannot substitute' in reason


@pytest.mark.parametrize('field', ['authority_unsupported_dimensions', 'authority_ambiguous_dimensions'])
def test_capsule_adoption_blocks_unsupported_or_competing_authority(field: str):
    from app.kubernetes.tenant.discovery_service import capsule_managed_adoption_blocker

    allocation = {
        'allocation_authority': 'capsule_tenant_resource_quotas',
        'control_state': 'observed',
        'admitted_capability': 'tenant_resource_quotas',
        field: ['unsupported evidence'],
    }
    assert capsule_managed_adoption_blocker(allocation, preview_only=False) is not None


def test_capsule_managed_adoption_rejects_namespaced_only_quota_before_records(monkeypatch):
    from app.kubernetes.tenant import discovery_adoption as module

    context = SimpleNamespace(
        cluster=SimpleNamespace(id='cluster-a'),
        client=SimpleNamespace(),
        resource_name='kaori-adopt-lab-v2',
        expected_provider_uid='provider-uid',
        expected_provider_resource_version='18',
    )
    monkeypatch.setattr(module, '_managed_capsule_map', lambda _: {})
    monkeypatch.setattr(
        module,
        '_read_capsule_tenant',
        lambda *_: (
            'v1beta2',
            {
                'metadata': {
                    'name': 'kaori-adopt-lab-v2',
                    'uid': 'provider-uid',
                    'resourceVersion': '18',
                    'labels': {},
                },
            },
        ),
    )
    monkeypatch.setattr(
        module,
        'observe_capsule_tenant_allocation',
        lambda *_args, **_kwargs: {
            'allocation_authority': 'native_namespaced',
            'control_state': 'observed',
            'shared_quota': {},
            'authority_unsupported_dimensions': [],
            'authority_ambiguous_dimensions': [],
        },
    )
    monkeypatch.setattr(module, 'qualify_capsule_tenant_adoption', lambda **_: ('capsule', {}))

    def must_not_create(*_args, **_kwargs):
        pytest.fail('Unadmitted quota must fail before allocating governance rows or provider writes.')

    monkeypatch.setattr(module, '_capsule_namespace_records', must_not_create)
    monkeypatch.setattr(module, '_managed_namespace_map', must_not_create)
    with pytest.raises(ValueError, match='Native quota cannot substitute'):
        module._adopt_capsule(context)

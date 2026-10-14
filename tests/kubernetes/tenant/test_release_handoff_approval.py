from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.kubernetes.tenant.capsule_handoff_related_inventory import _digest, capsule_related_scope_sha256
from app.kubernetes.tenant.release_handoff_approval import (
    _can_confirm_plan,
    _complete_provider_snapshot,
    _plan_hash,
    _require_no_active_handoff_plan,
    _valid_reference,
    approve_release_handoff_plan_committed,
    handoff_plan_preparation_state,
    prepare_release_handoff_plan_committed,
)
from app.kubernetes.tenant.release_handoff_inventory import handoff_fingerprint
from app.kubernetes.tenant.release_preflight import _release_blockers


def _snapshot(*, status: str = 'blocked', blockers: list[str] | None = None) -> dict:
    snapshot = {
        'tenant_id': 'tenant-a',
        'cluster_id': 'cluster-a',
        'generation': 2,
        'provider': 'native_kubernetes',
        'status': status,
        'checked_at': datetime.now(UTC).isoformat(),
        'handoff_fingerprint': '',
        'live_provider_identity': [
            {
                'kind': 'Namespace',
                'name': 'sandbox',
                'uid': 'namespace-uid',
                'resource_version': '5',
            }
        ],
        'handoff_components': [
            {
                'kind': 'Namespace',
                'name': 'sandbox',
                'uid': 'namespace-uid',
                'resource_version': '5',
                'handoff': 'external_acceptance_required',
                'ownership': 'kaori_marker_correlated',
            }
        ],
        'handoff_required_count': 1,
        'dependency_counts': {
            'Access Grants': 0,
            'credentials': 0,
            'Memberships': 0,
            'enabled Groups': 0,
            'advanced capabilities': 0,
            'managed resources': 0,
            'domain reservations': 0,
            'exposure policies': 0,
        },
        'blockers': blockers
        if blockers is not None
        else [
            'Adoption performed KAORI-owned provider mutations. '
            'Complete independently verified allocation/policy handoff before Release.',
            'sandbox KAORI-linked allocation ownership requires independently approved '
            'external handoff and provider read-back.',
        ],
    }
    snapshot['handoff_fingerprint'] = handoff_fingerprint(snapshot['handoff_components'])
    return snapshot


def _plan_from_snapshot(snapshot: dict) -> dict:
    plan = {
        'status': 'pending_independent_approval',
        'tenant_id': snapshot['tenant_id'],
        'cluster_id': snapshot['cluster_id'],
        'generation': snapshot['generation'],
        'provider': snapshot['provider'],
        'handoff_fingerprint': snapshot['handoff_fingerprint'],
        'provider_identity': snapshot['live_provider_identity'],
        'successor_owner': 'platform-team',
        'change_reference': 'CHG-2026-109',
        'requested_by': 42,
        'requested_at': datetime.now(UTC).isoformat(),
    }
    plan['plan_sha256'] = _plan_hash(plan)
    return plan


def test_handoff_plan_acceptance_requires_only_expected_handoff_blockers():
    _can_confirm_plan(_snapshot())


def _capsule_g1_snapshot() -> dict:
    origin_warning = (
        'Capsule controller-generated RoleBinding origins and provider handoff remain unverified; executor is blocked.'
    )
    snapshot = _snapshot(blockers=[origin_warning])
    snapshot['provider'] = 'capsule'
    snapshot['live_provider_identity'] = [
        {'kind': 'CapsuleTenant', 'name': 'demo', 'uid': 'cr-uid', 'resource_version': '5'},
        {'kind': 'Namespace', 'name': 'sandbox', 'uid': 'ns-uid', 'resource_version': '6'},
    ]
    snapshot['handoff_components'] = [
        {
            'kind': 'CapsuleTenant',
            'name': 'demo',
            'uid': 'cr-uid',
            'resource_version': '5',
            'authority': 'capsule',
            'handoff': 'external_acceptance_required',
            'capsule_spec_sha256': 'a' * 64,
            'capsule_related_resources_sha256': 'b' * 64,
            'capsule_shared_quota_sha256': 'c' * 64,
            'capsule_rbac_lineage_sha256': 'd' * 64,
        },
        {
            'kind': 'Namespace',
            'name': 'sandbox',
            'namespace': 'sandbox',
            'uid': 'ns-uid',
            'resource_version': '6',
            'authority': 'capsule',
            'handoff': 'observe_only',
        },
    ]
    snapshot['handoff_required_count'] = 1
    snapshot['handoff_fingerprint'] = handoff_fingerprint(snapshot['handoff_components'])
    snapshot['capsule_related_inventory'] = {
        'status': 'read_only_related_inventory',
        'resources': [],
        'list_snapshots': [],
        'resource_sha256': 'b' * 64,
        'blockers': [],
        'global_quota': {'scope_sha256': 'c' * 64, 'blockers': []},
        'rbac_lineage': {'lineage_sha256': 'd' * 64, 'blockers': []},
    }
    return snapshot


@pytest.mark.parametrize(
    ('field', 'value', 'expected'),
    [
        ('capsule_related_resources_sha256', 'e', 'quota/limit/RBAC scope digest'),
        ('capsule_shared_quota_sha256', 'e', 'GlobalResourceQuota scope digest'),
        ('capsule_rbac_lineage_sha256', 'e', 'Capsule RBAC lineage digest'),
        ('capsule_spec_sha256', 'e', 'Capsule Tenant spec digest'),
        ('resource_version', '30', 'provider object resourceVersion'),
        ('uid', 'replacement-cr', 'provider resource identity'),
        ('handoff', 'observe_only', 'ownership or handoff classification'),
    ],
)
def test_capsule_g1_approval_drift_diagnostic_identifies_changed_scope_without_waiver(
    field,
    value,
    expected,
):
    from app.kubernetes.tenant.release_handoff_approval import (
        _handoff_approval_drift_categories,
        _handoff_approval_drift_message,
    )

    original = _capsule_g1_snapshot()
    plan = {
        **_plan_from_snapshot(original),
        'handoff_components': deepcopy(original['handoff_components']),
    }
    changed = deepcopy(original)
    changed['handoff_components'][0][field] = value * 64 if field.endswith('_sha256') else value
    changed['handoff_fingerprint'] = handoff_fingerprint(changed['handoff_components'])
    categories = _handoff_approval_drift_categories(plan=plan, fresh=changed)
    assert any(expected in label for label in categories)
    message = _handoff_approval_drift_message(plan=plan, fresh=changed)
    assert expected in message
    assert 'prepare a new plan' in message
    assert len(message) < 300
    # Diagnosing a revised provider scope must never approve changed evidence.
    assert plan['handoff_fingerprint'] != changed['handoff_fingerprint']


def test_capsule_g1_approval_diagnostic_identifies_changed_list_scope_without_policy_exposure():
    from app.kubernetes.tenant.release_handoff_approval import (
        _handoff_approval_drift_categories,
        _handoff_approval_drift_message,
    )

    original = _capsule_g1_snapshot()
    plan = {
        **_plan_from_snapshot(original),
        'handoff_components': deepcopy(original['handoff_components']),
    }
    assert _handoff_approval_drift_categories(plan=plan, fresh=original) == ()
    changing = deepcopy(original)
    changing['handoff_components'][0]['capsule_related_resources_sha256'] = 'f' * 64
    changing['handoff_components'][0]['capsule_shared_quota_sha256'] = 'e' * 64
    changing['handoff_fingerprint'] = handoff_fingerprint(changing['handoff_components'])
    changing['capsule_related_inventory']['resources'].append({'subject': 'PRIVATE_SUBJECT_DO_NOT_EXPOSE'})
    message = _handoff_approval_drift_message(plan=plan, fresh=changing)
    assert 'quota/limit/RBAC scope digest' in message
    assert 'GlobalResourceQuota scope digest' in message
    assert 'PRIVATE_SUBJECT' not in message
    assert 'v1beta2' not in message


def test_capsule_g1_approval_changed_identity_is_never_accepted_by_safe_diagnostic():
    from app.kubernetes.tenant.release_handoff_approval import (
        _handoff_approval_drift_categories,
    )

    snapshot = _capsule_g1_snapshot()
    plan = {
        **_plan_from_snapshot(snapshot),
        'handoff_components': deepcopy(snapshot['handoff_components']),
    }
    drifted = deepcopy(snapshot)
    drifted['live_provider_identity'][0]['resource_version'] = '17'
    assert 'provider object resourceVersion' in _handoff_approval_drift_categories(
        plan=plan,
        fresh=drifted,
    )
    assert plan['provider_identity'] != drifted['live_provider_identity']
    drifted['live_provider_identity'].append(
        {
            'kind': 'RoleBinding',
            'name': 'unexpected',
            'uid': 'rb-uid',
            'resource_version': '9',
        }
    )
    assert 'provider resource identity or coverage' in _handoff_approval_drift_categories(
        plan=plan,
        fresh=drifted,
    )


def test_capsule_g1_plan_fingerprint_stays_identical_when_only_list_rvs_advance():
    """Two complete provider LISTs may have new collection revisions, not new objects."""
    from copy import deepcopy

    snapshot = _capsule_g1_snapshot()
    related = snapshot['capsule_related_inventory']
    related['list_snapshots'] = [
        {
            'namespace': 'sandbox',
            'kind': kind,
            'list_resource_version': 'list-100',
            'count': 0,
        }
        for kind in ('ResourceQuota', 'LimitRange', 'RoleBinding')
    ]
    related['resource_sha256'] = capsule_related_scope_sha256(
        resources=related['resources'],
        list_snapshots=related['list_snapshots'],
    )
    cr = snapshot['handoff_components'][0]
    cr['capsule_related_resources_sha256'] = related['resource_sha256']
    cr['capsule_related_resources_count'] = '0'
    shared = {'api_version': 'v1beta2', 'resources': []}
    related['global_quota'].update(
        {
            'status': 'observed_not_handoff_authorized',
            'served_version': 'v1beta2',
            'resources': [],
            'count': 0,
            'list_resource_version': 'global-100',
            'scope_sha256': _digest(shared),
        }
    )
    cr['capsule_shared_quota_sha256'] = related['global_quota']['scope_sha256']
    snapshot['handoff_fingerprint'] = handoff_fingerprint(snapshot['handoff_components'])
    _can_confirm_plan(snapshot)
    prepared = _plan_from_snapshot(snapshot)

    fresh = deepcopy(snapshot)
    for row in fresh['capsule_related_inventory']['list_snapshots']:
        row['list_resource_version'] = 'list-200'
    fresh['capsule_related_inventory']['global_quota']['list_resource_version'] = 'global-200'
    _can_confirm_plan(fresh)
    assert fresh['handoff_fingerprint'] == prepared['handoff_fingerprint']
    assert fresh['live_provider_identity'] == prepared['provider_identity']
    assert fresh['handoff_components'] == snapshot['handoff_components']
    assert _plan_hash(prepared) == prepared['plan_sha256']
    # The preview/executor still reject object identity, policy or owner drift.
    drift = deepcopy(fresh)
    drift['handoff_components'][0]['resource_version'] = 'source-mutated'
    drift['handoff_fingerprint'] = handoff_fingerprint(drift['handoff_components'])
    assert drift['handoff_fingerprint'] != prepared['handoff_fingerprint']


def test_capsule_g1_can_consent_to_known_executor_origin_obligation_only():
    # Independent consent is not a G2/G3 permission to PATCH or Release.
    _can_confirm_plan(_capsule_g1_snapshot())


@pytest.mark.parametrize(
    'change',
    [
        'native',
        'missing_inventory',
        'stale_related_digest',
        'quota_incomplete',
        'rbac_conflict',
        'extra_unknown_blocker',
    ],
)
def test_capsule_g1_does_not_waive_other_provider_or_dependency_failures(change):
    snapshot = _capsule_g1_snapshot()
    if change == 'native':
        snapshot['provider'] = 'native_kubernetes'
    elif change == 'missing_inventory':
        snapshot.pop('capsule_related_inventory')
    elif change == 'stale_related_digest':
        snapshot['capsule_related_inventory']['resource_sha256'] = 'f' * 64
    elif change == 'quota_incomplete':
        snapshot['capsule_related_inventory']['global_quota']['blockers'] = ['missing GRQ']
    elif change == 'rbac_conflict':
        snapshot['capsule_related_inventory']['rbac_lineage']['blockers'] = ['RBAC drift']
    elif change == 'extra_unknown_blocker':
        snapshot['blockers'].append('Capsule Namespace provider UID mismatch.')
    with pytest.raises(ValueError, match='Unresolved provider'):
        _can_confirm_plan(snapshot)


def _capsule_g1_related_kaori_control_snapshot() -> dict:
    snapshot = _capsule_g1_snapshot()
    related = snapshot['capsule_related_inventory']
    warning = (
        'Capsule ResourceQuota/sandbox/managed-quota retains KAORI provider '
        'controls requiring separately admitted handoff.'
    )
    related['resources'] = [
        {
            'kind': 'ResourceQuota',
            'namespace': 'sandbox',
            'name': 'managed-quota',
            'uid': 'quota-uid',
            'resource_version': '8',
            'origin': 'kaori_correlated',
            'policy_sha256': 'e' * 64,
            'metadata_sha256': 'f' * 64,
        }
    ]
    related['resource_count'] = 1
    related['list_snapshots'] = [
        {
            'kind': kind,
            'namespace': 'sandbox',
            'list_resource_version': 'list-rv',
            'count': 1 if kind == 'ResourceQuota' else 0,
        }
        for kind in ('ResourceQuota', 'LimitRange', 'RoleBinding')
    ]
    related['resource_sha256'] = capsule_related_scope_sha256(
        resources=related['resources'],
        list_snapshots=related['list_snapshots'],
    )
    related['blockers'] = [warning]
    related['global_quota'].update(
        {
            'served_version': 'v1beta2',
            'list_resource_version': 'quota-list',
            'resources': [],
            'count': 0,
        }
    )
    related['global_quota']['scope_sha256'] = _digest(
        {
            'api_version': 'v1beta2',
            'resources': [],
        }
    )
    cr = snapshot['handoff_components'][0]
    cr['ownership'] = 'external_or_unattributed'
    snapshot['handoff_components'][1]['ownership'] = 'external_or_unattributed'
    cr['capsule_related_resources_sha256'] = related['resource_sha256']
    cr['capsule_shared_quota_sha256'] = related['global_quota']['scope_sha256']
    cr['capsule_related_resources_count'] = '1'
    snapshot['handoff_fingerprint'] = handoff_fingerprint(snapshot['handoff_components'])
    snapshot['blockers'].append(warning)
    return snapshot


def test_capsule_g1_recognizes_related_warning_and_executor_warning_separately():
    snapshot = _capsule_g1_related_kaori_control_snapshot()
    from app.kubernetes.tenant.release_handoff_approval import (
        _capsule_g1_only_origin_obligation,
    )

    assert len(snapshot['blockers']) == 2
    assert all(_capsule_g1_only_origin_obligation(snapshot, reason) for reason in snapshot['blockers'])
    assert not _capsule_g1_only_origin_obligation(
        snapshot,
        'Capsule foreign owner requires verification.',
    )


def test_capsule_g1_allows_real_sha_bound_kaori_related_obligation_without_granting_execution():
    snapshot = _capsule_g1_related_kaori_control_snapshot()
    _can_confirm_plan(snapshot)
    assert snapshot['blockers']  # G2/G3 still have the exact origin + handoff warnings.


@pytest.mark.parametrize(
    'field',
    [
        'unattributed',
        'related_digest_drift',
        'unknown_extra_finding',
        'missing_list',
    ],
)
def test_capsule_g1_refuses_incomplete_or_unknown_related_scope(field):
    snapshot = _capsule_g1_related_kaori_control_snapshot()
    related = snapshot['capsule_related_inventory']
    if field == 'unattributed':
        related['resources'][0]['origin'] = 'unattributed'
    elif field == 'related_digest_drift':
        related['resource_sha256'] = 'a' * 64
    elif field == 'unknown_extra_finding':
        related['blockers'].append('RoleBinding subject owner unverified.')
    elif field == 'missing_list':
        related['list_snapshots'].pop()
    with pytest.raises(ValueError, match='Unresolved provider'):
        _can_confirm_plan(snapshot)


def test_resource_profile_allocation_preflight_copy_is_approved_handoff_obligation():
    """The actual managed-allocation blocker is not a new provider-identity failure."""
    tenant = SimpleNamespace(
        ownership_status='adopted',
        lifecycle_status='ready',
        provider_state='native',
        provider_key='native_kubernetes',
        reconciliation_authority='native_kubernetes',
        provider_evidence_json={'provider_mutation_performed': False},
    )
    namespace = SimpleNamespace(
        namespace='sandbox',
        provisioning_status='ready',
        ownership_status='adopted',
        provisioning_evidence_json={'provider_mutation_performed': False},
        resource_profile_id=12,
    )
    blockers = _release_blockers(tenant, [namespace], counts={})
    assert len(blockers) == 1
    assert 'has a KAORI-managed Resource Profile allocation.' in blockers[0]
    assert 'independent approval, verified provider handoff and read-back' in blockers[0]
    # Expected provider handoff is an obligation, not a waiver of any other gate.
    _can_confirm_plan(_snapshot(blockers=blockers))

    with pytest.raises(ValueError, match='Unresolved provider'):
        _can_confirm_plan(
            _snapshot(
                blockers=[
                    *blockers,
                    'Namespace/sandbox provider UID mismatch.',
                ]
            )
        )
    with pytest.raises(ValueError, match='Unresolved provider'):
        _can_confirm_plan(
            _snapshot(
                blockers=[
                    'sandbox has a KAORI-managed allocation linked to a Resource Profile. '
                    'Provider evidence missing; investigate before approving.',
                ]
            )
        )


def test_proven_namespace_mutation_requires_handoff_but_unknown_provenance_blocks_plan():
    approved_handoff_blocker = (
        'sandbox has KAORI-mutated Namespace provider controls; independently approved external handoff is required.'
    )
    _can_confirm_plan(_snapshot(blockers=[approved_handoff_blocker]))

    with pytest.raises(ValueError, match='Unresolved'):
        _can_confirm_plan(
            _snapshot(
                blockers=[
                    'sandbox has missing or unverified provider mutation provenance; '
                    'investigate before approving handoff.'
                ]
            )
        )


@pytest.mark.parametrize(
    'blocker',
    [
        'Namespace/sandbox provider UID mismatch.',
        'External Capsule access observation is stale.',
        'Native provider is unavailable.',
        'sandbox allocation hash changed since committed KAORI evidence.',
        'sandbox has inconsistent provider ownership markers.',
    ],
)
def test_handoff_approval_blocks_other_governance_or_provider_failures(blocker):
    with pytest.raises(ValueError, match='Unresolved'):
        _can_confirm_plan(_snapshot(blockers=[blocker]))


def test_handoff_approval_rejects_active_dependencies():
    snapshot = _snapshot()
    snapshot['dependency_counts']['Access Grants'] = 1
    with pytest.raises(ValueError, match='Clear and verify every active Tenant dependency'):
        _can_confirm_plan(snapshot)


def test_handoff_approval_rejects_foreign_or_unverified_ownership():
    snapshot = _snapshot()
    snapshot['handoff_components'][0]['handoff'] = 'owner_review_required'
    snapshot['handoff_fingerprint'] = handoff_fingerprint(snapshot['handoff_components'])
    with pytest.raises(ValueError, match='Conflicting provider ownership'):
        _can_confirm_plan(snapshot)

    snapshot['handoff_components'][0]['handoff'] = 'observe_only'
    snapshot['handoff_fingerprint'] = handoff_fingerprint(snapshot['handoff_components'])
    snapshot['handoff_required_count'] = 0
    with pytest.raises(ValueError, match='No verified KAORI-linked resource'):
        _can_confirm_plan(snapshot)


def test_handoff_evidence_requires_all_correlated_namespace_identities():
    snapshot = _snapshot()
    snapshot['live_provider_identity'].append(
        {
            'kind': 'Namespace',
            'name': 'second',
            'uid': 'other',
            'resource_version': '1',
        }
    )
    with pytest.raises(ValueError, match='coverage'):
        _complete_provider_snapshot(snapshot)


@pytest.mark.parametrize('duplicate_target', ['provider_identity', 'handoff_component'])
def test_handoff_rejects_ambiguous_duplicate_provider_identity(duplicate_target):
    snapshot = _snapshot()
    if duplicate_target == 'provider_identity':
        snapshot['live_provider_identity'].append(
            {
                **snapshot['live_provider_identity'][0],
                'uid': 'replacement-generation',
            }
        )
    else:
        snapshot['handoff_components'].append(
            {
                **snapshot['handoff_components'][0],
                'uid': 'replacement-generation',
            }
        )
        snapshot['handoff_fingerprint'] = handoff_fingerprint(snapshot['handoff_components'])
    with pytest.raises(ValueError, match='duplicated or ambiguous'):
        _complete_provider_snapshot(snapshot)


def test_handoff_evidence_rejects_stale_and_incomplete_provider_metadata():
    snapshot = _snapshot()
    snapshot['checked_at'] = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    with pytest.raises(ValueError, match='Refresh'):
        _complete_provider_snapshot(snapshot)

    snapshot = _snapshot()
    snapshot['handoff_components'][0]['uid'] = ''
    with pytest.raises(ValueError, match='incomplete'):
        _complete_provider_snapshot(snapshot)


def test_handoff_owner_and_change_references_are_bounded_and_nonsecret():
    assert _valid_reference('platform-team', name='Successor') == 'platform-team'
    assert _valid_reference('CHG-2026-109', name='Change') == 'CHG-2026-109'
    for value in ('', 'ab', 'space separated', '<script>', 'x' * 121):
        with pytest.raises(ValueError):
            _valid_reference(value, name='Successor')


def test_second_approver_cannot_be_handoff_requester(monkeypatch):
    from app.kubernetes.tenant import release_handoff_approval as module

    plan = _plan_from_snapshot(_snapshot())
    monkeypatch.setattr(module, 'latest_release_handoff_plan', lambda _: plan)
    with pytest.raises(ValueError, match='independent approver'):
        approve_release_handoff_plan_committed(
            tenant_id='tenant-a',
            actor_user_id=42,
            plan_sha256=plan['plan_sha256'],
            approved=True,
        )


def test_second_approver_requires_same_latest_plan_and_fresh_window(monkeypatch):
    from app.kubernetes.tenant import release_handoff_approval as module

    plan = _plan_from_snapshot(_snapshot())
    monkeypatch.setattr(module, 'latest_release_handoff_plan', lambda _: plan)
    with pytest.raises(ValueError, match='plan changed'):
        approve_release_handoff_plan_committed(
            tenant_id='tenant-a',
            actor_user_id=43,
            plan_sha256='b' * 64,
            approved=True,
        )
    plan['requested_at'] = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
    plan['plan_sha256'] = _plan_hash(plan)
    with pytest.raises(ValueError, match='expired'):
        approve_release_handoff_plan_committed(
            tenant_id='tenant-a',
            actor_user_id=43,
            plan_sha256=plan['plan_sha256'],
            approved=True,
        )


def test_second_approver_requires_explicit_acknowledgement():
    with pytest.raises(ValueError, match='acknowledgement'):
        approve_release_handoff_plan_committed(
            tenant_id='tenant-a',
            actor_user_id=43,
            plan_sha256='a' * 64,
            approved=False,
        )


class _FakeSession:
    def __init__(self, tenant=None):
        self.tenant = tenant
        self.events = []
        self.commits = 0

    def get(self, model, tenant_id):
        return self.tenant

    def add(self, event):
        self.events.append(event)

    def commit(self):
        self.commits += 1


def test_prepare_handoff_commits_plan_without_provider_mutation(monkeypatch):
    from app.kubernetes.tenant import release_handoff_approval as module

    tenant = SimpleNamespace(ownership_status='adopted', lifecycle_status='ready')

    class _TenantQuery:
        def filter_by(self, **kwargs):
            return self

        def with_for_update(self):
            return self

        def one_or_none(self):
            return tenant

    session = _FakeSession(tenant)
    monkeypatch.setattr(module, 'db', SimpleNamespace(session=session))
    monkeypatch.setattr(module, 'Tenant', SimpleNamespace(query=_TenantQuery()))
    monkeypatch.setattr(module, 'AuditEvent', lambda **kwargs: SimpleNamespace(**kwargs))
    monkeypatch.setattr(module, 'review_tenant_release_preflight_committed', lambda **_: _snapshot())
    monkeypatch.setattr(module, 'latest_release_handoff_plan', lambda _: None)
    monkeypatch.setattr(module, 'latest_release_handoff_approval', lambda _: None)

    result = prepare_release_handoff_plan_committed(
        tenant_id='tenant-a',
        actor_user_id=42,
        successor_owner='platform-team',
        change_reference='CHG-2026-109',
    )
    assert len(result['plan_sha256']) == 64
    assert result['status'] == 'pending_independent_approval'
    assert result['provider_mutation_performed'] is False
    assert result['provider_handoff_verified'] is False
    assert result['release_authorized'] is False
    assert session.commits == 1
    assert len(session.events) == 1
    assert session.events[0].action == 'tenant.release.handoff_plan_prepared'
    assert session.events[0].target_id == 'tenant-a'


def test_capsule_independent_reviewer_is_blocked_with_safe_drift_category(monkeypatch):
    from app.kubernetes.tenant import release_handoff_approval as module

    original = _capsule_g1_snapshot()
    plan = {
        **_plan_from_snapshot(original),
        'handoff_components': deepcopy(original['handoff_components']),
    }
    changed = deepcopy(original)
    changed['handoff_components'][0]['capsule_spec_sha256'] = 'e' * 64
    changed['handoff_fingerprint'] = handoff_fingerprint(changed['handoff_components'])

    class _Query:
        def filter_by(self, **kwargs):
            return self

        def with_for_update(self):
            return self

        def one_or_none(self):
            return SimpleNamespace(lifecycle_status='ready', ownership_status='adopted')

    session = _FakeSession()
    monkeypatch.setattr(module, 'db', SimpleNamespace(session=session))
    monkeypatch.setattr(module, 'Tenant', SimpleNamespace(query=_Query()))
    monkeypatch.setattr(module, 'latest_release_handoff_plan', lambda _: plan)
    monkeypatch.setattr(module, 'latest_release_handoff_approval', lambda _: None)
    monkeypatch.setattr(
        module,
        'review_tenant_release_preflight_committed',
        lambda **_: changed,
    )
    with pytest.raises(ValueError, match='Capsule Tenant spec digest'):
        approve_release_handoff_plan_committed(
            tenant_id='tenant-a',
            actor_user_id=43,
            plan_sha256=plan['plan_sha256'],
            approved=True,
        )
    assert session.events == []
    assert session.commits == 0


def test_independent_handoff_approval_commits_pending_provider_state(monkeypatch):
    from app.kubernetes.tenant import release_handoff_approval as module

    snapshot = _snapshot()
    plan = _plan_from_snapshot(snapshot)

    class _Query:
        def filter_by(self, **kwargs):
            return self

        def with_for_update(self):
            return self

        def one_or_none(self):
            return SimpleNamespace(lifecycle_status='ready', ownership_status='adopted')

    session = _FakeSession()
    monkeypatch.setattr(module, 'db', SimpleNamespace(session=session))
    monkeypatch.setattr(module, 'Tenant', SimpleNamespace(query=_Query()))
    monkeypatch.setattr(module, 'AuditEvent', lambda **kwargs: SimpleNamespace(**kwargs))
    monkeypatch.setattr(module, 'latest_release_handoff_plan', lambda _: plan)
    monkeypatch.setattr(module, 'latest_release_handoff_approval', lambda _: None)
    monkeypatch.setattr(module, 'review_tenant_release_preflight_committed', lambda **_: snapshot)

    result = approve_release_handoff_plan_committed(
        tenant_id='tenant-a',
        actor_user_id=43,
        plan_sha256=plan['plan_sha256'],
        approved=True,
    )
    assert result['status'] == 'acknowledged_pending_provider_handoff'
    assert result['requested_by'] == 42 and result['approved_by'] == 43
    assert result['provider_mutation_performed'] is False
    assert result['provider_handoff_verified'] is False
    assert result['release_authorized'] is False
    assert session.commits == 1
    assert session.events[0].action == 'tenant.release.handoff_acknowledged'


def test_handoff_approval_rejects_partial_dependency_ledger_and_forged_count():
    snapshot = _snapshot()
    snapshot['dependency_counts'].pop('exposure policies')
    with pytest.raises(ValueError, match='every active Tenant dependency'):
        _can_confirm_plan(snapshot)

    snapshot = _snapshot()
    snapshot['handoff_required_count'] = 0
    with pytest.raises(ValueError, match='count is inconsistent'):
        _can_confirm_plan(snapshot)


def test_handoff_approval_rejects_changed_component_fingerprint_and_unknown_ownership():
    snapshot = _snapshot()
    snapshot['handoff_components'][0]['resource_version'] = '6'
    with pytest.raises(ValueError, match='fingerprint'):
        _can_confirm_plan(snapshot)

    snapshot['handoff_fingerprint'] = handoff_fingerprint(snapshot['handoff_components'])
    snapshot['handoff_components'][0]['handoff'] = 'unknown'
    snapshot['handoff_fingerprint'] = handoff_fingerprint(snapshot['handoff_components'])
    with pytest.raises(ValueError, match='Unsupported or missing ownership'):
        _can_confirm_plan(snapshot)


@pytest.mark.parametrize(
    ('state', 'expected'),
    [
        ('pending', 'pending'),
        ('expired', 'expired'),
        ('acknowledged', 'acknowledged'),
        ('blocked', 'blocked'),
    ],
)
def test_handoff_prepare_policy_distinguishes_one_current_plan(state, expected):
    now = datetime.now(UTC)
    plan = _plan_from_snapshot(_snapshot())
    approval = None
    if state == 'expired':
        plan['requested_at'] = (now - timedelta(hours=1)).isoformat()
    elif state == 'acknowledged':
        approval = {
            'plan_sha256': plan['plan_sha256'],
            'status': 'acknowledged_pending_provider_handoff',
        }
    elif state == 'blocked':
        plan['status'] = 'unexpected'
    assert handoff_plan_preparation_state(plan, approval) == expected


def test_handoff_prepare_policy_allows_no_plan_and_ignores_foreign_old_approval():
    plan = _plan_from_snapshot(_snapshot())
    assert handoff_plan_preparation_state(None, None) == 'available'
    assert (
        handoff_plan_preparation_state(
            plan, {'plan_sha256': 'b' * 64, 'status': 'acknowledged_pending_provider_handoff'}
        )
        == 'pending'
    )


@pytest.mark.parametrize(
    ('state', 'message'),
    [
        ('pending', 'awaiting independent approval'),
        ('acknowledged', 'independently acknowledged'),
        ('blocked', 'not eligible for replacement'),
    ],
)
def test_handoff_prepare_blocks_other_operator_and_requester_on_locked_plan(monkeypatch, state, message):
    from app.kubernetes.tenant import release_handoff_approval as module

    plan = _plan_from_snapshot(_snapshot())
    approval = None
    if state == 'acknowledged':
        approval = {
            'plan_sha256': plan['plan_sha256'],
            'status': 'acknowledged_pending_provider_handoff',
        }
    if state == 'blocked':
        plan['status'] = 'unknown'
    monkeypatch.setattr(module, 'latest_release_handoff_plan', lambda _: plan)
    monkeypatch.setattr(module, 'latest_release_handoff_approval', lambda _: approval)
    with pytest.raises(ValueError, match=message):
        _require_no_active_handoff_plan(tenant_id='tenant-a', actor_user_id=42)


def test_expired_unacknowledged_plan_allows_fresh_prepare_after_locked_check(monkeypatch):
    from app.kubernetes.tenant import release_handoff_approval as module

    expired = _plan_from_snapshot(_snapshot())
    expired['requested_at'] = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    monkeypatch.setattr(module, 'latest_release_handoff_plan', lambda _: expired)
    monkeypatch.setattr(module, 'latest_release_handoff_approval', lambda _: None)
    _require_no_active_handoff_plan(tenant_id='tenant-a', actor_user_id=42)


def test_handoff_prepare_checks_active_plan_after_tenant_row_lock(monkeypatch):
    from app.kubernetes.tenant import release_handoff_approval as module

    tenant = SimpleNamespace(ownership_status='adopted', lifecycle_status='ready')

    class _TenantQuery:
        def filter_by(self, **kwargs):
            return self

        def with_for_update(self):
            events.append('row-lock')
            return self

        def one_or_none(self):
            return tenant

    events = []
    session = _FakeSession(tenant)
    monkeypatch.setattr(module, 'db', SimpleNamespace(session=session))
    monkeypatch.setattr(module, 'Tenant', SimpleNamespace(query=_TenantQuery()))
    monkeypatch.setattr(module, 'AuditEvent', lambda **kwargs: SimpleNamespace(**kwargs))
    monkeypatch.setattr(module, 'review_tenant_release_preflight_committed', lambda **_: _snapshot())

    current = _plan_from_snapshot(_snapshot())

    def latest(_):
        events.append('check-current-plan')
        return current

    monkeypatch.setattr(module, 'latest_release_handoff_plan', latest)
    monkeypatch.setattr(module, 'latest_release_handoff_approval', lambda _: None)

    with pytest.raises(ValueError, match='awaiting independent approval'):
        prepare_release_handoff_plan_committed(
            tenant_id='tenant-a',
            actor_user_id=43,
            successor_owner='another-owner',
            change_reference='CHG-2026-202',
        )
    assert events.index('row-lock') < events.index('check-current-plan')
    assert session.commits == 0
    assert not session.events


def test_other_reviewer_cannot_renew_expired_requesters_plan(monkeypatch):
    from app.kubernetes.tenant import release_handoff_approval as module

    expired = _plan_from_snapshot(_snapshot())
    expired['requested_at'] = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    monkeypatch.setattr(module, 'latest_release_handoff_plan', lambda _: expired)
    monkeypatch.setattr(module, 'latest_release_handoff_approval', lambda _: None)
    with pytest.raises(ValueError, match='Only the original requester'):
        _require_no_active_handoff_plan(tenant_id='tenant-a', actor_user_id=43)


def test_corrupt_active_plan_timestamp_fails_closed(monkeypatch):
    from app.kubernetes.tenant import release_handoff_approval as module

    plan = _plan_from_snapshot(_snapshot())
    plan['requested_at'] = 'not-a-date'
    monkeypatch.setattr(module, 'latest_release_handoff_plan', lambda _: plan)
    monkeypatch.setattr(module, 'latest_release_handoff_approval', lambda _: None)
    assert handoff_plan_preparation_state(plan, None) == 'blocked'
    with pytest.raises(ValueError, match='not eligible for replacement'):
        _require_no_active_handoff_plan(tenant_id='tenant-a', actor_user_id=42)

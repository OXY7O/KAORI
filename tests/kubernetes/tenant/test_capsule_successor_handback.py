"""#1231 Capsule successor handback: pure negative and preservation checks.

Authored only while KAORI CI/CD, test and live provider gates are on HOLD.
"""

from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.kubernetes.tenant.capsule_successor_handback import (
    _capsule_handback_scope,
    _handback_patch,
    _handback_snapshot,
    _verify_handback,
)


def _case():
    tenant = SimpleNamespace(
        id='tenant-1',
        cluster_id='cluster-1',
        generation=2,
        provider_reference='demo',
    )
    release = {
        'status': 'released',
        'release_mode': 'managed_handoff',
        'provider_handoff_verified': True,
        'provider': 'capsule',
        'tenant_id': tenant.id,
        'cluster_id': tenant.cluster_id,
        'generation': tenant.generation,
        'plan_sha256': 'a' * 64,
        'handoff_fingerprint': 'b' * 64,
        'successor_owner': 'platform-team',
        'released_namespace_count': 1,
        'verified_resource_count': 4,
        'verified_components': [
            {'kind': 'CapsuleTenant', 'name': 'demo', 'uid': 'cr-uid', 'resource_version': '11', 'state': 'preserved'},
            {
                'kind': 'Namespace',
                'name': 'demo-dev',
                'uid': 'ns-uid',
                'resource_version': '15',
                'state': 'provider_markers_transferred',
            },
            {
                'kind': 'ResourceQuota',
                'namespace': 'demo-dev',
                'name': 'managed-quota',
                'uid': 'quota-uid',
                'resource_version': '24',
                'state': 'provider_markers_transferred',
            },
            {
                'kind': 'RoleBinding',
                'namespace': 'demo-dev',
                'name': 'capsule-generated',
                'uid': 'rb-uid',
                'resource_version': '7',
                'state': 'preserved',
            },
        ],
    }
    return tenant, release


def _resource(*, name='demo-dev', uid='ns-uid', rv='15', kind='Namespace', owner='platform-team'):
    meta = SimpleNamespace(
        name=name,
        uid=uid,
        resource_version=rv,
        labels={
            'app.kubernetes.io/managed-by': owner,
            'capsule.clastix.io/tenant': 'demo',
            'external.example/owner': 'unmodified',
        },
        annotations={'external.example/keep': 'yes'},
        owner_references=[],
        finalizers=[],
        deletion_timestamp=None,
    )
    return SimpleNamespace(metadata=meta, spec={'quota': {'pods': 3}})


def test_capsule_handback_exact_scope_does_not_patch_cr_or_foreign_rbac():
    tenant, release = _case()
    cr, targets = _capsule_handback_scope(release=release, tenant=tenant)
    assert cr['uid'] == 'cr-uid'
    assert [(x['kind'], x['name']) for x in targets] == [
        ('ResourceQuota', 'managed-quota'),
        ('Namespace', 'demo-dev'),
    ]


@pytest.mark.parametrize(
    'change',
    [
        lambda r: r.update(verified_resource_count=3),
        lambda r: r.update(released_namespace_count=2),
        lambda r: r['verified_components'].pop(0),
        lambda r: r['verified_components'].append(deepcopy(r['verified_components'][1])),
        lambda r: r['verified_components'][1].update(uid=''),
        lambda r: r['verified_components'][0].update(state='provider_markers_transferred'),
        lambda r: r['verified_components'][2].update(state='unknown'),
        lambda r: r['verified_components'][2].update(namespace='foreign-ns'),
        lambda r: r.update(provider_handoff_verified=False),
        lambda r: r.update(release_mode='observed_only'),
    ],
)
def test_capsule_handback_rejects_missing_duplicate_foreign_or_unverified_scope(change):
    tenant, release = _case()
    change(release)
    with pytest.raises((ValueError, TypeError)):
        _capsule_handback_scope(release=release, tenant=tenant)


def test_handback_json_patch_is_exact_cas_metadata_only():
    tenant, release = _case()
    _, targets = _capsule_handback_scope(release=release, tenant=tenant)
    ns = next(item for item in targets if item['kind'] == 'Namespace')
    before = _resource()
    patch = _handback_patch(before=before, item=ns, owner='platform-team')
    assert patch == [
        {'op': 'test', 'path': '/metadata/uid', 'value': 'ns-uid'},
        {'op': 'test', 'path': '/metadata/resourceVersion', 'value': '15'},
        {'op': 'test', 'path': '/metadata/labels', 'value': dict(before.metadata.labels)},
        {'op': 'remove', 'path': '/metadata/labels/app.kubernetes.io~1managed-by'},
    ]
    assert all(op['path'].startswith('/metadata/') for op in patch)


def test_capsule_handback_preview_and_post_patch_preserve_policy_and_foreign_labels():
    tenant, release = _case()
    _, targets = _capsule_handback_scope(release=release, tenant=tenant)
    ns = next(item for item in targets if item['kind'] == 'Namespace')
    before = _resource()
    after = deepcopy(before)
    after.metadata.labels.pop('app.kubernetes.io/managed-by')
    # Admission preview can keep original RV.
    assert (
        _verify_handback(
            before=before,
            after=after,
            item=ns,
            owner='platform-team',
            preview=True,
        )
        == '15'
    )
    after.metadata.resource_version = '16'
    assert (
        _verify_handback(
            before=before,
            after=after,
            item=ns,
            owner='platform-team',
            preview=False,
        )
        == '16'
    )
    assert after.metadata.labels['external.example/owner'] == 'unmodified'


@pytest.mark.parametrize(
    'mutate',
    [
        lambda a: a.metadata.labels.update({'foreign.example/drift': 'x'}),
        lambda a: setattr(a.metadata, 'uid', 'different'),
        lambda a: a.spec.update({'quota': {'pods': 100}}),
        lambda a: setattr(a.metadata, 'resource_version', ''),
    ],
)
def test_capsule_handback_rejects_unexpected_provider_readback(mutate):
    tenant, release = _case()
    ns = release['verified_components'][1]
    before = _resource()
    after = deepcopy(before)
    after.metadata.labels.pop('app.kubernetes.io/managed-by')
    after.metadata.resource_version = '16'
    mutate(after)
    with pytest.raises(ValueError):
        _verify_handback(
            before=before,
            after=after,
            item={**ns, 'namespace': 'demo-dev'},
            owner='platform-team',
            preview=False,
        )


def test_capsule_handback_refuses_stale_release_rv_or_kaori_marker():
    tenant, release = _case()
    ns = {**release['verified_components'][1], 'namespace': 'demo-dev'}
    with pytest.raises(ValueError, match='changed since Release'):
        _handback_snapshot(
            before=_resource(rv='17'),
            item=ns,
            owner='platform-team',
        )
    foreign = _resource()
    foreign.metadata.labels['kaori.io/tenant-id'] = 'unexpected'
    with pytest.raises(ValueError, match='changed since Release'):
        _handback_snapshot(
            before=foreign,
            item=ns,
            owner='platform-team',
        )


def test_capsule_handback_preserves_global_quota_and_external_namespace_without_patch():
    tenant, release = _case()
    release['verified_components'].append(
        {
            'kind': 'GlobalResourceQuota',
            'name': 'shared',
            'uid': 'global-uid',
            'resource_version': '19',
            'state': 'preserved',
        }
    )
    release['verified_components'].append(
        {
            'kind': 'Namespace',
            'name': 'demo-ops',
            'uid': 'ops-uid',
            'resource_version': '33',
            'state': 'preserved',
        }
    )
    release['verified_resource_count'] = 6
    release['released_namespace_count'] = 2
    cr, targets = _capsule_handback_scope(release=release, tenant=tenant)
    assert cr['name'] == 'demo'
    assert {row['name'] for row in targets} == {'demo-dev', 'managed-quota'}
    assert not any(row['kind'] == 'GlobalResourceQuota' for row in targets)
    assert not any(row['name'] == 'demo-ops' for row in targets)


@pytest.mark.parametrize(
    'mutation',
    [
        lambda row: row.update(state='provider_markers_transferred'),
        lambda row: row.update(uid=''),
        lambda row: row.update(resource_version=None),
    ],
)
def test_capsule_handback_refuses_changed_or_mutatable_global_quota(mutation):
    tenant, release = _case()
    row = {
        'kind': 'GlobalResourceQuota',
        'name': 'shared',
        'uid': 'global-uid',
        'resource_version': '19',
        'state': 'preserved',
    }
    mutation(row)
    release['verified_components'].append(row)
    release['verified_resource_count'] = 5
    with pytest.raises(ValueError):
        _capsule_handback_scope(release=release, tenant=tenant)


def test_capsule_handback_start_requires_postgresql_not_plain_mutable_audit():
    from app.kubernetes.tenant.capsule_successor_handback import (
        _require_postgres_capsule_handback_start_guards,
    )

    session = SimpleNamespace(
        get_bind=lambda: SimpleNamespace(dialect=SimpleNamespace(name='sqlite')),
        execute=lambda *_: pytest.fail('SQLite may not query or write handback evidence'),
    )
    with pytest.raises(ValueError, match='guarded PostgreSQL'):
        _require_postgres_capsule_handback_start_guards(session)


def test_capsule_handback_start_denies_missing_write_once_triggers():
    from app.kubernetes.tenant.capsule_successor_handback import (
        _require_postgres_capsule_handback_start_guards,
    )

    class Session:
        def get_bind(self):
            return SimpleNamespace(dialect=SimpleNamespace(name='postgresql'))

        def execute(self, statement):
            assert 'pg_trigger' in str(statement)
            return SimpleNamespace(all=lambda: [])

    with pytest.raises(ValueError, match='absent or disabled'):
        _require_postgres_capsule_handback_start_guards(Session())


@pytest.mark.parametrize(
    'mutation',
    [
        lambda index, posture: index.update(indisvalid=False),
        lambda index, posture: index.update(predicate='other/unprotected'),
        lambda index, posture: posture.update(elevated=True),
        lambda index, posture: posture.update(is_owner=True),
        lambda index, posture: posture.update(may_truncate=True),
        lambda index, posture: posture.update(fsync_setting='off'),
        lambda index, posture: posture.update(replication_role='replica'),
    ],
)
def test_capsule_handback_start_fail_closed_for_index_or_db_role_drift(mutation):
    from app.kubernetes.tenant.capsule_successor_handback import (
        _require_postgres_capsule_handback_start_guards,
    )

    target = 'kubernetes_tenant_verified_capsule_successor_handback'
    action = 'tenant.release.capsule_successor_handback_started'
    index = {
        'indisunique': True,
        'indisvalid': True,
        'definition': 'CREATE UNIQUE INDEX ... (target_id)',
        'predicate': f"target_type = '{target}' AND action = '{action}'",
    }
    posture = {
        'fsync_setting': 'on',
        'sync_commit': 'on',
        'replication_role': 'origin',
        'elevated': False,
        'is_owner': False,
        'member_of_owner': False,
        'may_insert': True,
        'may_truncate': False,
    }
    mutation(index, posture)

    class Session:
        def get_bind(self):
            return SimpleNamespace(dialect=SimpleNamespace(name='postgresql'))

        def execute(self, statement):
            sql = str(statement)
            if 'pg_trigger' in sql:
                return SimpleNamespace(
                    all=lambda: [
                        (f'tr_capsule_handback_audit_deny_{kind}', 'O') for kind in ('update', 'delete', 'truncate')
                    ]
                )
            if 'pg_index' in sql:
                return SimpleNamespace(
                    mappings=lambda: SimpleNamespace(one_or_none=lambda: index),
                )
            if 'pg_class' in sql:
                return SimpleNamespace(
                    mappings=lambda: SimpleNamespace(one=lambda: posture),
                )
            pytest.fail('Unexpected handback START guard query')

    with pytest.raises(ValueError, match='index|role'):
        _require_postgres_capsule_handback_start_guards(Session())


def test_capsule_handback_start_accepts_only_exact_protected_db_posture():
    from app.kubernetes.tenant.capsule_successor_handback import (
        _require_postgres_capsule_handback_start_guards,
    )

    target = 'kubernetes_tenant_verified_capsule_successor_handback'
    action = 'tenant.release.capsule_successor_handback_started'

    class Session:
        def get_bind(self):
            return SimpleNamespace(dialect=SimpleNamespace(name='postgresql'))

        def execute(self, statement):
            sql = str(statement)
            if 'pg_trigger' in sql:
                return SimpleNamespace(
                    all=lambda: [
                        (f'tr_capsule_handback_audit_deny_{kind}', 'O') for kind in ('update', 'delete', 'truncate')
                    ]
                )
            if 'pg_index' in sql:
                index = {
                    'indisunique': True,
                    'indisvalid': True,
                    'definition': 'CREATE UNIQUE INDEX ... (target_id)',
                    'predicate': f"target_type = '{target}' AND action = '{action}'",
                }
                return SimpleNamespace(
                    mappings=lambda: SimpleNamespace(one_or_none=lambda: index),
                )
            if 'pg_class' in sql:
                posture = {
                    'fsync_setting': 'on',
                    'sync_commit': 'on',
                    'replication_role': 'origin',
                    'elevated': False,
                    'is_owner': False,
                    'member_of_owner': False,
                    'may_insert': True,
                    'may_truncate': False,
                }
                return SimpleNamespace(
                    mappings=lambda: SimpleNamespace(one=lambda: posture),
                )
            pytest.fail('Unexpected handback START guard query')

    _require_postgres_capsule_handback_start_guards(Session())


def test_capsule_handback_guard_migration_is_source_only_and_refuses_evidence_downgrade():
    from pathlib import Path

    source = Path('migrations/versions/20261012_capsule_handback_audit_guard.py').read_text()
    assert "revision = '20261012_capsule_handback_guard'" in source
    assert "down_revision = '20261011_reveal_uid'" in source
    assert 'tr_capsule_handback_audit_deny_truncate' in source
    assert 'uq_capsule_handback_start_tenant_once' in source
    assert 'OLD.target_type =' in source
    assert 'NEW.target_type =' in source
    assert 'Cannot remove Capsule handback guards' in source

"""Independent ESO readback is not evidence of Vault certificate delivery."""

from datetime import UTC, datetime, timedelta

import pytest

from app.kubernetes.governance.tls_certificates.eso_reconciliation import (
    ESOTargetEvidence,
    normalize_eso_readback,
    qualify_eso_reconciliation,
)

NOW = datetime(2026, 10, 22, 12, tzinfo=UTC)
ESO_UID = '12345678-1234-4234-8234-123456789abd'
SECRET_UID = '12345678-1234-4234-8234-123456789abc'
REPLACED_UID = '12345678-1234-4234-8234-123456789abe'
OWNER = [{'kind': 'ExternalSecret', 'api_group': 'external-secrets.io', 'uid': ESO_UID}]


def resource(*, ready='True', generation=3, observed_generation=None):
    payload = {
        'apiVersion': 'external-secrets.io/v1beta1',
        'kind': 'ExternalSecret',
        'metadata': {'uid': ESO_UID, 'namespace': 'private-team', 'generation': generation, 'name': 'hidden'},
        'spec': {'target': {'name': 'reusable'}, 'data': [{'remoteRef': {'key': 'vault/private/path'}}]},
        'status': {
            'syncedResourceVersion': '1042',
            'refreshTime': (NOW - timedelta(minutes=10)).isoformat(),
            'conditions': [{'type': 'Ready', 'status': ready}],
        },
    }
    if observed_generation is not None:
        payload['status']['observedGeneration'] = observed_generation
    return payload


def evaluate(raw=None, **overrides):
    receipt = normalize_eso_readback(resource() if raw is None else raw, cluster_id='cluster-a', observed_at=NOW)
    kwargs = {
        'target_cluster_id': 'cluster-a',
        'target_namespace': 'private-team',
        'target_secret_uid': SECRET_UID,
        'current_secret_uid': SECRET_UID,
        'target_fingerprint_sha256': 'a' * 64,
        'target_owner_refs': OWNER,
        'target_observed_at': NOW - timedelta(minutes=4),
        'current_identity_observed_at': NOW - timedelta(minutes=2),
        'controller_source_state': 'ready',
        'tls_source_state': 'ready',
        'now': NOW,
    }
    kwargs.update(overrides)
    target = ESOTargetEvidence(
        target_cluster_id=kwargs.pop('target_cluster_id'),
        target_namespace=kwargs.pop('target_namespace'),
        target_secret_uid=kwargs.pop('target_secret_uid'),
        current_secret_uid=kwargs.pop('current_secret_uid'),
        target_fingerprint_sha256=kwargs.pop('target_fingerprint_sha256'),
        target_owner_refs=kwargs.pop('target_owner_refs'),
        target_observed_at=kwargs.pop('target_observed_at'),
        current_identity_observed_at=kwargs.pop('current_identity_observed_at'),
    )
    return qualify_eso_reconciliation(receipt, target=target, **kwargs)


def test_current_controller_candidate_never_proves_vault_or_materialization():
    result = evaluate()
    assert result.status == 'reconciled_candidate'
    assert result.controller_reconciliation_observed and result.immutable_target_correlated
    assert not result.vault_to_controller_proven
    assert not result.delivery_proven
    assert not result.endpoint_serving_verified


def test_optional_observed_generation_must_match_when_present():
    assert evaluate(resource(observed_generation=3)).status == 'reconciled_candidate'
    assert evaluate(resource(observed_generation=2)).status == 'unknown'


def test_crd_secret_names_paths_and_spec_never_leave_normalizer():
    receipt = normalize_eso_readback(resource(), cluster_id='cluster-a', observed_at=NOW)
    assert receipt is not None
    assert 'private-team' not in repr(receipt)
    assert 'vault/private/path' not in repr(receipt)
    assert not hasattr(receipt, 'spec')
    assert not hasattr(receipt, 'name')


@pytest.mark.parametrize(
    'mutation',
    [
        lambda x: x['status'].update(observedGeneration=2),
        lambda x: x['status'].pop('syncedResourceVersion'),
        lambda x: x['status'].update(syncedResourceVersion=''),
        lambda x: x['status'].update(syncedResourceVersion=' untrusted '),
        lambda x: x['status'].pop('refreshTime'),
        lambda x: x['status'].update(refreshTime=(NOW + timedelta(minutes=1)).isoformat()),
        lambda x: x['status'].update(conditions=[{'type': 'Ready', 'status': 'True'}] * 2),
        lambda x: x['status'].update(conditions=[{'type': 'Ready', 'status': 'True', 'observedGeneration': 2}]),
        lambda x: x['status'].update(conditions=[{'type': 'Synced', 'status': 'True'}]),
        lambda x: x['metadata'].update(uid='vault/../../secrets'),
        lambda x: x['metadata'].update(generation=True),
        lambda x: x.update(kind='SecretStore'),
        lambda x: x.update(apiVersion='unapproved.io/v1'),
    ],
)
def test_unsupported_malformed_and_conflicting_status_is_unknown(mutation):
    raw = resource()
    mutation(raw)
    assert evaluate(raw).status == 'unknown'


@pytest.mark.parametrize(
    'override',
    [
        {'target_cluster_id': 'cluster-b'},
        {'target_namespace': 'other'},
        {'current_secret_uid': REPLACED_UID},
        {'current_secret_uid': None},
        {'target_secret_uid': None},
        {'target_owner_refs': None},
        {'target_owner_refs': []},
        {'target_owner_refs': [{'kind': 'ExternalSecret', 'api_group': 'external-secrets.io', 'uid': REPLACED_UID}]},
        {'target_fingerprint_sha256': 'Z' * 64},
        {'tls_source_state': 'partial'},
        {'controller_source_state': 'stale'},
        {'current_identity_observed_at': None},
        {'current_identity_observed_at': NOW - timedelta(days=2)},
        {'target_observed_at': NOW - timedelta(hours=2)},
        {'now': NOW + timedelta(days=2)},
    ],
)
def test_recreated_uid_stale_source_and_cross_scope_evidence_is_unknown(override):
    result = evaluate(**override)
    assert result.status == 'unknown' and not result.delivery_proven


def test_ready_false_is_observed_not_ready_not_delivery_failure():
    result = evaluate(resource(ready='False'))
    assert result.status == 'not_ready'
    assert not result.controller_reconciliation_observed
    assert not result.delivery_proven


def test_naive_timestamps_and_invalid_generation_are_not_qualified():
    raw = resource()
    raw['status']['refreshTime'] = '2026-10-22T11:50:00'
    assert evaluate(raw).status == 'unknown'
    assert evaluate(resource(generation=0, observed_generation=0)).status == 'unknown'

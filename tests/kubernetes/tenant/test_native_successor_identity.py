"""Review-only Native Kubernetes successor identity checks; no Release admission."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.kubernetes.tenant import native_successor_identity as subject
from app.kubernetes.tenant.release_handoff_approval import _plan_hash


def _plan(**overrides):
    data = {
        'tenant_id': 'tenant-1',
        'cluster_id': 'cluster-1',
        'generation': 1,
        'provider': 'native_kubernetes',
        'handoff_fingerprint': 'fingerprint-1',
        'provider_identity': [{'kind': 'Namespace', 'uid': 'uid-1'}],
        'handoff_components': [{'kind': 'Namespace', 'uid': 'uid-1'}],
        'successor_owner': 'platform-team',
        'change_reference': 'CHG-100',
        'requested_by': 21,
        'requested_at': datetime.now(UTC).isoformat(),
    }
    data.update(overrides)
    data['plan_sha256'] = _plan_hash(data)
    return data


def _status(*, authenticated=True, groups=None, username='alice', uid='provider-user-1', error=None):
    return SimpleNamespace(
        status=SimpleNamespace(
            authenticated=authenticated,
            error=error,
            user=SimpleNamespace(
                username=username, uid=uid,
                groups=['platform-team', 'system:authenticated'] if groups is None else groups,
            ),
            audiences=['kubernetes'],
        )
    )


class _AuthenticationApi:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def create_token_review(self, body, **kwargs):
        self.calls.append((body, kwargs))
        return self.response


def _review(monkeypatch, *, plan=None, response=None, cluster=None, token='provider-token'):
    api = _AuthenticationApi(_status() if response is None else response)
    provider = SimpleNamespace(authentication_api=lambda: api)
    monkeypatch.setattr(subject.runtime_adapter, 'build_client', lambda _: provider)
    receipt = subject.verify_native_successor_identity_for_review(
        cluster=cluster or SimpleNamespace(
            id='cluster-1', kubernetes_connection=SimpleNamespace(verify_ssl=True)
        ),
        plan=_plan() if plan is None else plan,
        provider_token=token,
    )
    return receipt, api


def test_token_review_proves_provider_principal_but_never_consent_or_release(monkeypatch):
    evidence, api = _review(monkeypatch)
    assert evidence['status'] == 'provider_identity_observed_consent_unverified'
    assert evidence['provider_groups_include_successor'] is True
    assert evidence['successor_owner'] == 'platform-team'
    assert evidence['provider_principal_uid'] == 'provider-user-1'
    assert evidence['consent_verified'] is False
    assert evidence['identity_mapping_admitted'] is False
    assert evidence['release_authorized'] is False
    assert evidence['provider_mutation_performed'] is False
    assert evidence['secret_material_persisted'] is False
    assert len(api.calls) == 1
    assert api.calls[0][1]['_request_timeout'] == 5
    assert 'provider-token' not in repr(evidence)
    assert api.calls[0][0].spec.token == 'provider-token'


@pytest.mark.parametrize('reply', [
    _status(authenticated=False),
    _status(groups=['other-group']),
    _status(groups=['platform-team', 'system:masters']),
    _status(username='system:serviceaccount:default:robot'),
    _status(uid=''),
    _status(error='invalid token'),
    _status(groups='platform-team'),
])
def test_provider_identity_must_be_authoritative_and_nonprivileged(monkeypatch, reply):
    with pytest.raises(ValueError, match='did not authenticate'):
        _review(monkeypatch, response=reply)


@pytest.mark.parametrize('changes', [
    {'cluster_id': 'another-cluster'},
    {'provider': 'capsule'},
    {'successor_owner': 'kaori'},
    {'successor_owner': 'team/subgroup'},
    {'successor_owner': 'system:masters'},
    {'handoff_components': []},
    {'provider_identity': []},
    {'generation': 0},
    {'requested_at': '2020-01-01T00:00:00+00:00'},
])
def test_fail_closed_on_wrong_provider_scope_owner_or_stale_plan(monkeypatch, changes):
    with pytest.raises(ValueError):
        _review(monkeypatch, plan=_plan(**changes))


def test_tampered_plan_digest_does_not_reach_token_review(monkeypatch):
    with pytest.raises(ValueError, match='fresh, exact'):
        _review(monkeypatch, plan={**_plan(), 'successor_owner': 'foreign'})


@pytest.mark.parametrize('token', ['', 'x' * 16385, 'a token with whitespace'])
def test_rejects_invalid_token_before_provider_request(monkeypatch, token):
    with pytest.raises(ValueError, match='bounded'):
        _review(monkeypatch, token=token)


def test_cluster_mismatch_blocks_even_a_valid_kubernetes_principal(monkeypatch):
    with pytest.raises(ValueError, match='fresh, exact'):
        _review(monkeypatch, cluster=SimpleNamespace(
            id='cluster-2', kubernetes_connection=SimpleNamespace(verify_ssl=True)
        ))


def test_identity_review_refuses_insecure_provider_connection(monkeypatch):
    cluster = SimpleNamespace(
        id='cluster-1', kubernetes_connection=SimpleNamespace(verify_ssl=False)
    )
    with pytest.raises(ValueError, match='TLS verification'):
        _review(monkeypatch, cluster=cluster)

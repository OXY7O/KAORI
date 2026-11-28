"""Remote draft proof is distinct from local grant and never active."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.infrastructure_automation import credential_evidence, credential_grants, remote_access_evidence


@pytest.mark.parametrize('remote', [False, True])
def test_provider_proof_resolver_preserves_operation_separation(monkeypatch, remote):
    calls = []
    policy, target = object(), object()
    monkeypatch.setattr(credential_evidence, 'exact_credential_target_current', lambda *args, **kwargs: not remote)
    monkeypatch.setattr(credential_evidence, 'exact_remote_credential_draft_current', lambda *args, **kwargs: remote)
    monkeypatch.setattr(
        credential_evidence, '_resolve_qualified_credential_evidence', lambda *args, **kwargs: calls.append('proof') or 'proof'
    )
    now = datetime.now(UTC)
    assert credential_evidence.resolve_current_credential_evidence(policy, target, now=now) == (
        None if remote else 'proof'
    )
    assert credential_evidence.resolve_remote_draft_credential_evidence(policy, target, now=now) == (
        'proof' if remote else None
    )
    assert calls == ['proof']


@pytest.mark.parametrize('failure', [None, 'active', 'duplicate', 'expired', 'revoked', 'approved', 'proof', 'revision'])
def test_remote_draft_qualifies_latest_exact_draft_only(monkeypatch, failure):
    now = datetime.now(UTC)
    policy = SimpleNamespace(id='draft', current_revision=1)
    revision = SimpleNamespace(
        revision_number=1, lifecycle_status='draft', effective_from=now - timedelta(minutes=1),
        effective_until=now + timedelta(minutes=5), requested_by_user_id=8,
        approved_by_user_id=None, approved_at=None, credential_evidence_ref=None,
    )
    evidence = SimpleNamespace(issued_at=now - timedelta(minutes=2), expires_at=now + timedelta(minutes=10))
    policies = [policy]
    if failure == 'duplicate':
        policies.append(SimpleNamespace(id='other', current_revision=1))
    elif failure in ('active', 'revoked'):
        revision.lifecycle_status = failure
    elif failure == 'expired':
        revision.effective_until = now
    elif failure == 'approved':
        revision.approved_by_user_id = 9
    elif failure == 'revision':
        revision.revision_number = 2
    monkeypatch.setattr(credential_grants, 'local_security_review_enabled', lambda: True)
    monkeypatch.setattr(credential_grants, 'lock_explicit_permissions', lambda *args: True)
    monkeypatch.setattr(credential_grants, '_latest_revision', lambda identity: revision)
    monkeypatch.setattr(credential_grants, 'db', SimpleNamespace(session=SimpleNamespace(
        execute=lambda statement: SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: policies)),
        get=lambda *args, **kwargs: object(),
    )))
    monkeypatch.setattr(
        credential_grants, 'resolve_remote_draft_credential_evidence',
        lambda *args, **kwargs: None if failure == 'proof' else evidence,
    )
    result = credential_grants.review_remote_credential_draft(
        actor_user_id=7, connection_id=31, assignment_id=1, now=now
    )
    if failure is None:
        assert result is not None and result.policy_id == 'draft'
        assert result.execution_authorized is False
    else:
        assert result is None


@pytest.mark.parametrize('failure', [None, 'missing_draft', 'wrong_proof', 'same_policy', 'missing_trust'])
def test_remote_access_requires_distinct_draft_and_matching_proof(monkeypatch, failure):
    now = datetime.now(UTC)
    evidence = SimpleNamespace(evidence_ref='a' * 64, expires_at=now + timedelta(minutes=10))
    grant = SimpleNamespace(policy_id='local', revision=2, evidence=evidence, expires_at=now + timedelta(minutes=9))
    draft = SimpleNamespace(
        policy_id='draft', revision=1, evidence=evidence, expires_at=now + timedelta(minutes=4),
        execution_authorized=False,
    )
    if failure == 'wrong_proof':
        draft.evidence = object()
    elif failure == 'same_policy':
        draft.policy_id = grant.policy_id
    policy = SimpleNamespace(current_revision=2)
    target = SimpleNamespace(ansible_connection_id=31, assignment_id=1, host_revision='b' * 64,
                             reference_fingerprint='c' * 64)
    trust = SimpleNamespace(
        expires_at=now + timedelta(minutes=8), target=SimpleNamespace(revision_number=1),
        evidence_ref='d' * 64,
    )
    monkeypatch.setattr(remote_access_evidence, 'review_current_credential_grant', lambda **kwargs: grant)
    monkeypatch.setattr(
        remote_access_evidence, 'review_remote_credential_draft',
        lambda **kwargs: None if failure == 'missing_draft' else draft,
    )
    monkeypatch.setattr(remote_access_evidence, 'db', SimpleNamespace(session=SimpleNamespace(
        get=lambda model, *args, **kwargs: policy if model is remote_access_evidence.ScopeAccessPolicy else target,
    )))
    monkeypatch.setattr(
        remote_access_evidence, 'review_current_console_trust',
        lambda *args, **kwargs: None if failure == 'missing_trust' else trust,
    )
    result = remote_access_evidence.review_remote_access_evidence(
        actor_user_id=7, connection_id=31, assignment_id=1, now=now
    )
    if failure is None:
        assert result is not None and result.expires_at == draft.expires_at
        assert result.execution_authorized is False
        draft.revision = 2
        changed = remote_access_evidence.review_remote_access_evidence(
            actor_user_id=7, connection_id=31, assignment_id=1, now=now
        )
        assert changed is not None and changed.fingerprint != result.fingerprint
    else:
        assert result is None

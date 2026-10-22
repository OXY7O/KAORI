"""#2726 shadow parity is never permission enforcement or source discovery."""

from types import SimpleNamespace

import pytest

from app.access import scope_parity


class _Session:
    def __init__(self, actor):
        self.actor = actor

    def get(self, _model, _actor_id):
        return self.actor


@pytest.mark.parametrize(('legacy', 'scoped', 'expected'), [
    (True, 'allow', 'parity_allowed'),
    (False, 'deny', 'parity_denied'),
    (True, 'deny', 'legacy_allowed_scope_denied'),
    (False, 'allow', 'legacy_denied_scope_allowed'),
    (True, 'unavailable', 'scoped_unavailable'),
])
def test_read_only_comparison_classifies_access_delta(monkeypatch, legacy, scoped, expected):
    actor = SimpleNamespace(is_active=True, has_permission=lambda _permission: legacy)
    monkeypatch.setattr(scope_parity, 'db', SimpleNamespace(session=_Session(actor)))
    monkeypatch.setattr(
        scope_parity,
        'evaluate_exact_vault_scope',
        lambda **_k: SimpleNamespace(status=scoped, allowed=scoped == 'allow'),
    )
    finding = scope_parity.compare_scope_parity(
        actor_user_id=11, instance_id=33,
        provider_namespace='', mount='fixture-only-mount',
    )
    assert finding.variance == expected
    assert finding.requires_review is (expected not in {'parity_allowed', 'parity_denied'})
    assert 'fixture-only-mount' not in repr(finding)
    assert '33' not in repr(finding)


def test_parity_shadow_does_not_grant_or_modify_permission(monkeypatch):
    actor = SimpleNamespace(is_active=False, has_permission=lambda _permission: True)
    monkeypatch.setattr(scope_parity, 'db', SimpleNamespace(session=_Session(actor)))
    monkeypatch.setattr(
        scope_parity, 'evaluate_exact_vault_scope',
        lambda **_k: SimpleNamespace(status='deny', allowed=False),
    )
    finding = scope_parity.compare_scope_parity(
        actor_user_id=11, instance_id=33, provider_namespace='', mount='kv',
    )
    assert finding.variance == 'parity_denied'
    assert not finding.baseline_allowed
    summary = scope_parity.summarize_scope_parity([finding])
    assert summary['mode'] == 'non_enforcing_shadow'
    assert summary['cutover_admitted'] == 0
    assert summary['parity_denied'] == 1
    assert 'kv' not in repr(summary)
    assert '33' not in repr(summary)


def test_summary_is_bounded_and_never_emits_resource_identity():
    item = scope_parity.ScopeParityFinding(True, 'deny', 'legacy_allowed_scope_denied')
    assert scope_parity.summarize_scope_parity([item])['requires_review'] == 1
    with pytest.raises(ValueError, match='sample bound'):
        scope_parity.summarize_scope_parity([item] * 201)


def test_scope_parity_remains_internal_without_public_route():
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    routes = (root / 'app/secrets_pki/routes.py').read_text(encoding='utf-8')
    assert 'compare_scope_parity' not in routes
    assert 'read_governed_scoped_secret_registry' not in routes
    assert 'read_scoped_secret_registry' not in routes

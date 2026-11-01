"""Vault Alert Source uses Alertmanager's scoped binding, not a new ingestion engine."""

from types import SimpleNamespace

import pytest

from app.integrations.observability.alert_source.providers.alertmanager import (
    binding_validation,
    vault_scope,
)
from app.integrations.observability.alert_source.providers.alertmanager.binding_profiles import (
    get_alert_consumer_profile,
)


def _scope(value='42', *, label='vault_instance', operator='='):
    return {'matchers': [{'label': label, 'operator': operator, 'value': value}]}


@pytest.fixture
def admit_vault(monkeypatch):
    identity = SimpleNamespace(
        id=42,
        integration_type='secrets_pki',
        provider_key='vault',
        lifecycle_status='active',
        enabled=True,
    )
    monkeypatch.setattr(
        vault_scope,
        'db',
        SimpleNamespace(
            session=SimpleNamespace(get=lambda _cls, pk: identity if pk == 42 else None),
        ),
    )
    return identity


def test_vault_consumer_profile_uses_existing_alertmanager_registry():
    profile = get_alert_consumer_profile('vault_instance')
    assert profile is not None
    assert profile.profile_key == 'vault-alerts-v1'
    assert 'alerts_v2' in profile.required_capabilities


def test_only_exact_canonical_vault_identity_is_authorized(admit_vault):
    vault_scope.require_vault_alert_scope(asset_key='42', selector_json=_scope())
    for selector in (
        _scope('99'),
        _scope('vault-production'),
        _scope('42', label='instance'),
        _scope('.*', operator='=~'),
        {'matchers': [*_scope()['matchers'], *_scope('42', label='job')['matchers']]},
    ):
        with pytest.raises(ValueError, match='exact vault_instance'):
            vault_scope.require_vault_alert_scope(asset_key='42', selector_json=selector)


def test_broken_asset_scope_is_rejected_even_with_matching_selector(admit_vault):
    with pytest.raises(ValueError, match='ineligible'):
        vault_scope.require_vault_alert_scope(asset_key='43', selector_json=_scope())


def test_no_active_alert_does_not_imply_an_observed_alert_identity(monkeypatch, admit_vault):
    instance = SimpleNamespace(integration_instance_id=12)
    binding = SimpleNamespace(
        integration_instance_id=12,
        asset_type='vault_instance',
        asset_key='42',
        selector_json=_scope(),
        validation_profile=None,
        validation_status=None,
        validation_message=None,
        validation_evidence=None,
        last_validated_at=None,
    )
    calls = []

    def get_alerts(*, filters):
        calls.append(('alerts', filters))
        return []

    def get_silences(*, filters):
        calls.append(('silences', filters))
        return []

    monkeypatch.setattr(
        binding_validation,
        'build_client',
        lambda _instance: SimpleNamespace(
            get_alerts=get_alerts,
            get_silences=get_silences,
        ),
    )
    result = binding_validation.validate_binding(instance=instance, binding=binding, commit=False)
    assert result['status'] == 'ready'
    assert binding.validation_evidence['identity_observed'] is False
    assert binding.validation_evidence['sample_alert_names'] == []
    assert calls[0] == ('alerts', ['vault_instance="42"'])


def test_foreign_alert_labels_block_vault_source_scope(monkeypatch, admit_vault):
    instance = SimpleNamespace(integration_instance_id=12)
    binding = SimpleNamespace(
        integration_instance_id=12,
        asset_type='vault_instance',
        asset_key='42',
        selector_json=_scope(),
        validation_profile=None,
        validation_status=None,
        validation_message=None,
        validation_evidence=None,
        last_validated_at=None,
    )
    monkeypatch.setattr(
        binding_validation,
        'build_client',
        lambda _instance: SimpleNamespace(
            get_alerts=lambda **_kwargs: [
                {'labels': {'vault_instance': '99', 'alertname': 'contains-private-path'}},
            ],
            get_silences=lambda **_kwargs: pytest.fail('No silence query after foreign identity'),
        ),
    )
    result = binding_validation.validate_binding(instance=instance, binding=binding, commit=False)
    assert result['status'] == 'blocked'
    assert 'contains-private-path' not in str(result)
    assert binding.validation_evidence is None

"""HV-12 Vault Alert Source summary: only allowlisted aggregates persist."""

from types import SimpleNamespace

import pytest

from app.integrations.observability.alert_source.providers.alertmanager import (
    binding_validation,
    vault_alert_evidence,
    vault_scope,
)


def _scope():
    return {'matchers': [{'label': 'vault_instance', 'operator': '=', 'value': '42'}]}


def _alert(*, asset='42', state='active', severity='critical'):
    return {
        'labels': {
            'vault_instance': asset,
            'severity': severity,
            'alertname': 'sensitive/kv/secret-owner/example',
        },
        'status': {'state': state},
        'annotations': {'summary': 'secret-path/credential'},
        'fingerprint': 'deadbeef',
        'generatorURL': 'https://internal.example/secret-path',
    }


@pytest.mark.parametrize(
    ('payload', 'status'),
    [
        ([], 'unobserved'),
        ([{'labels': {'vault_instance': '43'}, 'status': {'state': 'active'}}], 'blocked'),
        ([{'labels': {'vault_instance': '42'}, 'status': {'state': 'resolved'}}], 'incomplete'),
        ([_alert(severity='unknown')], 'incomplete'),
        ([_alert(state='pending')], 'incomplete'),
        ([None], 'blocked'),
        ({'alerts': []}, 'blocked'),
        ([_alert()] * 101, 'blocked'),
    ],
)
def test_disallowed_samples_fail_closed_without_counts(payload, status):
    result = vault_alert_evidence.qualify_vault_alert_sample(asset_key='42', payload=payload)
    assert result['status'] == status
    assert result['identity_observed'] is False
    assert result['observed_rows'] is None
    assert result['firing'] is None
    assert result['critical'] is None
    assert 'sensitive' not in str(result)
    assert 'deadbeef' not in str(result)


@pytest.mark.parametrize('identity', ['', '0', '042', '-42', '+42', '42a', '４２', '42949672960'])
def test_noncanonical_identity_rejected(identity):
    assert vault_alert_evidence.qualify_vault_alert_sample(
        asset_key=identity, payload=[_alert()],
    )['status'] == 'blocked'


def test_valid_sample_counts_only_raw_observations_without_case_claims():
    result = vault_alert_evidence.qualify_vault_alert_sample(
        asset_key='42',
        payload=[_alert(), _alert(state='suppressed', severity='warning'),
                 _alert(state='unprocessed', severity='info')],
    )
    assert result['status'] == 'qualified'
    assert result['identity_observed'] is True
    assert (result['observed_rows'], result['firing'], result['suppressed'], result['unprocessed']) == (3, 1, 1, 1)
    assert (result['critical'], result['warning'], result['info']) == (1, 1, 1)
    assert 'secret-path' not in str(result)
    assert 'deadbeef' not in str(result)


def _binding():
    return SimpleNamespace(
        integration_instance_id=12, asset_type='vault_instance', asset_key='42',
        selector_json=_scope(), validation_profile=None, validation_status=None,
        validation_message=None, validation_evidence=None, last_validated_at=None,
    )


def _setup(monkeypatch, alerts):
    identity = SimpleNamespace(
        id=42, integration_type='secrets_pki', provider_key='vault',
        enabled=True, lifecycle_status='active',
    )
    monkeypatch.setattr(
        vault_scope, 'db', SimpleNamespace(
            session=SimpleNamespace(get=lambda _model, key: identity if key == 42 else None),
        ),
    )
    queries = []
    def get_alerts(*, filters):
        queries.append(('alerts', filters))
        return alerts

    def get_silences(*, filters):
        queries.append(('silences', filters))
        return []

    monkeypatch.setattr(
        binding_validation, 'build_client',
        lambda _instance: SimpleNamespace(get_alerts=get_alerts, get_silences=get_silences),
    )
    return queries


def test_binding_validation_commits_only_safe_qualified_counts(monkeypatch):
    calls = _setup(monkeypatch, [_alert(), _alert(state='suppressed', severity='warning')])
    binding = _binding()
    result = binding_validation.validate_binding(
        instance=SimpleNamespace(integration_instance_id=12), binding=binding, commit=False,
    )
    assert result['status'] == 'ready'
    sample = binding.validation_evidence['vault_alert_sample']
    assert sample['status'] == 'qualified'
    assert sample['observed_rows'] == 2
    assert sample['firing'] == 1
    assert sample['suppressed'] == 1
    assert 'sensitive' not in str(binding.validation_evidence)
    assert 'deadbeef' not in str(binding.validation_evidence)
    assert calls[0] == ('alerts', ['vault_instance="42"'])


def test_empty_validated_binding_is_unobserved_not_healthy(monkeypatch):
    _setup(monkeypatch, [])
    binding = _binding()
    result = binding_validation.validate_binding(
        instance=SimpleNamespace(integration_instance_id=12), binding=binding, commit=False,
    )
    assert result['status'] == 'ready'
    assert binding.validation_evidence['vault_alert_sample']['status'] == 'unobserved'
    assert binding.validation_evidence['vault_alert_sample']['observed_rows'] is None


@pytest.mark.parametrize('bad_payload', [[_alert(asset='99')], [_alert(state='weird')], [_alert()] * 101, {'a': 1}])
def test_unsafe_binding_sample_never_qualifies_or_leaks(monkeypatch, bad_payload):
    calls = _setup(monkeypatch, bad_payload)
    binding = _binding()
    result = binding_validation.validate_binding(
        instance=SimpleNamespace(integration_instance_id=12), binding=binding, commit=False,
    )
    assert result['status'] in {'blocked', 'degraded'}
    if result['status'] == 'blocked':
        assert binding.validation_evidence is None
    else:
        assert binding.validation_evidence['vault_alert_sample']['status'] == 'incomplete'
    assert 'sensitive' not in str(result) + str(binding.validation_evidence)
    assert all(query[0] != 'silences' for query in calls) if result['status'] == 'blocked' else True

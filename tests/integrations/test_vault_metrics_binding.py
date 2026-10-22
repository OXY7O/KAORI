"""Vault Metrics Source binding requires a uniquely labelled, fresh source signal."""

from time import time
from types import SimpleNamespace

from app.integrations.observability.metrics_source.binding_profiles import (
    get_binding_validation_profile,
)
from app.integrations.observability.metrics_source.binding_validators import get_binding_validator
from app.integrations.observability.metrics_source.binding_validators import vault as vault_validator


def _binding(instance_id='42', *, selector=None):
    return SimpleNamespace(
        asset_key=instance_id,
        selector_json=selector or {
            'matchers': [{'label': 'vault_instance', 'operator': '=', 'value': instance_id}],
        },
    )


def _client(*, value='1', age=2, count=1, name='vault_core_active'):
    queries = []
    record = {
        'metric': {'__name__': name, 'vault_instance': '42', 'instance': 'vault-host:8200'},
        'value': [time() - age, value],
    }

    def query(expression):
        queries.append(expression)
        return {'status': 'success', 'data': {
            'resultType': 'vector', 'result': [record] * count,
        }}

    return SimpleNamespace(query=query, queries=queries)


def _run(monkeypatch, client, binding=None, *, provider='vault', enabled=True):
    identity = SimpleNamespace(
        id=42, integration_type='secrets_pki', provider_key=provider,
        lifecycle_status='active', enabled=enabled,
    )
    monkeypatch.setattr(
        vault_validator, 'db',
        SimpleNamespace(session=SimpleNamespace(get=lambda cls, pk: identity if pk == 42 else None)),
    )
    profile = get_binding_validation_profile('prometheus_http', 'vault_instance')
    assert profile is not None
    return vault_validator.validate_vault_metrics_binding(
        client=client, binding=binding or _binding(), profile=profile,
    )


def test_vault_validation_profile_is_registered_with_existing_metrics_source():
    profile = get_binding_validation_profile('prometheus_http', 'vault_instance')
    assert profile is not None and profile.validation_strategy == 'custom'
    assert profile.profile_key == 'vault-telemetry-v1'
    assert get_binding_validator('prometheus_http', 'vault_instance') is (
        vault_validator.validate_vault_metrics_binding
    )


def test_single_node_exact_identity_is_ready_but_not_historical_retention(monkeypatch):
    source = _client()
    result = _run(monkeypatch, source)
    assert result.status == 'ready'
    assert result.matched_signal == 'vault_core_active'
    assert result.matched_series == 1
    assert result.evidence['historical_query_readiness'] == 'not_validated'
    assert result.evidence['alert_source_readiness'] == 'not_evaluated'
    assert source.queries == ['vault_core_active{vault_instance="42"}']


def test_provider_api_readiness_is_not_changed_on_missing_metrics(monkeypatch):
    result = _run(monkeypatch, _client(count=0))
    assert result.status == 'degraded'
    assert result.evidence['selector_isolation'] == 'no_match'
    assert 'provider_api_status' not in result.evidence


def test_ambiguous_ha_selector_is_blocked(monkeypatch):
    result = _run(monkeypatch, _client(count=2))
    assert result.status == 'blocked'
    assert result.evidence['selector_isolation'] == 'ambiguous_identity'


def test_metric_sample_must_be_fresh_and_value_qualified(monkeypatch):
    assert _run(monkeypatch, _client(age=3600)).status == 'degraded'
    assert _run(monkeypatch, _client(value='NaN')).status == 'degraded'
    assert _run(monkeypatch, _client(value='99')).status == 'degraded'


def test_selector_requires_exact_safe_label_and_canonical_instance_id(monkeypatch):
    for selector in (
        {'matchers': [{'label': 'job', 'operator': '=', 'value': 'vault'}]},
        {'matchers': [{'label': 'vault_instance', 'operator': '=~', 'value': '.*'}]},
        {'matchers': [{'label': 'vault_instance', 'operator': '=', 'value': 'another'}]},
        {'matchers': [
            {'label': 'vault_instance', 'operator': '=', 'value': '42'},
            {'label': 'instance', 'operator': '=~', 'value': '.*'},
        ]},
    ):
        client = _client()
        result = _run(monkeypatch, client, _binding(selector=selector))
        assert result.status == 'blocked'
        assert client.queries == []


def test_other_provider_identity_is_not_admitted_as_vault(monkeypatch):
    source = _client()
    assert _run(monkeypatch, source, provider='openbao').status == 'blocked'
    assert source.queries == []


def test_invalid_metric_response_and_provider_errors_are_sanitized(monkeypatch):
    source = SimpleNamespace(query=lambda _expression: (_ for _ in ()).throw(
        RuntimeError('https://vault.example/private/token'),
    ))
    result = _run(monkeypatch, source)
    assert result.status == 'degraded'
    assert 'vault.example' not in result.message
    assert 'vault.example' not in repr(result.evidence)

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
        selector_json=selector
        or {
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
        return {
            'status': 'success',
            'data': {
                'resultType': 'vector',
                'result': [record] * count,
            },
        }

    return SimpleNamespace(query=query, queries=queries)


def _run(monkeypatch, client, binding=None, *, provider='vault', enabled=True):
    identity = SimpleNamespace(
        id=42,
        integration_type='secrets_pki',
        provider_key=provider,
        lifecycle_status='active',
        enabled=enabled,
    )
    monkeypatch.setattr(
        vault_validator,
        'db',
        SimpleNamespace(session=SimpleNamespace(get=lambda cls, pk: identity if pk == 42 else None)),
    )
    profile = get_binding_validation_profile('prometheus_http', 'vault_instance')
    assert profile is not None
    return vault_validator.validate_vault_metrics_binding(
        client=client,
        binding=binding or _binding(),
        profile=profile,
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
        {
            'matchers': [
                {'label': 'vault_instance', 'operator': '=', 'value': '42'},
                {'label': 'instance', 'operator': '=~', 'value': '.*'},
            ]
        },
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
    source = SimpleNamespace(
        query=lambda _expression: (_ for _ in ()).throw(
            RuntimeError('https://vault.example/private/token'),
        )
    )
    result = _run(monkeypatch, source)
    assert result.status == 'degraded'
    assert 'vault.example' not in result.message
    assert 'vault.example' not in repr(result.evidence)


def test_vault_asset_uses_the_same_label_in_the_shared_binding_picker():
    from app.integrations.consumer_assets import get_consumer_asset_definition

    definition = get_consumer_asset_definition('vault_instance')
    assert definition is not None
    assert definition.model.__name__ == 'IntegrationInstance'
    assert definition.integration_type == 'secrets_pki'
    assert definition.selector_label == 'vault_instance'


def _range_client(*, variant='ready'):
    source = _client()
    source.range_queries = []

    def query_range(expression, start, end, step):
        source.range_queries.append((expression, start, end, step))
        window_start, window_end = int(start), int(end)
        points = [[ts, '1'] for ts in range(window_start, window_end + 1, 300)]
        record = {
            'metric': {
                '__name__': 'vault_core_active',
                'vault_instance': '42',
                'instance': 'private-hostname-not-to-persist',
            },
            'values': points,
        }
        if variant == 'foreign':
            record['metric']['vault_instance'] = '43'
        if variant == 'bad_value':
            record['values'][0][1] = 'NaN'
        if variant == 'unsorted':
            record['values'][2][0] = record['values'][1][0]
        if variant == 'missing_early':
            record['values'] = points[4:]
        if variant == 'missing_late':
            record['values'] = points[:-4]
        if variant == 'future':
            record['values'][-1][0] = window_end + 120
        if variant == 'outside_start':
            record['values'][0][0] = window_start - 120
        if variant == 'bad_timestamp':
            record['values'][0][0] = 'NaN'
        if variant == 'wrong_metric':
            record['metric']['__name__'] = 'unrelated_metric'
        if variant == 'gap':
            record['values'] = points[:5] + points[8:]
        if variant == 'overbudget':
            record['values'] += [[window_end + i, '1'] for i in range(5)]
        if variant == 'empty':
            return {'status': 'success', 'data': {'resultType': 'matrix', 'result': []}}
        if variant == 'multiple':
            return {'status': 'success', 'data': {'resultType': 'matrix', 'result': [record, record]}}
        if variant == 'bad_type':
            return {'status': 'success', 'data': {'resultType': 'vector', 'result': [record]}}
        if variant == 'error':
            raise RuntimeError('https://metrics.local/secrets/unauthorized-token')
        return {'status': 'success', 'data': {'resultType': 'matrix', 'result': [record]}}

    source.query_range = query_range
    return source


def test_vault_binding_validates_bounded_historical_window_without_long_term_claim(monkeypatch):
    source = _range_client()
    result = _run(monkeypatch, source)
    assert result.status == 'ready'
    assert result.evidence['historical_query_readiness'] == 'recent_hour_qualified'
    assert result.evidence['retention_coverage'] == 'one_hour_observed_only'
    assert result.evidence['historical_window_seconds'] == 3600
    assert result.evidence['historical_step_seconds'] == 300
    assert result.evidence['historical_sample_count'] == 13
    assert len(source.range_queries) == 1
    assert source.range_queries[0][0] == 'vault_core_active{vault_instance="42"}'
    assert source.range_queries[0][3] == '300'
    assert int(source.range_queries[0][2]) - int(source.range_queries[0][1]) == 3600
    assert 'private-hostname' not in repr(result.evidence)
    assert 'values' not in result.evidence


def test_absent_historical_query_range_is_not_claimed(monkeypatch):
    source = _client()
    result = _run(monkeypatch, source)
    assert result.status == 'ready'
    assert result.evidence['historical_query_readiness'] == 'not_validated'


def test_history_query_negative_results_never_change_instant_or_vault_health(monkeypatch):
    expected = {
        'foreign': 'ambiguous',
        'bad_value': 'incomplete',
        'unsorted': 'incomplete',
        'missing_early': 'incomplete',
        'missing_late': 'incomplete',
        'future': 'incomplete',
        'outside_start': 'incomplete',
        'bad_timestamp': 'incomplete',
        'wrong_metric': 'ambiguous',
        'gap': 'incomplete',
        'overbudget': 'incomplete',
        'empty': 'incomplete',
        'multiple': 'ambiguous',
        'bad_type': 'unavailable',
        'error': 'unavailable',
    }
    for variant, historical_status in expected.items():
        source = _range_client(variant=variant)
        result = _run(monkeypatch, source)
        assert result.status == 'ready'
        assert result.evidence['historical_query_readiness'] == historical_status
        assert result.evidence['retention_coverage'] == 'not_qualified'
        assert 'provider_api_status' not in result.evidence
        assert 'unauthorized-token' not in repr(result.evidence)
        assert len(source.range_queries) == 1


def test_history_query_never_runs_for_unqualified_instant_source(monkeypatch):
    source = _range_client()
    result = _run(monkeypatch, source, provider='openbao')
    assert result.status == 'blocked'
    assert source.queries == []
    assert source.range_queries == []
    result = _run(
        monkeypatch,
        source,
        _binding(
            selector={'matchers': [{'label': 'job', 'operator': '=', 'value': 'vault'}]},
        ),
    )
    assert result.status == 'blocked'
    assert source.range_queries == []

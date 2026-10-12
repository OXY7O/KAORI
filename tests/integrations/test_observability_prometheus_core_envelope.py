"""Provider Core Validation requires a valid response *and* usable query probe data."""

from types import SimpleNamespace

import pytest

from app.integrations.observability.metrics_source.adapters.prometheus_http.validation import (
    _valid_core_response,
    validate_metrics_core,
)


@pytest.mark.parametrize(
    ('key', 'valid_data'),
    [
        ('instant_query', {'resultType': 'vector', 'result': [
            {'metric': {}, 'value': [1.0, '1']}
        ]}),
        ('range_query', {'resultType': 'matrix', 'result': [
            {'metric': {}, 'values': [[1.0, '1'], [2.0, '1']]}
        ]}),
        ('series_discovery', []),
        ('label_discovery', []),
    ],
)
def test_valid_core_envelopes(key, valid_data) -> None:
    assert _valid_core_response(key, {'status': 'success', 'data': valid_data})


@pytest.mark.parametrize('key', ['instant_query', 'range_query', 'series_discovery', 'label_discovery'])
@pytest.mark.parametrize('payload', [
    {'status': 'success'},
    {'status': 'success', 'data': None},
    {'status': 'success', 'data': {'resultType': 'vector'}},
    {'status': 'error', 'data': []},
    [],
    None,
])
def test_missing_or_malformed_envelope_never_proves_capability(key, payload) -> None:
    assert not _valid_core_response(key, payload)


def test_query_probe_must_have_nonempty_vector_of_valid_samples() -> None:
    assert not _valid_core_response('instant_query', {
        'status': 'success', 'data': {'resultType': 'vector', 'result': []},
    })
    assert not _valid_core_response('range_query', {
        'status': 'success', 'data': {'resultType': 'matrix', 'result': [
            {'metric': {}, 'values': [['bad-timestamp', '1']]}
        ]},
    })


def test_discovery_api_rejects_malformed_items_but_accepts_true_empty() -> None:
    assert _valid_core_response('series_discovery', {'status': 'success', 'data': []})
    assert _valid_core_response('label_discovery', {'status': 'success', 'data': []})
    assert not _valid_core_response('series_discovery', {'status': 'success', 'data': ['bad']})
    assert not _valid_core_response('label_discovery', {'status': 'success', 'data': [{'k': 'v'}]})


def test_full_core_validation_cannot_persist_ready_from_fake_success_envelopes() -> None:
    client = SimpleNamespace(
        query=lambda *_a: {'status': 'success'},
        query_range=lambda *_a: {'status': 'success'},
        series=lambda *_a, **_k: {'status': 'success'},
        label_values=lambda *_a: {'status': 'success'},
    )
    result = validate_metrics_core(client)
    assert result['status'] == 'blocked'
    assert result['available_capabilities'] == []
    assert len(result['missing_capabilities']) == 4
    assert all(item['status'] == 'missing' for item in result['capability_assessments'])

"""Alertmanager API v2 empty evidence is valid; partial malformed evidence is not."""

from types import MethodType

import pytest

from app.integrations.observability.alert_source.providers.alertmanager.client import AlertmanagerClient
from app.integrations.observability.alert_source.providers.alertmanager.exceptions import (
    AlertmanagerResponseError,
)


def _client() -> AlertmanagerClient:
    return AlertmanagerClient(endpoint='https://alertmanager.example.invalid')


def _response(client, payload):
    client._request_json = MethodType(lambda self, **_kwargs: payload, client)


@pytest.mark.parametrize('payload', [[], [{'labels': {'alertname': 'Down'}}]])
def test_valid_alerts_including_genuine_empty_list_are_preserved(payload) -> None:
    client = _client()
    _response(client, payload)
    assert client.get_alerts() == payload


@pytest.mark.parametrize('payload', [[None], [{'unexpected': 1}], [{'labels': []}], 'wrong'])
def test_malformed_alert_records_fail_closed(payload) -> None:
    client = _client()
    _response(client, payload)
    with pytest.raises(AlertmanagerResponseError):
        client.get_alerts()


@pytest.mark.parametrize('payload', [[], [{'id': 'silence-1', 'matchers': []}]])
def test_valid_silences_including_genuine_empty_list_are_preserved(payload) -> None:
    client = _client()
    _response(client, payload)
    assert client.get_silences() == payload


@pytest.mark.parametrize(
    'payload', [[None], [{'id': '', 'matchers': []}], [{'id': 'x'}], [{'id': 'x', 'matchers': None}], {}]
)
def test_malformed_silence_records_fail_closed(payload) -> None:
    client = _client()
    _response(client, payload)
    with pytest.raises(AlertmanagerResponseError):
        client.get_silences()


@pytest.mark.parametrize('payload', [{}, [], {'versionInfo': {}}, {'versionInfo': {'version': ''}}])
def test_missing_alertmanager_status_identity_is_not_a_successful_connection(payload) -> None:
    client = _client()
    client.get_status = MethodType(lambda self: payload, client)
    with pytest.raises(AlertmanagerResponseError, match='status'):
        client.test_connection()


def test_status_with_version_identity_remains_valid_when_cluster_is_absent() -> None:
    client = _client()
    client.get_status = MethodType(lambda self: {'versionInfo': {'version': '0.28.0'}}, client)
    result = client.test_connection()
    assert result['connected'] is True
    assert result['version'] == '0.28.0'
    assert result['cluster_status'] == 'unknown'

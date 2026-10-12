from __future__ import annotations

from types import SimpleNamespace

import pytest
from flask import Flask
from werkzeug.exceptions import NotFound

from app.artifact_registry.presentation_analytics import _registry_analytics_scope
from app.artifact_registry.routes import _analytics_provider_id


@pytest.mark.parametrize('query', ['?provider_id=abc', '?provider_id=-1', '?provider_id=0', '?provider_id=2.2'])
def test_invalid_analytics_provider_id_fails_closed(query: str):
    app = Flask(__name__)
    with app.test_request_context('/artifact-registry/analytics' + query):
        with pytest.raises(NotFound):
            _analytics_provider_id()


def test_unavailable_or_disabled_selected_provider_never_becomes_all():
    identities = [SimpleNamespace(id=1)]
    assert _registry_analytics_scope(None, identities) is None
    assert _registry_analytics_scope(1, identities) == 1
    with pytest.raises(NotFound):
        _registry_analytics_scope(3, identities)


def test_analytics_governance_explicitly_not_configured_differs_from_unassessed():
    from app.artifact_registry.presentation_analytics import _analytics_aggregate, _accumulate_domain_counts

    aggregate = _analytics_aggregate()
    _accumulate_domain_counts(aggregate, {
        'inventory': {'projects': 10},
        'security': {},
        'runtime': {},
        'governance': {
            'projects_assessed': 2,
            'retention_configured': 1,
            'retention_not_configured': 1,
            'immutability_configured': 1,
            'immutability_not_configured': 0,
        },
    })
    assert aggregate['projects'] == 10
    assert aggregate['retention_not_configured'] == 1
    assert aggregate['immutability_not_configured'] == 0

from __future__ import annotations

from types import SimpleNamespace

import pytest
from werkzeug.exceptions import NotFound

from app.artifact_registry import presentation_common


@pytest.mark.parametrize('requested_id', [9, 0, -1])
def test_unavailable_registry_overview_scope_does_not_fall_through_to_all(
    monkeypatch, requested_id: int,
) -> None:
    provider = SimpleNamespace(id=1, name='Enabled Registry')
    monkeypatch.setattr(presentation_common, '_providers', lambda: [provider])
    # No RegistryCollectionState read can occur until scope membership is validated.
    with pytest.raises(NotFound):
        presentation_common._overview_scope_context(provider_id=requested_id)


def test_registry_overview_does_not_admit_disabled_active_integrations() -> None:
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[3] /
        'app/artifact_registry/presentation_common.py'
    ).read_text(encoding='utf-8')
    providers = source.split('def _providers(', 1)[1].split('@overload', 1)[0]
    assert "IntegrationInstance.integration_type == 'registry'" in providers
    assert "IntegrationInstance.lifecycle_status == 'active'" in providers
    assert 'IntegrationInstance.enabled.is_(True)' in providers
    assert 'raise NotFound(' in source


@pytest.mark.parametrize('query', ['?provider_id=abc', '?provider_id=-5', '?provider_id=0', '?provider_id=1.5'])
def test_invalid_provider_id_query_is_rejected_before_any_projection(query: str) -> None:
    from flask import Flask

    from app.artifact_registry.routes import _overview_provider_id

    flask = Flask('registry-overview-scope-test')
    with flask.test_request_context('/artifact-registry/' + query):
        with pytest.raises(NotFound):
            _overview_provider_id()


@pytest.mark.parametrize(('query', 'selected'), [
    ('', None),
    ('?provider_id=', None),
    ('?provider_id=7', 7),
])
def test_valid_provider_id_query_is_preserved(query: str, selected: int | None) -> None:
    from flask import Flask

    from app.artifact_registry.routes import _overview_provider_id

    flask = Flask('registry-overview-scope-test')
    with flask.test_request_context('/artifact-registry/' + query):
        assert _overview_provider_id() == selected

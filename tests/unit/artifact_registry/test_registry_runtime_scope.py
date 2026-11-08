from __future__ import annotations

from types import SimpleNamespace

import pytest
from flask import Flask
from werkzeug.exceptions import NotFound

from app.artifact_registry import routes


@pytest.mark.parametrize(
    'query',
    [
        '?source_id=abc',
        '?source_id=-1',
        '?source_id=0',
        '?source_id=1.2',
        '?artifact_id=xyz',
        '?artifact_id=-1',
    ],
)
def test_invalid_runtime_filters_are_not_treated_as_unfiltered(query):
    app = Flask(__name__)
    with app.test_request_context('/artifact-registry/runtime' + query):
        selected = 'source_id' if 'source_id' in query else 'artifact_id'
        with pytest.raises(NotFound):
            routes._runtime_scope_id(selected)


def test_disabled_registry_source_cannot_be_selected(monkeypatch):
    app = Flask(__name__)
    monkeypatch.setattr(routes, '_active_registry_sources', lambda: [SimpleNamespace(id=7)])
    with app.test_request_context('/artifact-registry/runtime?source_id=8'):
        with pytest.raises(NotFound):
            routes._runtime_scope_id('source_id')
    with app.test_request_context('/artifact-registry/runtime?source_id=7'):
        assert routes._runtime_scope_id('source_id') == 7
    with app.test_request_context('/artifact-registry/runtime?artifact_id=8'):
        assert routes._runtime_scope_id('artifact_id') == 8

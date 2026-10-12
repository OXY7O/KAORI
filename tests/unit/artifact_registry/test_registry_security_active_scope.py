from __future__ import annotations

import pytest
from flask import Flask
from werkzeug.exceptions import NotFound

from app.artifact_registry.routes import _security_source_id
from app.artifact_registry.security import presentation


@pytest.mark.parametrize('query', ['?source_id=abc', '?source_id=-1', '?source_id=0', '?source_id=4.2'])
def test_invalid_security_source_get_fails_closed(query: str) -> None:
    app = Flask(__name__)
    with app.test_request_context('/artifact-registry/security' + query):
        with pytest.raises(NotFound):
            _security_source_id()


@pytest.mark.parametrize('value', ['abc', '-1', '0'])
def test_invalid_security_sync_post_filter_fails_before_job_dispatch(value: str) -> None:
    app = Flask(__name__)
    with app.test_request_context('/artifact-registry/security/sync', method='POST', data={'source_id': value}):
        with pytest.raises(NotFound):
            _security_source_id(from_form=True)


def test_source_filter_never_falls_back_to_global_when_empty() -> None:
    class Query:
        def __init__(self) -> None:
            self.filters = []

        def filter(self, predicate):
            self.filters.append(predicate)
            return self

    query = Query()
    assert presentation._apply_source_scope(query, [], scoped=False) is query
    assert len(query.filters) == 1
    assert str(query.filters[0]).lower() == 'false'


def test_selected_disabled_or_uncommitted_source_does_not_become_all_sources(monkeypatch) -> None:
    monkeypatch.setattr(presentation, '_registered_sources', lambda: [])
    monkeypatch.setattr(presentation, '_providers', lambda: [])
    with pytest.raises(NotFound):
        presentation.build_security(source_id=17)

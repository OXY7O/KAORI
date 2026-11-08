"""GitHub Source Control public response helper keeps concrete Flask headers."""

from __future__ import annotations

import pytest
from flask import Flask, Response

from app.integrations.source_control.source_control.providers.github.application import routes


def test_registration_response_remains_concrete_and_non_cacheable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(routes, 'render_template', lambda *_args, **_kwargs: 'registration preview')
    app = Flask(__name__)
    with app.test_request_context('/integrations/source-control/github/'):
        response = routes._respond('integrations/source_control/github/form.html')
        response.status_code = 409

    assert isinstance(response, Response)
    assert response.status_code == 409
    assert response.get_data(as_text=True) == 'registration preview'
    assert response.headers['Cache-Control'] == 'no-store, max-age=0'
    assert response.headers['Pragma'] == 'no-cache'

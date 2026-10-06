from __future__ import annotations

from flask import Flask

from app.platform_operations.kubernetes.secret_reveal import routes


def test_secret_reveal_htmx_save_returns_workspace_without_redirect(monkeypatch) -> None:
    app = Flask(__name__)
    app.secret_key = 'test-secret'

    monkeypatch.setattr(
        routes,
        'url_for',
        lambda endpoint, **values: '/platform-operations/kubernetes/?tab=secret-reveal&cluster_id=cluster-1',
    )
    monkeypatch.setattr(
        routes,
        'build_secret_reveal_settings_context',
        lambda *args, **kwargs: {'selected_cluster': None},
    )
    monkeypatch.setattr(
        routes,
        'render_template',
        lambda template, **context: '<div id="secret-reveal-cluster-workspace"></div>',
    )

    with app.test_request_context(
        '/save',
        method='POST',
        headers={'HX-Request': 'true'},
        data={
            'namespace_q': 'platform',
            'namespace_policy': 'enabled',
            'page': '2',
            'per_page': '10',
        },
    ):
        response = routes._settings_response('cluster-1')

    assert response.status_code == 200
    assert 'secret-reveal-cluster-workspace' in response.get_data(as_text=True)
    assert response.headers['HX-Push-Url'].startswith('/platform-operations/kubernetes/')
    assert response.headers['HX-Trigger'] == '{"kaori:notifications-changed": true}'
    assert 'Location' not in response.headers


def test_secret_reveal_non_htmx_save_keeps_redirect_fallback(monkeypatch) -> None:
    app = Flask(__name__)
    app.secret_key = 'test-secret'

    monkeypatch.setattr(
        routes,
        'url_for',
        lambda endpoint, **values: '/platform-operations/kubernetes/?tab=secret-reveal&cluster_id=cluster-1',
    )

    with app.test_request_context('/save', method='POST'):
        response = routes._settings_response('cluster-1')

    assert response.status_code == 302
    assert response.headers['Location'].endswith(
        '/platform-operations/kubernetes/?tab=secret-reveal&cluster_id=cluster-1'
    )

from __future__ import annotations

from html.parser import HTMLParser
from types import SimpleNamespace

import pytest
from flask import Response

from app import create_app
from app.access.authentication import routes as auth_routes
from app.bootstrap import presentation as bootstrap_presentation
from app.bootstrap.security import _protect_inline_scripts


class _SecurityHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.next_input: dict[str, str | None] | None = None
        self.script_attributes: list[dict[str, str | None]] = []
        self.tags: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append(tag)
        attributes = dict(attrs)
        if tag == 'input' and attributes.get('name') == 'next':
            self.next_input = attributes
        if tag == 'script':
            self.script_attributes.append(attributes)


@pytest.fixture()
def app(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        auth_routes,
        'check_authentication_database_readiness',
        lambda: SimpleNamespace(ready=True, setup_required=False, missing_tables=()),
    )
    monkeypatch.setattr(auth_routes, 'enabled_sso_providers', lambda: [])
    monkeypatch.setattr(bootstrap_presentation, 'pop_operational_feedback', lambda: None)
    return create_app('testing')


def _csp_directives(value: str) -> dict[str, str]:
    directives: dict[str, str] = {}
    for raw_directive in value.split(';'):
        directive = raw_directive.strip()
        if not directive:
            continue
        name, _, policy = directive.partition(' ')
        directives[name] = policy.strip()
    return directives


def _csp_nonce(value: str) -> str:
    script_sources = _csp_directives(value)['script-src'].split()
    nonce_source = next(source for source in script_sources if source.startswith("'nonce-") and source.endswith("'"))
    return nonce_source[len("'nonce-") : -1]


def test_html_responses_apply_central_http_security_baseline(app) -> None:
    response = app.test_client().get('/auth/login')

    assert response.status_code == 200
    assert response.headers['X-Frame-Options'] == 'DENY'
    assert response.headers['X-Content-Type-Options'] == 'nosniff'

    permissions = {item.strip() for item in response.headers['Permissions-Policy'].split(',')}
    assert {'camera=()', 'microphone=()', 'geolocation=()'} <= permissions

    directives = _csp_directives(response.headers['Content-Security-Policy'])
    assert directives['default-src'] == "'self'"
    assert directives['base-uri'] == "'self'"
    assert directives['object-src'] == "'none'"
    assert directives['frame-ancestors'] == "'none'"
    assert directives['form-action'] == "'self'"
    assert "'self'" in directives['script-src'].split()
    assert "'unsafe-inline'" not in directives['script-src'].split()
    assert directives['script-src-attr'] == "'none'"
    assert _csp_nonce(response.headers['Content-Security-Policy'])

    assert response.headers['Cross-Origin-Opener-Policy'] == 'same-origin'
    assert response.headers['Cross-Origin-Embedder-Policy'] == 'require-corp'
    assert response.headers['Cross-Origin-Resource-Policy'] == 'same-origin'


def test_inline_bootstrap_scripts_are_protected_by_response_nonce(app) -> None:
    response = app.test_client().get('/auth/login')
    nonce = _csp_nonce(response.headers['Content-Security-Policy'])

    parser = _SecurityHtmlParser()
    parser.feed(response.get_data(as_text=True))
    inline_scripts = [attributes for attributes in parser.script_attributes if 'src' not in attributes]

    assert inline_scripts
    assert all(attributes.get('nonce') == nonce for attributes in inline_scripts)


def test_nonce_transformer_trusts_only_governed_inline_openings() -> None:
    response = Response(
        '<script>window.bare = true</script>'
        '<script data-kaori-prepaint-bootstrap="app-shell">window.app = true</script>'
        '<script data-kaori-prepaint-bootstrap="auth-theme">window.auth = true</script>'
        '<script data-kaori-prepaint-bootstrap="unapproved">window.bad = true</script>'
        '<script data-untrusted="true">window.other = true</script>'
        '<script src="/static/js/app.js"></script>',
        mimetype='text/html',
    )

    _protect_inline_scripts(response, 'fixed-nonce')

    parser = _SecurityHtmlParser()
    parser.feed(response.get_data(as_text=True))
    scripts = parser.script_attributes

    assert scripts[0].get('nonce') == 'fixed-nonce'
    assert scripts[1].get('nonce') == 'fixed-nonce'
    assert scripts[2].get('nonce') == 'fixed-nonce'
    assert 'nonce' not in scripts[3]
    assert 'nonce' not in scripts[4]
    assert 'nonce' not in scripts[5]


def test_csp_nonce_rotates_between_html_responses(app) -> None:
    client = app.test_client()

    first = _csp_nonce(client.get('/auth/login').headers['Content-Security-Policy'])
    second = _csp_nonce(client.get('/auth/login').headers['Content-Security-Policy'])

    assert first != second


def test_static_responses_receive_mime_sniffing_and_resource_isolation(app) -> None:
    response = app.test_client().get('/static/favicon.svg')

    assert response.status_code == 200
    assert response.headers['X-Content-Type-Options'] == 'nosniff'
    assert response.headers['Cross-Origin-Resource-Policy'] == 'same-origin'
    assert 'Cross-Origin-Embedder-Policy' not in response.headers
    assert 'Cross-Origin-Opener-Policy' not in response.headers


def test_hostile_next_payload_stays_data_inside_hidden_login_field(app) -> None:
    payload = '/"><svg/onload=alert(1)><input autofocus onfocus=alert(2)>'
    response = app.test_client().get('/auth/login', query_string={'next': payload})
    html = response.get_data(as_text=True)

    assert response.status_code == 200

    parser = _SecurityHtmlParser()
    parser.feed(html)

    assert parser.next_input is not None
    assert parser.next_input.get('value') == payload
    assert 'autofocus' not in parser.next_input
    assert 'onfocus' not in parser.next_input
    assert 'svg' not in parser.tags

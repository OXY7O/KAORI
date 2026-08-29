from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace

import pytest

from app import create_app
from app.access.authentication import routes as auth_routes
from app.bootstrap import presentation as bootstrap_presentation

ROOT = Path(__file__).resolve().parents[2]
_INLINE_SCRIPT_RE = re.compile(r'<script(?![^>]*\bsrc=)[^>]*>', re.IGNORECASE)


class _LoginFormParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.next_input: dict[str, str | None] | None = None
        self.tags: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append(tag)
        attributes = dict(attrs)
        if tag == 'input' and attributes.get('name') == 'next':
            self.next_input = attributes


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


def test_static_responses_receive_mime_sniffing_protection(app) -> None:
    response = app.test_client().get('/static/favicon.svg')

    assert response.status_code == 200
    assert response.headers['X-Content-Type-Options'] == 'nosniff'


def test_csp_compatible_layouts_do_not_embed_inline_script_blocks() -> None:
    for relative_path in ('app/templates/layouts/app.html', 'app/templates/layouts/auth.html'):
        template = (ROOT / relative_path).read_text(encoding='utf-8')
        assert _INLINE_SCRIPT_RE.search(template) is None, relative_path


def test_hostile_next_payload_stays_data_inside_hidden_login_field(app) -> None:
    payload = '/"><svg/onload=alert(1)><input autofocus onfocus=alert(2)>'
    response = app.test_client().get('/auth/login', query_string={'next': payload})
    html = response.get_data(as_text=True)

    assert response.status_code == 200

    parser = _LoginFormParser()
    parser.feed(html)

    assert parser.next_input is not None
    assert parser.next_input.get('value') == payload
    assert 'autofocus' not in parser.next_input
    assert 'onfocus' not in parser.next_input
    assert 'svg' not in parser.tags

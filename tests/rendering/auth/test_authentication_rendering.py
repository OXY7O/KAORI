from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE_ROOT = ROOT / 'app/templates'


def _environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(TEMPLATE_ROOT),
        autoescape=select_autoescape(('html', 'xml')),
        undefined=StrictUndefined,
    )


def test_authentication_templates_compile_with_shared_layout() -> None:
    environment = _environment()

    for template_name in (
        'layouts/auth.html',
        'access/authentication/index.html',
        'access/authentication/setup_required.html',
        'access/authentication/partials/_brand_panel.html',
        'access/authentication/partials/_login_form.html',
        'access/authentication/partials/_login_alerts.html',
    ):
        environment.get_template(template_name)


def test_login_rendering_keeps_accessibility_compactness_and_no_page_local_handlers() -> None:
    index = (TEMPLATE_ROOT / 'access/authentication/index.html').read_text(encoding='utf-8')
    form = (TEMPLATE_ROOT / 'access/authentication/partials/_login_form.html').read_text(encoding='utf-8')
    alerts = (TEMPLATE_ROOT / 'access/authentication/partials/_login_alerts.html').read_text(encoding='utf-8')
    css = (ROOT / 'app/static/css/auth-login.css').read_text(encoding='utf-8')

    assert 'aria-label="KAORI sign in"' in index
    assert 'aria-label="Show password"' in form
    assert 'autocomplete="username"' in form
    assert 'autocomplete="current-password"' in form
    assert 'aria-live="polite"' in alerts
    assert ' onclick=' not in form.lower()
    assert ' onchange=' not in form.lower()
    assert 'width: min(1060px, 100%);' in css
    assert 'min-height: 44px;' in css

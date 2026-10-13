from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

ROOT = Path(__file__).resolve().parents[4]
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


class _SetupStructureParser(HTMLParser):
    """Require actual rendered setup controls to remain inside the canvas."""

    _VOID = {
        'area',
        'base',
        'br',
        'col',
        'embed',
        'hr',
        'img',
        'input',
        'link',
        'meta',
        'param',
        'source',
        'track',
        'wbr',
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.elements: list[tuple[str, dict[str, str | None]]] = []
        self.errors: list[str] = []
        self.found: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if any(name.startswith('<') for name, _value in attrs):
            self.errors.append(f'malformed start tag <{tag}>: nested tag parsed as attribute')
        workspace_in_ancestors = any('data-kaori-setup-workspace' in attributes for _tag, attributes in self.elements)
        console_in_ancestors = any('data-kaori-setup-console' in attributes for _tag, attributes in self.elements)
        markers = {
            'data-kaori-setup-console',
            'data-kaori-setup-command',
            'data-kaori-terminal-command',
            'data-kaori-setup-security',
            'data-kaori-setup-flow',
            'data-kaori-setup-advanced',
        }
        for marker in markers.intersection(values):
            self.found.add(marker)
            if not workspace_in_ancestors:
                self.errors.append(f'{marker} escaped the setup workspace')
        if 'data-kaori-setup-command' in values and not console_in_ancestors:
            self.errors.append('bootstrap command escaped the primary action panel')
        if tag == 'footer' and not workspace_in_ancestors:
            self.errors.append('setup footer escaped the workspace')
        if tag not in self._VOID:
            self.elements.append((tag, values))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in self._VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag in self._VOID:
            return
        if not self.elements or self.elements[-1][0] != tag:
            self.errors.append(f'unbalanced closing tag </{tag}>')
            return
        self.elements.pop()


def test_rendered_database_setup_html_stays_inside_its_workspace() -> None:
    """Regression for #744: missing '>' previously broke bootstrap containment."""
    environment = _environment()
    environment.globals.update(
        url_for=lambda _endpoint, **_params: '/auth/login',
        load_operational_feedback=lambda: None,
    )
    template = environment.get_template('access/authentication/setup_required.html')

    for setup_required in (True, False):
        for app_env in ('development', 'production'):
            html = template.render(
                config={'APP_ENV': app_env, 'TESTING': False},
                readiness={
                    'setup_required': setup_required,
                    'missing_tables': ['users', 'roles'] if setup_required else [],
                },
            )
            parser = _SetupStructureParser()
            parser.feed(html)
            parser.close()

            assert not parser.errors, f'setup_required={setup_required}, app_env={app_env}: ' + '; '.join(parser.errors)
            assert not parser.elements, 'unclosed rendered HTML elements'
            assert 'data-kaori-setup-console' in parser.found
            assert 'data-kaori-terminal-command' in parser.found
            assert 'data-kaori-setup-security' in parser.found
            if setup_required:
                assert 'data-kaori-setup-command' in parser.found
                assert 'data-kaori-setup-flow' in parser.found
                assert 'data-kaori-setup-advanced' in parser.found

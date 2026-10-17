"""KAORI identity-provider native card selection regression (#2280).

Uses the existing Playwright pytest infrastructure against the real catalog
selector partial and its production JS controller, without LDAP connections
or provider mutations.
"""

from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import Page, expect

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / 'app/templates'


def _definition(key: str, label: str, profile: str, flow: str) -> SimpleNamespace:
    return SimpleNamespace(
        provider_key=key,
        adapter_key='ldap' if profile == 'ldap' else key,
        family=SimpleNamespace(value='directory' if profile == 'ldap' else 'sso'),
        label=label,
        icon='network',
        flow=SimpleNamespace(value=flow),
        configuration_profile=profile,
        admission_policy='administrative_projection' if profile == 'ldap' else 'subject_allowlist',
        description='Provider identity from the KAORI catalog.',
        enabled_copy='Configuration stays disabled until validated.',
        admission_label='Admission Policy',
        admission_help='Provider-controlled policy.',
        client_secret_placeholder='KAORI_PROVIDER_SECRET',
    )


def test_provider_cards_select_ldap_by_pointer_and_keyboard(page: Page) -> None:
    env = Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=True)
    form = SimpleNamespace(
        provider_key=SimpleNamespace(
            name='provider_key',
            label=SimpleNamespace(text='Provider'),
            errors=[],
        )
    )
    definitions = [
        _definition('ldap_directory', 'LDAP / Active Directory', 'ldap', 'credentials'),
        _definition('google', 'Google OpenID Connect', 'browser_client', 'browser'),
        _definition('github', 'GitHub OAuth', 'browser_client', 'browser'),
    ]
    selector = env.get_template('access/identity_providers/partials/_provider_selector.html').render(
        form=form,
        provider_options=definitions,
        selected_definition=definitions[2],
    )
    # CSS reproduces the existing Tailwind positioning utility contract in
    # isolated set_content mode; application CSS itself is not loaded here.
    page.set_content(
        """<!doctype html><html><head><style>
        .relative { position: relative; }
        .absolute { position: absolute; }
        .inset-0 { inset: 0; }
        .z-10 { z-index: 10; }
        .h-full { height: 100%; }
        .w-full { width: 100%; }
        .opacity-0 { opacity: 0; }
        .cursor-pointer { cursor: pointer; }
        fieldset { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
        fieldset > div { min-width: 0; }
        fieldset label { display: flex; flex-direction: column; min-height: 145px;
                         border: 1px solid gray; padding: 12px; }
        [hidden] { display: none !important; }
        </style></head><body>
        <div data-provider-form-page><form data-provider-form>
        """
        + selector
        + """
        <div data-configuration-panel="ldap" hidden>
          <input data-ldap-field name="server_uri" disabled>
        </div>
        <div data-configuration-panel="browser_client">
          <input data-browser-field name="client_id">
        </div>
        <div data-provider-guidance id="guidance-ldap_directory" hidden>LDAP Guidance</div>
        <div data-provider-guidance id="guidance-google" hidden>Google Guidance</div>
        <div data-provider-guidance id="guidance-github">GitHub Guidance</div>
        <span data-enabled-copy></span>
        </form><div data-browser-callback>Browser callback</div></div>
        </body></html>
        """
    )
    page.add_script_tag(content=(ROOT / 'app/static/js/identity_provider_form.js').read_text(encoding='utf-8'))
    ldap = page.locator('input[data-provider-key="ldap_directory"]')
    github = page.locator('input[data-provider-key="github"]')
    expect(github).to_be_checked()
    expect(page.locator('#guidance-github')).to_be_visible()
    expect(page.locator('input[data-ldap-field]')).to_be_disabled()

    # Operator clicks inside the card body, not the browser's hidden radio position.
    card = page.locator('label[for="provider-key-ldap_directory"]')
    bounds = card.bounding_box()
    assert bounds is not None
    page.mouse.click(bounds['x'] + bounds['width'] / 2, bounds['y'] + bounds['height'] / 2)
    expect(ldap).to_be_checked()
    expect(github).not_to_be_checked()
    expect(page.locator('#guidance-ldap_directory')).to_be_visible()
    expect(page.locator('#guidance-github')).to_be_hidden()
    expect(page.locator('[data-configuration-panel="ldap"]')).to_be_visible()
    expect(page.locator('input[data-ldap-field]')).to_be_enabled()
    expect(page.locator('input[data-browser-field]')).to_be_disabled()
    expect(page.locator('[data-browser-callback]')).to_be_hidden()
    expect(card.locator('[data-provider-option-status]')).to_have_text('Selected')

    # Native keyboard navigation remains usable without a proxy button.
    ldap.focus()
    page.keyboard.press('ArrowRight')
    expect(page.locator('input[data-provider-key="google"]')).to_be_checked()
    expect(page.locator('#guidance-google')).to_be_visible()
    expect(page.locator('input[data-ldap-field]')).to_be_disabled()
    expect(page.locator('input[data-browser-field]')).to_be_enabled()
    expect(page.locator('[data-browser-callback]')).to_be_visible()

    page.keyboard.press('ArrowLeft')
    expect(ldap).to_be_checked()
    expect(page.locator('#guidance-ldap_directory')).to_be_visible()

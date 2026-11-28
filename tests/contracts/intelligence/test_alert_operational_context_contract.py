"""Page-owned alert context preserves exact scope while adapting to tab responsibilities."""

from pathlib import Path
from flask import Flask
from jinja2 import StrictUndefined

ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = ROOT / 'app/templates'
PARTIALS = TEMPLATES / 'intelligence/partials'
TABS = ('overview', 'active', 'routing', 'templates', 'silences', 'resolved')


def test_page_owns_one_context_before_hero_and_workspace() -> None:
    page = (PARTIALS / '_alert_intelligence_page.html').read_text()
    workspace = (PARTIALS / '_alert_intelligence_workspace.html').read_text()
    include = "{% include 'intelligence/partials/_alert_intelligence_context.html' %}"
    assert page.count(include) == 1
    assert page.index('workspace_tabs.render_navigation(') < page.index(include)
    assert page.index(include) < page.index('page_hero.shell_classes()')
    assert page.index(include) < page.index('_alert_intelligence_summary.html')
    assert 'id="alert-intelligence-context-form"' not in workspace


def test_context_render_adapts_without_widening_or_losing_scope() -> None:
    app = Flask(__name__, template_folder=str(TEMPLATES))
    app.add_url_rule('/intelligence/alert-intelligence', 'alert_intelligence.index', lambda: '')
    app.jinja_env.undefined = StrictUndefined
    template = app.jinja_env.get_template('intelligence/partials/_alert_intelligence_context.html')

    with app.test_request_context('/intelligence/alert-intelligence'):
        for domain in ('kubernetes', 'object_storage', 'registry', 'secrets_pki'):
            provider_mode = domain == 'secrets_pki'
            key = '17' if provider_mode else 'asset-123'
            for tab in TABS:
                payload = {
                    'tab': tab,
                    'domain': domain,
                    'domain_options': [{'value': domain, 'label': domain}],
                    'provider_case_mode': provider_mode,
                    'scope_invalid': False,
                    'selected_provider': 'vault' if provider_mode else '',
                    'provider_options': [{'value': 'vault', 'label': 'Vault'}] if provider_mode else [],
                    'selected_asset_key': key,
                    'selected_asset_name': 'Selected Asset',
                    'assets': [{'value': key, 'label': 'Selected Asset', 'environment': 'Production'}],
                }
                html = template.render(payload=payload)
                assert html.count('id="alert-intelligence-context-form"') == 1
                assert 'name="domain"' in html
                assert f'name="tab"\n                   value="{tab}"' in html
                editable = provider_mode or tab in ('overview', 'active', 'silences', 'resolved') or (
                    domain == 'registry' and tab == 'routing'
                )
                assert ('id="alert-intelligence-asset-select"' in html) == editable
                assert ('name="provider"' in html) == provider_mode
                if editable:
                    assert f'value="{key}"' in html
                    assert 'data-alert-retained-scope' not in html
                else:
                    assert f'type="hidden" name="asset" value="{key}"' in html
                    assert 'data-alert-retained-scope' in html
                    assert 'Change Scope' in html
                    assert f'asset={key}' in html
                assert ('Global notification templates' in html) == (tab == 'templates' and not provider_mode)

        payload.update({
            'tab': 'templates',
            'domain': 'registry',
            'provider_case_mode': False,
            'scope_invalid': True,
            'selected_asset_key': '__invalid_registry_scope__',
            'selected_asset_name': 'Unavailable Registry Provider',
            'assets': [{'value': '__invalid_registry_scope__', 'label': 'Unavailable Registry Provider',
                        'environment': 'Select an active provider'}],
        })
        html = template.render(payload=payload)
        assert 'id="alert-intelligence-asset-select"' in html
        assert 'value="__invalid_registry_scope__"' in html
        assert 'data-alert-retained-scope' not in html

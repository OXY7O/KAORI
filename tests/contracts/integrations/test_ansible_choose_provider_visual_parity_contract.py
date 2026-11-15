"""Issue #4854: reuse canonical Choose Provider UI for Ansible profile choices."""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

from flask import render_template

from app import create_app

ROOT = Path(__file__).resolve().parents[3]
CHOOSE = 'integrations/orchestration/configuration_automation/providers/ansible/choose.html'
CANONICAL = 'integrations/provider_selector.html'


def _render_choose(monkeypatch) -> str:
    app = create_app('testing')
    principal = SimpleNamespace(
        id=None,
        is_authenticated=False,
        username='ui-test',
        role_name='Viewer',
        has_permission=lambda _: False,
    )
    monkeypatch.setattr('flask_login.utils._get_user', lambda: principal)
    with app.test_request_context('/integrations/ansible/profiles'):
        return render_template(CHOOSE)


def test_choose_profile_renders_canonical_provider_selection_pattern(monkeypatch) -> None:
    rendered = _render_choose(monkeypatch)
    assert 'data-kaori-ansible-profile-choose' in rendered
    assert 'data-kaori-provider-card-grid' in rendered
    assert 'Choose an Automation Profile' in rendered
    assert 'Profile Admission' in rendered
    assert 'Source-First Setup' in rendered
    assert 'Registration Unavailable' in rendered
    assert rendered.index('Back to Ansible') < rendered.index('data-kaori-provider-card-grid')

    # Real registration is available only for the Kubespray source profile.
    assert rendered.count('data-kaori-provider-register') == 1
    assert rendered.count('data-kaori-provider-disabled') == 3
    assert rendered.count('data-kaori-provider-lifecycle="planned"') == 3
    assert rendered.count('data-kaori-provider-lifecycle="available"') == 1
    assert 'href="/integrations/ansible/connections/new"' in rendered
    assert rendered.count('Registration is not yet available.') == 3

    cards = re.findall(r'<article\b[^>]*data-kaori-(?:ansible-profile|provider-lifecycle)[^>]*>.*?</article>', rendered, re.S)
    assert len(cards) == 4
    assert 'data-kaori-provider-register' in cards[0]
    for card in cards[1:]:
        assert 'data-kaori-provider-disabled' in card
        assert re.search(r'<button\b[^>]*\bdisabled\b', card)
        assert not re.search(r'<a\b[^>]*href=', card), 'Planned profiles must not expose any registration URL'


def test_choose_page_reuses_existing_provider_card_primitives() -> None:
    choose = (ROOT / 'app/templates' / CHOOSE).read_text(encoding='utf-8')
    canonical = (ROOT / 'app/templates' / CANONICAL).read_text(encoding='utf-8')
    for fragment in (
        'page_hero.shell_classes()',
        'page_hero.context_panel_classes()',
        'page_hero.context_panel_metrics_classes()',
        'info_tip.render(',
        'table_label.status_label(',
        'integration_ui.palette_icon(',
        'data-kaori-provider-card-grid',
        "action_button.classes('primary', full=true)",
        "action_button.classes('locked-info', full=true)",
    ):
        assert fragment in choose or fragment.replace("'", '"') in choose
        assert fragment in canonical or fragment.replace("'", '"') in canonical

    assert "url_for('integrations.ansible_new_connection')" in choose
    assert 'disabled' in choose
    assert 'grid gap-4 md:grid-cols-2 xl:grid-cols-4' in choose
    assert 'sm:grid-cols-2' not in choose


def test_orchestration_compact_copy_does_not_change_provider_ownership() -> None:
    taxonomy = (ROOT / 'app/definitions/catalogs/integrations/taxonomy.yaml').read_text(encoding='utf-8')
    domain = (ROOT / 'app/templates/integrations/domain.html').read_text(encoding='utf-8')
    workspace = (ROOT / 'app/templates/integrations/partials/_domain_workspace.html').read_text(
        encoding='utf-8'
    )
    assert 'Git automation, provenance, and governance.' in taxonomy
    assert 'Cluster API access, inventory, and control-plane operations.' in taxonomy
    assert 'Defines provider ownership and managed asset bindings.' in domain
    assert 'Review providers, connections, and bindings.' in domain
    assert 'Manage connections and asset bindings.' in workspace
    assert 'Open Kubernetes' in workspace
    assert 'Open {{ item.runtime_label }}' in workspace  # Other domains retain their labels.
    assert "url_for(item.workspace_endpoint)" in workspace
    assert "url_for('integrations.choose_integration_provider', integration_type=item.key)" in workspace

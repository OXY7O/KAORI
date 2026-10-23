"""Directory Provisioning two-panel UI follows approved KAORI shared patterns (#2944)."""

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = 'app/templates/access/identity_providers/directory_provisioning.html'


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_hero_matches_existing_roles_and_provider_form_reference() -> None:
    source = read(TEMPLATE)
    roles = read('app/templates/access/roles/form.html')
    provider = read('app/templates/access/identity_providers/form.html')
    Environment().parse(source)

    assert 'page_hero.shell_classes()' in source
    assert 'page_hero.layout_classes()' in source
    assert 'page_hero.content_classes()' in source
    assert 'page_hero.intro(' in source
    assert source.count('page_hero.meta_label(') == 3
    assert 'page_hero.context_card(' in roles
    assert 'page_hero.context_card(' in provider
    assert source.count('page_hero.context_card(') == 1
    assert 'page_hero.context_panel_classes()' not in source
    assert 'page_hero.content_classes() }} xl:col-span-12' not in source
    assert 'Directory Boundary' not in source
    assert 'Provider Configuration Controls Discovery' not in source
    assert "url_for('identity_providers.index')" in source
    assert "url_for('users.index')" in source


def test_primary_and_right_guidance_use_shared_8_4_layout() -> None:
    source = read(TEMPLATE)
    shared = read('app/templates/components/form_with_context_rail.html')

    assert '{% import "components/form_with_context_rail.html" as form_context %}' in source
    assert 'form_context.layout_classes()' in source
    assert 'form_context.main_classes()' in source
    assert 'form_context.rail_classes()' in source
    assert "grid gap-6 xl:grid-cols-12 xl:items-start" in shared
    assert 'xl:col-span-8' in shared
    assert 'xl:col-span-4' in shared
    assert source.count('surface_ui.block_classes(allow_overflow=true)') == 1
    assert 'data-directory-search-results' in source
    assert 'form_context.main_classes() }} space-y-5' in source
    assert 'info_flow.render(' in source
    assert 'context_guidance.render(' in source
    assert 'open_by_default=false' in source
    assert 'Authentication Boundary' not in source


def test_title_level_guide_replaces_persistent_input_helpers() -> None:
    source = read(TEMPLATE)
    canonical = read('app/templates/components/info_tip.html')

    assert '{% import "components/info_tip.html" as info_tip %}' in source
    assert source.count('info_tip.render(') == 1
    assert "'directory-identity-search-guide'" in source
    assert "variant='guide'" in source
    assert 'data-kaori-info-tip-trigger' in canonical
    assert 'Only enabled directory providers are listed.' not in source
    assert 'Enter at least two characters to search the directory.</span>' not in source
    assert 'search_form.query.errors' in source
    assert 'role="alert"' in source
    assert 'role="status"' in source
    assert 'disabled=not has_directory_providers' in source


def test_identity_projection_security_and_actions_unchanged() -> None:
    source = read(TEMPLATE)

    assert source.count('<form ') == 2  # Search and per-identity Provision, never nested.
    assert source.count('</form>') == 2
    assert 'selected_provider.display_name' in source
    assert 'results|length' in source
    assert 'identity.display_name or identity.username' in source
    assert 'identity.username' in source
    assert 'identity.email' in source
    assert 'identity.distinguished_name' in source
    assert "url_for('identity_providers.provision_identity')" in source
    assert 'name="csrf_token"' in source
    assert 'name="provider_id"' in source
    assert 'name="projection_proof"' in source
    assert "projection_proofs.get(identity.subject, '')" in source
    assert 'name="role_id"' in source
    assert 'provision_form.role_id.choices' in source
    assert 'name="is_active"' in source
    assert 'checked' in source
    assert "action_button.classes('primary')" in source
    assert 'No Enabled Directory Provider' in source
    assert 'No Matching Directory Identity' in source
    assert 'Search the Directory to Begin' in source


def test_compact_guidance_keeps_external_credentials_authoritative() -> None:
    source = read(TEMPLATE)
    assert "info_flow.render('How Directory Provisioning Works'" in source
    assert "context_guidance.render('Before Searching'" in source
    assert 'KAORI links the identity; the directory retains credentials.' in source
    assert 'KAORI projects access; the directory owns credentials.' in source
    assert 'Authentication Boundary' not in source
    assert 'Credential Owner' not in source
    assert 'KAORI Stores' not in source

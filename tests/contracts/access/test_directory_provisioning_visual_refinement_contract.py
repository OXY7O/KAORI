"""Directory Provisioning visual UAT refinement with unchanged trust boundary (#2944)."""

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = 'app/templates/access/identity_providers/directory_provisioning.html'


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_hero_is_shared_full_width_without_nested_context_panel() -> None:
    source = read(TEMPLATE)
    Environment().parse(source)

    assert 'page_hero.shell_classes()' in source
    assert 'page_hero.layout_classes()' in source
    assert 'page_hero.content_classes() }} xl:col-span-12' in source
    assert 'page_hero.intro(' in source
    assert 'page_hero.metadata_row_classes()' in source
    assert source.count('page_hero.meta_label(') == 3
    assert 'page_hero.primary_action_classes()' in source
    assert "url_for('identity_providers.index')" in source
    assert "url_for('users.index')" in source
    assert 'page_hero.context_panel_classes()' not in source
    assert 'page_hero.aside_classes()' not in source
    assert 'Directory Boundary' not in source
    assert 'Provider Configuration Controls Discovery' not in source


def test_search_uses_one_canonical_section_guide_not_persistent_field_help() -> None:
    source = read(TEMPLATE)
    canonical = read('app/templates/components/info_tip.html')

    assert '{% import "components/info_tip.html" as info_tip %}' in source
    assert source.count('info_tip.render(') == 1
    assert "'directory-identity-search-guide'" in source
    assert "variant='guide'" in source
    assert 'surface_ui.block_classes(allow_overflow=true)' in source
    assert 'data-kaori-info-tip-trigger' in canonical
    assert 'Only enabled directory providers are listed.' not in source
    assert 'Enter at least two characters to search the directory.</span>' not in source
    assert 'Only enabled directory sources appear' not in source  # Guidance is title-owned.
    assert 'Provider: only enabled directory sources' in source
    assert 'Search: use at least two characters' in source
    assert 'search_form.query.errors' in source  # Errors cannot be hidden in a tooltip.
    assert 'role="status"' in source  # No-provider blocker stays visible.
    assert 'disabled=not has_directory_providers' in source


def test_result_identity_and_provisioning_contract_is_unchanged() -> None:
    source = read(TEMPLATE)
    assert 'surface_ui.block_classes()' in source
    assert 'Directory Search Results' in source
    assert 'selected_provider.display_name' in source
    assert "results|length" in source
    assert 'identity.display_name or identity.username' in source
    assert 'identity.username' in source
    assert 'identity.email' in source
    assert 'identity.distinguished_name' in source
    assert 'lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]' in source
    assert 'aria-label="KAORI access assignment"' in source
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


def test_copy_and_rail_are_concise_without_redundant_boundary() -> None:
    source = read(TEMPLATE)
    assert "info_flow.render('How Directory Provisioning Works'" in source
    assert "info_flow.render('Before Searching'" in source
    for text in (
        'Follow the controlled admin workflow for directory-backed access.',
        'KAORI verifies directory identity and stores its access link. Credentials stay directory-managed.',
        'KAORI projects access; the directory owns credentials.',
        'Check these requirements before searching.',
        'Confirm the provider is enabled and validated.',
        'Confirm the bind-secret variable reaches KAORI.',
        'Check for existing KAORI username or email conflicts.',
    ):
        assert text in source
    assert 'Authentication Boundary' not in source
    assert 'Credential Owner' not in source
    assert 'KAORI Stores' not in source

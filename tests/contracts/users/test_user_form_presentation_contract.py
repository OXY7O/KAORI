from pathlib import Path

import pytest

pytestmark = pytest.mark.contract

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ROOT / 'app/templates/users/form.html'


def test_user_form_uses_kaori_title_case_for_section_titles() -> None:
    content = TEMPLATE.read_text(encoding='utf-8')

    required_titles = {
        'Validation Error',
        'Display Name',
        'Initial Password',
        'Confirm Password',
        'Assigned Role',
        'Active Account',
        'Add User by Identity Provider',
        'Administrative Boundary',
        'Current Identity Source',
        'Editable Administrative Controls',
        'Editing Your Own Profile',
    }

    for title in required_titles:
        assert f'>{title}<' in content


def test_add_user_guidance_is_provider_specific() -> None:
    content = TEMPLATE.read_text(encoding='utf-8')

    assert 'Identity creation paths' not in content
    assert 'Complete This Form' in content
    assert 'Use Directory Provisioning' in content
    assert 'Use SSO Admission' in content
    assert "url_for('users.external_identities')" in content
    assert "url_for('users.providers')" in content


def test_edit_user_sidebar_contains_provider_context() -> None:
    content = TEMPLATE.read_text(encoding='utf-8')

    assert 'Current Identity Source' in content
    assert '{{ identity_context.provider_name }}' in content
    assert '{{ identity_context.credential_owner }}' in content


def test_add_user_provider_guidance_is_collapsible() -> None:
    content = TEMPLATE.read_text(encoding='utf-8')

    heading_index = content.index('Add User by Identity Provider')
    details_index = content.rfind('<details', 0, heading_index)
    summary_index = content.rfind('<summary', 0, heading_index)
    closing_index = content.index('</details>', heading_index)

    assert details_index != -1
    assert summary_index > details_index
    assert closing_index > heading_index
    assert 'group-open:rotate-180' in content[summary_index:closing_index]


def test_related_user_management_reuses_integration_related_card_component() -> None:
    content = TEMPLATE.read_text(encoding='utf-8')

    assert '{% import "components/related_page_card.html" as related_page_card %}' in content
    assert content.count('related_page_card.render(') == 4
    assert content.count("eyebrow='Related User Management'") == 4
    assert 'border border-brand-outline bg-kaori-soft shadow-sm' not in content
    assert 'border-brand-outline bg-surface-card/80' not in content


def test_related_user_management_is_provider_aware() -> None:
    content = TEMPLATE.read_text(encoding='utf-8')

    assert "user.auth_source == 'ldap'" in content
    assert "user.auth_source == 'database'" in content
    assert "'LDAP Directory Provisioning'" in content
    assert "'User Registry'" in content
    assert "'Identity Providers'" in content
    assert "boundary=identity_context.provider_name ~" in content


def test_add_and_edit_user_hero_uses_compact_kaori_context_panel() -> None:
    content = TEMPLATE.read_text(encoding='utf-8')

    assert "{{ 'Creation Scope' if mode == 'create' else 'Identity Context' }}" in content
    assert "{{ 'Credential Owner' if mode == 'create' else 'Provider Type' }}" in content
    assert "{{ 'Provisioning' if mode == 'create' else 'Account State' }}" in content
    assert "Create Local Database users here. Provision LDAP users" not in content
    assert "remains the authoritative authentication source. This page updates" not in content
    assert 'w-full items-center justify-center gap-2 rounded-lg border border-white/80 bg-white' in content


def test_add_user_provider_guidance_is_open_by_default() -> None:
    content = TEMPLATE.read_text(encoding='utf-8')

    heading_index = content.index('Add User by Identity Provider')
    details_index = content.rfind('<details open', 0, heading_index)

    assert details_index != -1

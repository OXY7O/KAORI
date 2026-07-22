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
        'Related User Management',
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


def test_edit_user_sidebar_contains_provider_and_related_context() -> None:
    content = TEMPLATE.read_text(encoding='utf-8')

    assert 'Current Identity Source' in content
    assert '{{ identity_context.provider_name }}' in content
    assert '{{ identity_context.credential_owner }}' in content
    assert content.count('Related User Management') == 2

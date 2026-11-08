"""Role-aware Welcome capability entry for Secrets & PKI."""

from app.welcome.shortcuts import WELCOME_SHORTCUT_DEFINITIONS, resolve_welcome_target


def test_secrets_pki_has_one_provider_neutral_welcome_shortcut():
    matches = [item for item in WELCOME_SHORTCUT_DEFINITIONS if item['title'] == 'Secrets & PKI']
    assert len(matches) == 1
    shortcut = matches[0]
    assert shortcut['group'] == 'visibility'
    assert shortcut['targets'] == (('secrets_pki.view', 'secrets_pki.overview'),)
    assert 'Vault' in shortcut['description']
    assert 'Secret values' in shortcut['description']


def test_welcome_secret_entry_is_permission_gated():
    shortcut = next(item for item in WELCOME_SHORTCUT_DEFINITIONS if item['title'] == 'Secrets & PKI')
    assert resolve_welcome_target(shortcut['targets'], lambda permission: False) is None
    assert (
        resolve_welcome_target(
            shortcut['targets'],
            lambda permission: permission == 'secrets_pki.view',
        )
        == 'secrets_pki.overview'
    )


def test_provider_specific_cards_are_not_duplicated_at_workspace_level():
    assert not any(item['title'] in {'Vault', 'Vault PKI', 'Vault Secrets'} for item in WELCOME_SHORTCUT_DEFINITIONS)
    integrations = next(item for item in WELCOME_SHORTCUT_DEFINITIONS if item['title'] == 'Integrations')
    assert 'secrets management' in integrations['description']
    assert integrations['targets'] == (('integrations.manage', 'integrations.overview'),)

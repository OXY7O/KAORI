from __future__ import annotations

from app.users.identity import identity_source_definition, password_is_managed_by_kaori


def test_concrete_sso_sources_map_to_sso_family() -> None:
    assert identity_source_definition('google_oidc').key == 'sso'
    assert identity_source_definition('github_oauth').key == 'sso'


def test_only_database_accounts_use_kaori_password_management() -> None:
    assert password_is_managed_by_kaori('database') is True
    assert password_is_managed_by_kaori('ldap') is False
    assert password_is_managed_by_kaori('google_oidc') is False
    assert password_is_managed_by_kaori('github_oauth') is False
    assert password_is_managed_by_kaori('future_external_provider') is False

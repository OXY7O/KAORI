"""Linked Identity Provider instance identity remains immutable without governed relinking."""

from types import SimpleNamespace

import pytest

from app.access.identity_providers.service import (
    ProviderIdentityRebindError,
    ensure_provider_identity_continuity,
)


def _provider(*, linked: bool):
    return SimpleNamespace(
        key='google-workspace',
        provider_key='google',
        identity_links=SimpleNamespace(first=lambda: object() if linked else None),
    )


def _candidate(*, key: str = 'google-workspace', provider_key: str = 'google'):
    return SimpleNamespace(key=key, provider_key=provider_key)


@pytest.mark.parametrize('attribute,value', [
    ('key', 'other-callback'),
    ('provider_key', 'github'),
])
def test_linked_provider_rebind_fails_closed(attribute: str, value: str) -> None:
    provider = _provider(linked=True)
    config = _candidate(**{attribute: value})
    with pytest.raises(ProviderIdentityRebindError, match='linked identities'):
        ensure_provider_identity_continuity(provider, config)
    assert provider.key == 'google-workspace'
    assert provider.provider_key == 'google'


def test_linked_provider_allows_same_authority_configuration_edits() -> None:
    ensure_provider_identity_continuity(_provider(linked=True), _candidate())


def test_unlinked_provider_allows_explicit_reconfiguration() -> None:
    provider = _provider(linked=False)
    ensure_provider_identity_continuity(provider, _candidate(provider_key='github', key='github-org'))

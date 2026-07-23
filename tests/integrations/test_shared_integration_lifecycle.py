from types import SimpleNamespace

import pytest

from app.integrations.lifecycle import ensure_provider_operational


def _provider(*, enabled: bool = True, canonical_enabled: bool = True, lifecycle: str = 'active'):
    return SimpleNamespace(
        enabled=enabled,
        integration_instance=SimpleNamespace(
            enabled=canonical_enabled,
            lifecycle_status=lifecycle,
        ),
    )


def test_operational_provider_returns_canonical_identity() -> None:
    provider = _provider()

    canonical = ensure_provider_operational(provider, provider_type='prometheus')

    assert canonical is provider.integration_instance


@pytest.mark.parametrize(
    ('provider', 'message'),
    [
        (_provider(enabled=False), 'provider instance is disabled'),
        (_provider(canonical_enabled=False), 'integration is no longer active'),
        (_provider(lifecycle='deleting'), 'integration is no longer active'),
        (SimpleNamespace(enabled=True, integration_instance=None), 'canonical integration identity is missing'),
    ],
)
def test_non_operational_provider_fails_closed(provider, message: str) -> None:
    with pytest.raises(RuntimeError, match=message):
        ensure_provider_operational(provider, provider_type='alertmanager')

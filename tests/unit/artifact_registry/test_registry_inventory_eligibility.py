from types import SimpleNamespace

import pytest

from app.artifact_registry import eligibility


@pytest.mark.parametrize(
    ('readiness', 'compatibility_status', 'expected'),
    [
        ('ready', 'compatible', True),
        ('degraded', 'compatible_with_warnings', True),
        ('degraded', 'unverified_version', False),
        ('blocked', 'capability_mismatch', False),
        ('validation_required', None, False),
    ],
)
def test_inventory_read_contract_eligibility_matrix(
    readiness: str,
    compatibility_status: str | None,
    expected: bool,
) -> None:
    assert eligibility.inventory_read_contract_eligible(readiness, compatibility_status) is expected


def test_extended_support_provider_is_inventory_eligible(monkeypatch) -> None:
    identity = SimpleNamespace(
        id=42,
        integration_type='registry',
        enabled=True,
        lifecycle_status='active',
        readiness_status='degraded',
    )
    runtime_state = SimpleNamespace(
        readiness='degraded',
        snapshot=SimpleNamespace(metadata={'compatibility_status': 'compatible_with_warnings'}),
    )
    module = SimpleNamespace(
        require_record_for_canonical=lambda _identity_id: object(),
        runtime_state=lambda _record: runtime_state,
    )
    monkeypatch.setattr(eligibility, 'get_integration', lambda _integration_type: module)

    decision = eligibility.registry_inventory_eligibility(identity)

    assert decision.eligible is True
    assert decision.readiness == 'degraded'
    assert decision.compatibility_status == 'compatible_with_warnings'


def test_unverified_degraded_provider_is_not_inventory_eligible(monkeypatch) -> None:
    identity = SimpleNamespace(
        id=42,
        integration_type='registry',
        enabled=True,
        lifecycle_status='active',
        readiness_status='degraded',
    )
    runtime_state = SimpleNamespace(
        readiness='degraded',
        snapshot=SimpleNamespace(metadata={'compatibility_status': 'unverified_version'}),
    )
    module = SimpleNamespace(
        require_record_for_canonical=lambda _identity_id: object(),
        runtime_state=lambda _record: runtime_state,
    )
    monkeypatch.setattr(eligibility, 'get_integration', lambda _integration_type: module)

    decision = eligibility.registry_inventory_eligibility(identity)

    assert decision.eligible is False
    assert decision.compatibility_status == 'unverified_version'

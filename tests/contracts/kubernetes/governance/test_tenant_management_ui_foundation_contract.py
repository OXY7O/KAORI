from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
CONTRACT = ROOT / 'docs' / 'design' / 'patterns' / 'KUBERNETES_TENANT_MANAGEMENT.md'
DESIGN_INDEX = ROOT / 'docs' / 'design' / 'README.md'


def test_tenant_management_ui_foundation_contract_is_registered_and_complete() -> None:
    assert CONTRACT.is_file(), 'Tenant Management UI foundation contract is missing'

    contract = CONTRACT.read_text(encoding='utf-8')
    design_index = DESIGN_INDEX.read_text(encoding='utf-8')

    assert '`patterns/KUBERNETES_TENANT_MANAGEMENT.md`' in design_index
    assert 'Status: PRE-IMPLEMENTATION CONTRACT' in contract
    assert 'not release-visible' in contract
    assert 'one global sidebar destination' in contract
    assert 'Kubernetes Governance' in contract

    for module in (
        'Overview',
        'Tenants',
        'Namespaces',
        'Members & Access',
        'CI/CD',
        'Credentials',
        'Resource Profiles',
        'Managed Resources',
        'Policies',
        'Activity',
        'Providers',
    ):
        assert f'- {module}' in contract

    assert 'Native Kubernetes' in contract
    assert 'Capsule' in contract
    assert 'unavailable' in contract
    assert 'degraded' in contract
    assert 'read-only / recovery' in contract
    assert 'actionable' in contract
    assert 'permission keys remain reserved until backend authorization ownership is admitted' in contract
    assert '#112' in contract
    assert '#114' in contract
    assert '#125' in contract

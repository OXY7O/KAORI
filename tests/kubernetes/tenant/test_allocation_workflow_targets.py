"""Active Allocation Change selectors must not expose Released/re-adopted history (#1159)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import app.kubernetes.tenant.service as tenant_service
from app.kubernetes.tenant.registry_context import _allocation_workflow_target_options


def _row(
    tenant_id: str,
    *,
    tenant_status: str = 'ready',
    namespace_status: str = 'ready',
    provider: str = 'native_kubernetes',
    ownership: str = 'adopted',
    control: str = 'kaori_managed',
    namespace_id: int = 1,
):
    tenant = SimpleNamespace(
        id=tenant_id,
        name='tenant-uat-demo',
        lifecycle_status=tenant_status,
        provider_key=provider,
    )
    return SimpleNamespace(
        id=namespace_id,
        namespace='tenant-uat-demo',
        environment=SimpleNamespace(tenant=tenant),
        provisioning_status=namespace_status,
        ownership_status=ownership,
        provisioning_evidence_json={'allocation_control_state': control},
    )


def test_two_released_generations_and_one_readopted_ready_yield_one_managed_option():
    history = [
        _row('old-1', tenant_status='released', namespace_status='released', namespace_id=1),
        _row('old-2', tenant_status='released', namespace_status='ready', namespace_id=2),
    ]
    current = _row('new-3', namespace_id=3)
    records = [*history, current]

    managed, cutover = _allocation_workflow_target_options(records)

    assert [record.id for record in managed] == [3]
    assert cutover == []
    assert len(records) == 3  # Registry and verified generation lineage remain intact.


@pytest.mark.parametrize('terminal', ['released', 'deprovisioned'])
def test_terminal_namespace_under_ready_tenant_is_not_actionable(terminal):
    record = _row('ready-tenant', namespace_status=terminal)
    managed, cutover = _allocation_workflow_target_options([record])
    assert managed == []
    assert cutover == []


def test_active_native_and_capsule_workflow_roles_stay_explicit():
    managed_native = _row('native', namespace_id=1)
    managed_capsule = _row('capsule', provider='capsule', namespace_id=2)
    observed_native = _row('native-observed', control='adopted_observed', namespace_id=3)
    observed_capsule = _row('capsule-observed', provider='capsule', control='adopted_observed', namespace_id=4)
    released_capsule = _row(
        'capsule-released', tenant_status='released', provider='capsule',
        control='adopted_observed', namespace_id=5,
    )
    managed, cutover = _allocation_workflow_target_options(
        [managed_native, managed_capsule, observed_native, observed_capsule, released_capsule]
    )
    assert [record.id for record in managed] == [1]
    assert [record.id for record in cutover] == [3, 4]  # Capsule remains visible as disabled.


def test_same_named_independently_active_records_remain_distinct_by_id():
    first = _row('tenant-a', namespace_id=6)
    second = _row('tenant-b', namespace_id=7)
    managed, _ = _allocation_workflow_target_options([first, second])
    assert [row.id for row in managed] == [6, 7]  # Do not deduplicate by display name.


@pytest.mark.parametrize('terminal', ['released', 'deprovisioned'])
def test_stale_post_cannot_mutate_terminal_managed_generation(monkeypatch, terminal):
    record = _row('ready-tenant', namespace_status=terminal)
    profile = SimpleNamespace(enabled=True)
    monkeypatch.setattr(
        tenant_service.db.session,
        'get',
        lambda model, _object_id: (
            record if model is tenant_service.TenantNamespace else profile
        ),
    )
    with pytest.raises(ValueError, match='Released or deprovisioned Namespace'):
        tenant_service.change_native_namespace_allocation({
            'tenant_namespace_id': '1',
            'resource_profile_id': '3',
        })


@pytest.mark.parametrize('terminal', ['released', 'deprovisioned'])
def test_stale_post_cannot_cutover_terminal_observed_generation(monkeypatch, terminal):
    record = _row('ready-tenant', namespace_status=terminal, control='adopted_observed')
    monkeypatch.setattr(
        tenant_service.db.session, 'get', lambda _model, _object_id: record,
    )
    with pytest.raises(ValueError, match='Released or deprovisioned Namespace'):
        tenant_service.cutover_adopted_namespace_allocation({
            'tenant_namespace_id': '1',
        })


def test_active_selector_and_terminal_post_guards_are_wired_into_existing_registry():
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    registry = (root / 'app/kubernetes/tenant/registry_context.py').read_text(encoding='utf-8')
    forms = (root / 'app/templates/kubernetes/tenant/partials/_allocation_change.html').read_text(
        encoding='utf-8'
    )
    assert 'namespace_options = TenantNamespace.query.order_by(' in registry
    assert 'namespace_allocation_options, namespace_cutover_options = _allocation_workflow_target_options(' in registry
    assert "'namespace_options': namespace_options" in registry
    assert '{% for item in namespace_allocation_options %}' in forms
    assert '<option value="{{ item.id }}">' in forms

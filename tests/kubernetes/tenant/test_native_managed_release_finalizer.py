"""#1049 managed Native Release remains provider-preserving and evidence-bound."""

from __future__ import annotations

import pytest

from app.kubernetes.tenant.release_preflight import release_verified_native_tenant_committed


def test_native_managed_release_cannot_skip_explicit_confirmation():
    with pytest.raises(ValueError, match='Explicit provider-preserving'):
        release_verified_native_tenant_committed(
            tenant_id='tenant-a', actor_user_id=42,
            plan_sha256='a' * 64, approved=False,
        )


def test_missing_verified_handoff_cannot_commit_native_release(monkeypatch):
    from app.kubernetes.tenant import release_handoff_approval as approval
    from app.kubernetes.tenant import native_handoff_executor as executor
    from app.kubernetes.tenant import native_handoff_readback as readback
    from app.kubernetes.tenant import native_successor_acceptance as consent

    monkeypatch.setattr(approval, 'latest_release_handoff_plan', lambda _: None)
    monkeypatch.setattr(approval, 'latest_release_handoff_approval', lambda _: None)
    monkeypatch.setattr(consent, 'latest_native_successor_acceptance', lambda _: None)
    monkeypatch.setattr(executor, 'latest_native_handoff_execution', lambda _: None)
    monkeypatch.setattr(readback, '_latest_native_dry_run', lambda _: None)
    with pytest.raises(ValueError, match='Fully verified'):
        release_verified_native_tenant_committed(
            tenant_id='tenant-a', actor_user_id=42,
            plan_sha256='a' * 64, approved=True,
        )


def test_native_managed_finalizer_reuses_canonical_released_history_without_provider_writes():
    from pathlib import Path
    source = (
        Path(__file__).resolve().parents[3]
        / 'app/kubernetes/tenant/release_preflight.py'
    ).read_text(encoding='utf-8')
    start = source.index('def release_verified_native_tenant_committed(')
    fragment = source[start:]
    assert "TenantLifecycleStatus.RELEASED.value" in fragment
    assert "TenantNamespaceProvisioningStatus.RELEASED.value" in fragment
    assert "verify_external_native_component(" in fragment
    assert "'release_mode': 'managed_handoff'" in fragment
    assert "'provider_resource_deleted': False" in fragment
    assert "with_for_update()" in fragment
    for forbidden in (
        'patch_namespace(', 'delete_namespace(', 'create_namespace(',
        'replace_namespaced_resource_quota(', 'delete_namespaced_resource_quota(',
    ):
        assert forbidden not in fragment

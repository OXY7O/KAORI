"""Focused fail-closed tests for committed Native Release ancestry (#1138)."""

from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.kubernetes.tenant.registry_context import (
    _matches_verified_native_profile_predecessor,
)
from app.models.tenant import TenantLifecycleStatus


def _verified_chain():
    current = SimpleNamespace(
        id="tenant-gen-3",
        cluster_id="cluster-a",
        slug="tenant-uat-demo",
        provider_key="native_kubernetes",
        generation=3,
        correlation_id="corr-3",
        provider_reference="tenant-uat-demo",
        provider_evidence_json={"provider_uid": "immutable-ns-uid"},
    )
    previous = SimpleNamespace(
        id="tenant-gen-2",
        cluster_id="cluster-a",
        slug="tenant-uat-demo",
        provider_key="native_kubernetes",
        generation=2,
        correlation_id="corr-2",
        provider_reference="tenant-uat-demo",
        lifecycle_status=TenantLifecycleStatus.RELEASED.value,
        provider_evidence_json={
            "provider_uid": "immutable-ns-uid",
            "release_governance": {"status": "released"},
        },
    )
    lineage = {
        "predecessor_tenant_id": previous.id,
        "predecessor_generation": previous.generation,
        "predecessor_correlation_id": previous.correlation_id,
        "provider_uid_verified": True,
    }
    return current, previous, lineage


def test_explicit_verified_predecessor_correlates_same_provider_identity():
    current, previous, lineage = _verified_chain()
    assert _matches_verified_native_profile_predecessor(
        current, current, previous, lineage,
    )


@pytest.mark.parametrize(
    "location,field,value",
    [
        ("predecessor", "cluster_id", "other-cluster"),
        ("predecessor", "slug", "other-tenant"),
        ("predecessor", "provider_key", "capsule"),
        ("predecessor", "lifecycle_status", "ready"),
        ("predecessor", "generation", 4),
        ("predecessor", "correlation_id", "different"),
        ("predecessor", "provider_reference", "other-namespace"),
        ("current", "provider_reference", "other-namespace"),
        ("lineage", "predecessor_tenant_id", "unknown"),
        ("lineage", "predecessor_generation", 1),
        ("lineage", "predecessor_correlation_id", "forged"),
        ("lineage", "provider_uid_verified", False),
    ],
)
def test_name_match_alone_cannot_claim_historical_release(
    location, field, value,
):
    current, previous, lineage = _verified_chain()
    target = {
        "predecessor": previous, "current": current, "lineage": lineage,
    }[location]
    if isinstance(target, dict):
        target[field] = value
    else:
        setattr(target, field, value)
    assert not _matches_verified_native_profile_predecessor(
        current, current, previous, lineage,
    )


@pytest.mark.parametrize(
    "location,changes",
    [
        ("current", {"provider_uid": "recreated-uid"}),
        ("previous", {"provider_uid": "recreated-uid"}),
        ("previous", {"release_governance": {"status": "pending"}}),
        ("previous", {"release_governance": {}}),
        ("current", {"provider_uid": ""}),
    ],
)
def test_prior_release_requires_matching_uid_and_committed_released_evidence(
    location, changes,
):
    current, previous, lineage = _verified_chain()
    changed = deepcopy(
        current.provider_evidence_json
        if location == "current" else previous.provider_evidence_json
    )
    changed.update(changes)
    if location == "current":
        current.provider_evidence_json = changed
    else:
        previous.provider_evidence_json = changed
    assert not _matches_verified_native_profile_predecessor(
        current, current, previous, lineage,
    )


def test_no_previous_tenant_cannot_prove_cross_tenant_history():
    current, _, lineage = _verified_chain()
    assert not _matches_verified_native_profile_predecessor(
        current, current, None, lineage,
    )

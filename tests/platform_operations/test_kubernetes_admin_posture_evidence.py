"""Configured Kubernetes Reveal controls never imply live RBAC/namespace proof."""

from app.platform_operations.kubernetes.presentation import _administration_posture


def _status(*, clusters=1, ready=1, enabled=1, eligible=1, gate=True):
    return _administration_posture(
        cluster_count=clusters,
        ready_cluster_count=ready,
        enabled_namespace_count=enabled,
        eligible_policy_count=eligible,
        global_reveal_enabled=gate,
    )[0]


def test_admin_posture_requires_policy_on_canonical_ready_cluster():
    assert _status(clusters=0, ready=0, enabled=0) == 'Setup Required'
    assert _status(gate=False) == 'Global Gate Disabled'
    assert _status(ready=0) == 'Readiness Review'
    assert _status(clusters=2, ready=1) == 'Partial Readiness'
    assert _status(enabled=0, eligible=0) == 'Policy Required'
    assert _status(eligible=0) == 'Policy Scope Review'
    assert _status(eligible=1) == 'Verification Required'


def test_configured_policy_does_not_claim_live_operational_evidence():
    assert _status(eligible=1) != 'Operational'

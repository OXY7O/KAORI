"""Fail-closed Native release/readopt checkpoints from committed evidence only."""
from __future__ import annotations

from datetime import UTC, datetime

from app.kubernetes.tenant.native_release_readiness import project_native_release_readiness


def evidence(*, reviewed: bool = True, approved: bool = True, dry_run: bool = True):
    now = datetime.now(UTC).isoformat()
    plan = {
        "plan_sha256": "a" * 64,
        "status": "pending_independent_approval",
        "requested_by": 11,
    }
    review = {
        "handoff_required_count": 2,
        "handoff_components": [{"kind": "Namespace", "name": "test"}],
        "checked_at": now,
    } if reviewed else None
    approval = {
        "plan_sha256": "a" * 64,
        "status": "acknowledged_pending_provider_handoff",
        "requested_by": 11,
        "approved_by": 12,
        "approved_at": now,
    } if approved else None
    preview = {
        "plan_sha256": "a" * 64,
        "status": "dry_run_passed",
        "provider_mutation_performed": False,
        "checked_at": now,
    } if dry_run else None
    return dict(
        preflight=review, plan=plan, approval=approval,
        successor_claim=None, dry_run=preview, readback=None,
    )


def test_independent_approval_and_dry_run_do_not_grant_release():
    projection = project_native_release_readiness(**evidence())
    assert projection["review_complete"] is True
    assert projection["approval_complete"] is True
    assert projection["dry_run_passed"] is True
    assert projection["completed_count"] == 2
    assert projection["total_count"] == 5
    assert projection["execute_admitted"] is False
    assert projection["release_admitted"] is False
    assert [stage["complete"] for stage in projection["stages"]] == [
        True, True, False, False, False
    ]


def test_wrong_actor_or_plan_fingerprint_cannot_complete_approval():
    invalid = evidence()
    invalid["approval"]["approved_by"] = 11
    assert not project_native_release_readiness(**invalid)["approval_complete"]
    invalid = evidence()
    invalid["approval"]["plan_sha256"] = "b" * 64
    assert not project_native_release_readiness(**invalid)["approval_complete"]


def test_external_reference_is_not_successor_acceptance():
    snapshot = evidence()
    snapshot["successor_claim"] = {
        "plan_sha256": "a" * 64,
        "status": "external_reference_unverified",
    }
    status = project_native_release_readiness(**snapshot)
    assert status["reference_recorded"] is True
    assert status["stages"][2]["complete"] is False
    assert status["execute_admitted"] is False


def test_observed_provider_readback_is_not_successor_consent():
    snapshot = evidence()
    snapshot["readback"] = {
        "plan_sha256": "a" * 64,
        "status": "provider_handoff_observed_acceptance_unverified",
        "external_successor_verified": False,
    }
    status = project_native_release_readiness(**snapshot)
    assert status["readback_observed_unverified"] is True
    assert status["stages"][2]["complete"] is False
    assert status["stages"][3]["complete"] is False
    assert status["release_admitted"] is False


def test_unreviewed_or_unapproved_plan_shows_pending_not_fake_success():
    snapshot = evidence(reviewed=False, approved=False, dry_run=False)
    result = project_native_release_readiness(**snapshot)
    assert result["completed_count"] == 0
    assert not result["approval_complete"]
    assert not result["dry_run_passed"]


def test_no_live_provider_or_database_mutation_in_normal_read_model():
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    source = (root / "app/kubernetes/tenant/native_release_readiness.py").read_text()
    context = (root / "app/kubernetes/tenant/registry_context.py").read_text()
    template = (
        root / "app/templates/kubernetes/tenant/partials/_tenant_registry.html"
    ).read_text()
    for forbidden in (
        "runtime_adapter.build_client", "patch_namespace(", "db.session.commit(",
        "requests.get(", "release_adopted_tenant_committed(",
    ):
        assert forbidden not in source
    assert "project_native_release_readiness(" in context
    assert "Native Release &amp; Re-adopt Readiness" in template
    assert "and not row.release_preflight.blockers" in template

"""Committed-evidence Native Release readiness, never a mutation authority.

This deliberately does not infer trusted successor acceptance from a local
KAORI approval, a text reference, a provider label, or dry-run/read-back.
#1047 must admit an identity-backed acceptance contract before execution.
"""
from __future__ import annotations

from typing import Any, Mapping

from app.kubernetes.tenant.release_handoff_approval import _checked_recently


def project_native_release_readiness(
    *,
    preflight: Mapping[str, Any] | None,
    plan: Mapping[str, Any] | None,
    approval: Mapping[str, Any] | None,
    successor_claim: Mapping[str, Any] | None,
    dry_run: Mapping[str, Any] | None,
    readback: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Display checkpoints only; no provider calls, audit writes, or admission."""
    plan_sha = str((plan or {}).get("plan_sha256") or "")
    active_plan = bool(
        len(plan_sha) == 64
        and plan
        and plan.get("status") == "pending_independent_approval"
        and _checked_recently(plan.get("requested_at"))
    )
    review_current = bool(
        preflight
        and preflight.get("handoff_required_count", 0) > 0
        and preflight.get("handoff_components")
        and _checked_recently(preflight.get("checked_at"))
    )
    same_plan = bool(
        active_plan and approval
        and approval.get("plan_sha256") == plan_sha
        and approval.get("requested_by") == plan.get("requested_by")
        and approval.get("approved_by") != plan.get("requested_by")
        and isinstance(approval.get("approved_by"), int)
        and approval.get("status") == "acknowledged_pending_provider_handoff"
        and _checked_recently(approval.get("approved_at"))
    )
    preview_passed = bool(
        same_plan and dry_run
        and dry_run.get("plan_sha256") == plan_sha
        and dry_run.get("status") == "dry_run_passed"
        and dry_run.get("provider_mutation_performed") is False
        and _checked_recently(dry_run.get("checked_at"))
    )
    reference_recorded = bool(
        same_plan and successor_claim
        and successor_claim.get("plan_sha256") == plan_sha
        and successor_claim.get("status") == "external_reference_unverified"
    )
    # The existing native read-back deliberately observes without trusted
    # acceptance; never turn this into verified provider transfer.
    readback_observed = bool(
        readback and readback.get("plan_sha256") == plan_sha
        and readback.get("status") == "provider_handoff_observed_acceptance_unverified"
        and readback.get("external_successor_verified") is False
    )
    stages = (
        ("Release review", review_current,
         "Current provider inventory and dependency evidence must be reviewed."),
        ("Independent approval", same_plan,
         "A different authorized KAORI operator acknowledges this exact plan."),
        ("Verified successor acceptance", False,
         "No approved Kubernetes/IdP principal mapping and consent verifier is integrated."),
        ("KAORI provider handoff", False,
         "Live ownership transfer executor is not yet admitted; Native dry-run is not execution."),
        ("Released and Re-adopt", False,
         "Canonical Released commit and new-generation Re-adopt require verified handoff."),
    )
    return {
        "stages": [
            {"label": label, "complete": complete, "detail": detail}
            for label, complete, detail in stages
        ],
        "review_complete": review_current,
        "approval_complete": same_plan,
        "dry_run_passed": preview_passed,
        "reference_recorded": reference_recorded,
        "readback_observed_unverified": readback_observed,
        "completed_count": sum(int(complete) for _, complete, _ in stages),
        "total_count": len(stages),
        "execute_admitted": False,
        "release_admitted": False,
    }

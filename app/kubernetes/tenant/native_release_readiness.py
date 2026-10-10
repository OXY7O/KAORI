"""Committed-evidence Native Release readiness, never a mutation authority.

This deliberately does not infer trusted successor acceptance from a local
KAORI approval, a text reference, a provider label, or dry-run/read-back.
#1047 must admit an identity-backed acceptance contract before execution.
"""
from __future__ import annotations

import re
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
    successor_acceptance: Mapping[str, Any] | None = None,
    handoff_execution: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Display checkpoints only; no provider calls, audit writes, or admission."""
    plan_sha = str((plan or {}).get("plan_sha256") or "")
    active_plan = bool(
        bool(re.fullmatch(r'[0-9a-f]{64}', plan_sha))
        and plan
        and plan.get("status") == "pending_independent_approval"
        and _checked_recently(plan.get("requested_at"))
    )
    review_current = bool(
        preflight
        and type(preflight.get("handoff_required_count")) is int
        and preflight["handoff_required_count"] > 0
        and preflight.get("handoff_components")
        and _checked_recently(preflight.get("checked_at"))
    )
    approval_recorded = bool(
        plan and approval
        and bool(re.fullmatch(r'[0-9a-f]{64}', plan_sha))
        and plan.get("status") == "pending_independent_approval"
        and approval.get("plan_sha256") == plan_sha
        and approval.get("requested_by") == plan.get("requested_by")
        and approval.get("approved_by") != plan.get("requested_by")
        and type(approval.get("approved_by")) is int
        and approval.get("status") == "acknowledged_pending_provider_handoff"
    )
    same_plan = bool(
        active_plan and approval_recorded
        and _checked_recently(approval.get("approved_at"))
    )
    approval_expired = bool(approval_recorded and not same_plan)
    review_expired = bool(
        preflight
        and type(preflight.get("handoff_required_count")) is int
        and preflight.get("handoff_required_count", 0) > 0
        and preflight.get("handoff_components")
        and not _checked_recently(preflight.get("checked_at"))
    )
    readback_for_plan = bool(
        (readback and readback.get("plan_sha256") == plan_sha)
        or (handoff_execution and handoff_execution.get("plan_sha256") == plan_sha)
    )
    restart_required = bool(approval_expired and not readback_for_plan)
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
        same_plan and readback and readback.get("plan_sha256") == plan_sha
        and readback.get("status") == "provider_handoff_observed_acceptance_unverified"
        and readback.get("external_successor_verified") is False
    )
    verified_acceptance = bool(
        same_plan and successor_acceptance
        and successor_acceptance.get("plan_sha256") == plan_sha
        and successor_acceptance.get("handoff_fingerprint") == plan.get("handoff_fingerprint")
        and successor_acceptance.get("provider_identity") == plan.get("provider_identity")
        and successor_acceptance.get("successor_owner") == plan.get("successor_owner")
        and successor_acceptance.get("reviewed_by") == approval.get("approved_by")
        and successor_acceptance.get("status") == "verified_explicit_successor_acceptance"
        and successor_acceptance.get("consent_verified") is True
        and successor_acceptance.get("resource_authority_verified") is True
        and _checked_recently(successor_acceptance.get("accepted_at"))
    )
    provider_transfer_verified = bool(
        handoff_execution
        and handoff_execution.get("status") == "provider_handoff_verified"
        and handoff_execution.get("plan_sha256") == plan_sha
        and handoff_execution.get("handoff_fingerprint") == (plan or {}).get("handoff_fingerprint")
        and handoff_execution.get("provider_handoff_verified") is True
        and handoff_execution.get("external_successor_verified") is True
        and type(handoff_execution.get("verified_count")) is int
        and handoff_execution.get("verified_count") == handoff_execution.get("expected_component_count")
        and handoff_execution.get("verified_count", 0) > 0
    )
    stages = (
        ("Release review", review_current,
         "Previous review expired; run a new authoritative provider review."
         if review_expired else "Current provider inventory and dependency evidence must be reviewed."),
        ("Independent approval", same_plan,
         "Independent review is recorded but the plan/approval expired; only the original requester may restart after fresh provider checks."
         if approval_expired else "A different authorized KAORI operator acknowledges this exact plan."),
        ("Verified successor acceptance", verified_acceptance,
         "Authenticated Kubernetes principal explicitly accepted this exact plan and passed scoped access review."
         if verified_acceptance else "Kubernetes TokenReview, scoped SubjectAccessReview and explicit successor consent are required."),
        ("KAORI provider handoff", provider_transfer_verified,
         "Exact Native provider handoff was committed with post-write read-back."
         if provider_transfer_verified else "Execute accepted Native handoff and verify all provider objects; partial transfer requires recovery."),
        ("Released and Re-adopt", False,
         "Canonical Released commit and new-generation Re-adopt require verified handoff."),
    )
    return {
        "stages": [
            {
                "label": label, "complete": complete, "detail": detail,
                "display_status": (
                    "Expired" if label == "Release review" and review_expired
                    else "Recorded · Expired" if label == "Independent approval" and approval_expired
                    else "Evidence available" if complete else "Pending"
                ),
            }
            for label, complete, detail in stages
        ],
        "review_complete": review_current,
        "approval_complete": same_plan,
        "verified_successor_acceptance": verified_acceptance,
        "provider_transfer_verified": provider_transfer_verified,
        "approval_recorded": approval_recorded,
        "approval_expired": approval_expired,
        "review_expired": review_expired,
        "restart_required": restart_required,
        "restart_blocked_by_readback": bool(approval_expired and readback_for_plan),
        "dry_run_passed": preview_passed,
        "reference_recorded": reference_recorded,
        "readback_observed_unverified": readback_observed,
        "completed_count": sum(int(complete) for _, complete, _ in stages),
        "total_count": len(stages),
        "execute_admitted": False,
        "release_admitted": False,
    }

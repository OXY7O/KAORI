"""Committed-evidence Native Release readiness, never a mutation authority.

This deliberately does not infer trusted successor acceptance from a local
KAORI approval, a text reference, a provider label, or dry-run/read-back.
#1047 must admit an identity-backed acceptance contract before execution.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

from app.kubernetes.tenant.native_handoff_recovery import readback_proves_handoff_not_started
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
    readback_history: list[Mapping[str, Any]] | None = None,
    execution_history: list[Mapping[str, Any]] | None = None,
    no_transfer_assessment: Mapping[str, Any] | None = None,
    no_transfer_decision: Mapping[str, Any] | None = None,
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
    # The restart service evaluates the complete committed audit history and
    # fresh provider preflight. This is only a display hint; unknown and
    # incomplete receipts remain fail-closed.
    readbacks = (
        readback_history if readback_history is not None
        else ([readback] if readback else [])
    )
    executions = (
        execution_history if execution_history is not None
        else ([handoff_execution] if handoff_execution else [])
    )
    same_plan_readbacks = [
        item for item in readbacks
        if isinstance(item, dict) and item.get("plan_sha256") == plan_sha
    ]
    any_execution = any(
        not isinstance(item, dict)
        or not isinstance(item.get("plan_sha256"), str)
        or len(item["plan_sha256"]) != 64
        or item["plan_sha256"] == plan_sha
        for item in executions
    )
    history_incomplete = any(
        not isinstance(item, dict)
        or not isinstance(item.get("plan_sha256"), str)
        or len(item["plan_sha256"]) != 64
        for item in readbacks
    )
    zero_transfer_observed = bool(
        plan and same_plan_readbacks and not history_incomplete
        and all(
            readback_proves_handoff_not_started(item, plan=plan)
            for item in same_plan_readbacks
        )
    )
    restart_blocked = bool(
        history_incomplete or any_execution
        or (same_plan_readbacks and not zero_transfer_observed)
    )
    # Advisory only. Registry execution_history is newest-first: the terminal
    # failed receipt precedes the initial in_progress receipt. The initial
    # receipt is written before any provider PATCH and intentionally does not
    # contain terminal mutation/verified counters. Never invent those fields.
    # This is a screening hint, not the event-ID/actor/chronology admission
    # performed by _source_history and fresh authoritative provider inspection.
    same_plan_executions = [
        item for item in executions
        if isinstance(item, dict) and item.get("plan_sha256") == plan_sha
    ]
    invalid_execution_history = any(
        not isinstance(item, dict)
        or not isinstance(item.get("plan_sha256"), str)
        or re.fullmatch(r"[0-9a-f]{64}", item["plan_sha256"]) is None
        for item in executions
    )
    no_transfer_assessment_candidate = bool(
        plan
        and not invalid_execution_history
        and not history_incomplete
        and (not same_plan_readbacks or zero_transfer_observed)
        and len(same_plan_executions) == 2
        and same_plan_executions[0].get("status") == "partial_handoff_recovery_required"
        and same_plan_executions[1].get("status") == "in_progress"
        and all(
            item.get("handoff_fingerprint") == plan.get("handoff_fingerprint")
            for item in same_plan_executions
        )
        and same_plan_executions[0].get("provider_mutation_performed") is False
        and same_plan_executions[0].get("provider_handoff_verified") is False
        and same_plan_executions[0].get("release_authorized") is False
        and type(same_plan_executions[0].get("verified_count")) is int
        and same_plan_executions[0]["verified_count"] == 0
        and type(same_plan_executions[0].get("expected_component_count")) is int
        and same_plan_executions[0]["expected_component_count"] > 0
        and same_plan_executions[0].get("verified_components") == []
        and isinstance(same_plan_executions[0].get("errors"), list)
        and bool(same_plan_executions[0]["errors"])
        and same_plan_executions[1].get("release_authorized") is False
        and "provider_mutation_performed" not in same_plan_executions[1]
        and "provider_handoff_verified" not in same_plan_executions[1]
        and "verified_count" not in same_plan_executions[1]
        and "verified_components" not in same_plan_executions[1]
        and isinstance(same_plan_executions[1].get("started_at"), str)
        and isinstance(same_plan_executions[0].get("checked_at"), str)
    )
    restart_required = bool(approval_expired and not restart_blocked)
    # Committed UI hints for the independent recovery workflow. Backend must
    # still verify ALL historical events and fresh live Kubernetes state.
    no_transfer_assessment_current = bool(
        approval_expired and plan and no_transfer_assessment
        and no_transfer_assessment.get('status') == 'verified_no_transfer_pending_independent_review'
        and no_transfer_assessment.get('plan_sha256') == plan_sha
        and no_transfer_assessment.get('handoff_fingerprint') == plan.get('handoff_fingerprint')
        and no_transfer_assessment.get('assessed_by') == plan.get('requested_by')
        and _checked_recently(no_transfer_assessment.get('assessed_at'))
    )
    no_transfer_authorized_current = bool(
        no_transfer_assessment_current and no_transfer_decision
        and no_transfer_decision.get('status') == 'authorized_for_requester_restart'
        and no_transfer_decision.get('plan_sha256') == plan_sha
        and no_transfer_decision.get('handoff_fingerprint') == plan.get('handoff_fingerprint')
        and no_transfer_decision.get('assessment_sha256') == no_transfer_assessment.get('assessment_sha256')
        and no_transfer_decision.get('history_digest') == no_transfer_assessment.get('history_digest')
        and no_transfer_decision.get('provider_proof_sha256') == no_transfer_assessment.get('provider_proof_sha256')
        and no_transfer_decision.get('authorized_by') not in {
            plan.get('requested_by'), no_transfer_assessment.get('executor_actor_id'),
        }
        and _checked_recently(no_transfer_decision.get('authorized_at'))
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
    # Advisory UI precondition only: mirror the *current*, SHA/fingerprint
    # scoped evidence guards of the external observer. The service rechecks
    # those guards before any provider read and remains authoritative.
    external_reference_current = bool(
        reference_recorded
        and _checked_recently((successor_claim or {}).get("recorded_at"))
        and (successor_claim or {}).get("successor_owner") == (plan or {}).get("successor_owner")
    )
    external_readback_prerequisites_current = bool(
        same_plan and approval_recorded
        and (approval or {}).get("handoff_fingerprint") == (plan or {}).get("handoff_fingerprint")
        and external_reference_current and preview_passed
        and (dry_run or {}).get("handoff_fingerprint") == (plan or {}).get("handoff_fingerprint")
        and (dry_run or {}).get("release_authorized") is False
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
        and successor_acceptance.get("status") == "platform_admin_handoff_accepted"
        and successor_acceptance.get("authority_mode") == "platform_admin_governed"
        and successor_acceptance.get("verified_provider_identity") is True
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
        and handoff_execution.get("authority_mode") == "platform_admin_governed"
        and handoff_execution.get("provider_authority_verified") is True
        and type(handoff_execution.get("verified_count")) is int
        and handoff_execution.get("verified_count") == handoff_execution.get("expected_component_count")
        and handoff_execution.get("verified_count", 0) > 0
    )
    # Explicitly distinguish a recorded, incomplete executor attempt from
    # ordinary pending provider handoff. This is display evidence only:
    # 0 verified resources does not prove that 0 resources were mutated.
    provider_handoff_recovery_required = bool(
        plan and handoff_execution
        and handoff_execution.get("plan_sha256") == plan_sha
        and handoff_execution.get("handoff_fingerprint") == plan.get("handoff_fingerprint")
        and handoff_execution.get("status") == "partial_handoff_recovery_required"
        and handoff_execution.get("provider_handoff_verified") is False
    )
    stages = (
        ("Release review", review_current,
         "Previous review expired; run a new authoritative provider review."
         if review_expired else "Current provider inventory and dependency evidence must be reviewed."),
        ("Independent approval", same_plan,
         "Independent review is recorded but the plan/approval expired; only the original requester may restart after fresh provider checks."
         if approval_expired else "A different authorized KAORI operator acknowledges this exact plan."),
        ("Platform Admin governance acceptance", verified_acceptance,
         "Authorized Platform Admin accepted this exact plan; kubeconfig identity and scoped permissions were verified."
         if verified_acceptance else "Requires independent Platform Admin confirmation, Kubernetes SelfSubjectReview and scoped SelfSubjectAccessReview."),
        ("KAORI provider handoff", provider_transfer_verified,
         "Platform Admin Native provider handoff was committed with post-write read-back."
         if provider_transfer_verified else (
             "An incomplete provider handoff attempt requires recovery review. Inspect the committed error and provider mutation evidence before any retry."
             if provider_handoff_recovery_required
             else "Execute accepted Native handoff and verify all provider objects; partial transfer requires recovery."
         )),
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
                    else "Recovery Required" if label == "KAORI provider handoff" and provider_handoff_recovery_required
                    else "Evidence available" if complete else "Pending"
                ),
            }
            for label, complete, detail in stages
        ],
        "review_complete": review_current,
        "approval_complete": same_plan,
        "verified_successor_acceptance": verified_acceptance,
        "provider_transfer_verified": provider_transfer_verified,
        "provider_handoff_recovery_required": provider_handoff_recovery_required,
        "approval_recorded": approval_recorded,
        "approval_expired": approval_expired,
        "review_expired": review_expired,
        "restart_required": restart_required,
        "no_transfer_assessment_candidate": no_transfer_assessment_candidate,
        "no_transfer_assessment_current": no_transfer_assessment_current,
        "no_transfer_authorized_current": no_transfer_authorized_current,
        "restart_blocked_by_readback": bool(approval_expired and restart_blocked),
        "restart_zero_transfer_recheck_required": bool(approval_expired and zero_transfer_observed and not restart_blocked),
        "dry_run_passed": preview_passed,
        "reference_recorded": reference_recorded,
        "external_reference_current": external_reference_current,
        "external_readback_prerequisites_current": external_readback_prerequisites_current,
        "readback_observed_unverified": readback_observed,
        "completed_count": sum(int(complete) for _, complete, _ in stages),
        "total_count": len(stages),
        "execute_admitted": False,
        "release_admitted": False,
    }

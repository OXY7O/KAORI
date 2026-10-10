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
        "requested_at": now,
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



def test_external_readback_ui_requires_fresh_same_plan_evidence_without_authorizing_release():
    snapshot = evidence()
    now = datetime.now(UTC).isoformat()
    snapshot['plan'].update({
        'handoff_fingerprint': 'scope-fp', 'successor_owner': 'platform-team',
    })
    snapshot['approval']['handoff_fingerprint'] = 'scope-fp'
    snapshot['successor_claim'] = {
        'plan_sha256': 'a' * 64, 'status': 'external_reference_unverified',
        'recorded_at': now, 'successor_owner': 'platform-team',
    }
    snapshot['dry_run'].update({
        'handoff_fingerprint': 'scope-fp', 'release_authorized': False,
    })

    result = project_native_release_readiness(**snapshot)
    assert result['external_reference_current'] is True
    assert result['external_readback_prerequisites_current'] is True
    assert result['verified_successor_acceptance'] is False
    assert result['execute_admitted'] is False
    assert result['release_admitted'] is False

    # Historical "Approved" and "Dry-Run Passed" do not authorize a read
    # after independent evidence expires (the DevContainer failure).
    snapshot['approval']['approved_at'] = '2020-01-01T00:00:00+00:00'
    expired = project_native_release_readiness(**snapshot)
    assert expired['approval_expired'] is True
    assert expired['external_readback_prerequisites_current'] is False
    snapshot['approval']['approved_at'] = now

    snapshot['successor_claim']['recorded_at'] = '2020-01-01T00:00:00+00:00'
    assert not project_native_release_readiness(**snapshot)['external_readback_prerequisites_current']
    snapshot['successor_claim']['recorded_at'] = now
    snapshot['successor_claim']['successor_owner'] = 'untrusted-claim'
    assert not project_native_release_readiness(**snapshot)['external_readback_prerequisites_current']
    snapshot['successor_claim']['successor_owner'] = 'platform-team'

    snapshot['dry_run']['checked_at'] = '2020-01-01T00:00:00+00:00'
    assert not project_native_release_readiness(**snapshot)['external_readback_prerequisites_current']
    snapshot['dry_run']['checked_at'] = now
    snapshot['dry_run']['handoff_fingerprint'] = 'different-scope'
    assert not project_native_release_readiness(**snapshot)['external_readback_prerequisites_current']



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


def test_stale_handoff_plan_cannot_appear_as_completed_approval():
    snapshot = evidence()
    snapshot["plan"]["requested_at"] = "2020-01-01T00:00:00+00:00"
    status = project_native_release_readiness(**snapshot)
    assert not status["approval_complete"]
    assert not status["dry_run_passed"]
    assert status["completed_count"] == 1


def test_expired_review_and_approved_plan_report_recorded_but_inactive():
    snapshot = evidence()
    snapshot["preflight"]["checked_at"] = "2020-01-01T00:00:00+00:00"
    snapshot["plan"]["requested_at"] = "2020-01-01T00:00:00+00:00"
    snapshot["approval"]["approved_at"] = "2020-01-01T00:00:00+00:00"
    output = project_native_release_readiness(**snapshot)
    assert output["completed_count"] == 0
    assert output["approval_recorded"] is True
    assert output["approval_complete"] is False
    assert output["review_expired"] is True
    assert output["restart_required"] is True
    assert output["stages"][0]["display_status"] == "Expired"
    assert output["stages"][1]["display_status"] == "Recorded · Expired"
    assert output["execute_admitted"] is False
    assert output["release_admitted"] is False


def test_prior_handoff_readback_blocks_expired_plan_restart():
    snapshot = evidence()
    snapshot["plan"]["requested_at"] = "2020-01-01T00:00:00+00:00"
    snapshot["approval"]["approved_at"] = "2020-01-01T00:00:00+00:00"
    snapshot["readback"] = {
        "plan_sha256": "a" * 64,
        "status": "partial_handoff_recovery_required",
        "external_successor_verified": False,
    }
    projection = project_native_release_readiness(**snapshot)
    assert projection["approval_expired"] is True
    assert projection["restart_blocked_by_readback"] is True
    assert projection["restart_required"] is False
    assert projection["release_admitted"] is False



def test_canonical_zero_transfer_receipt_allows_advisory_restart_with_live_recheck():
    snapshot = evidence()
    snapshot['plan'].update({
        'tenant_id': 'tenant-a', 'cluster_id': 'cluster-a',
        'generation': 3, 'handoff_fingerprint': 'fp',
        'handoff_components': [{
            'kind': 'Namespace', 'namespace': None, 'name': 'sandbox',
            'uid': 'uid-1', 'resource_version': '21',
            'handoff': 'external_acceptance_required',
        }],
    })
    component = {
        'kind': 'Namespace', 'namespace': None, 'name': 'sandbox',
        'uid': 'uid-1', 'resource_version': '21',
        'state': 'pending_provider_transfer',
        'spec_preserved': True, 'foreign_metadata_preserved': True,
    }
    recovery = {
        'status': 'provider_handoff_not_started',
        'components': [component], 'transferred_count': 0,
        'pending_count': 1, 'provider_spec_preserved': True,
        'provider_resource_deleted': False, 'successor_consent_verified': False,
        'resume_authorized': False, 'release_authorized': False,
    }
    receipt = {
        'tenant_id': 'tenant-a', 'cluster_id': 'cluster-a',
        'generation': 3, 'plan_sha256': 'a' * 64,
        'handoff_fingerprint': 'fp', 'status': 'provider_handoff_not_started',
        'observed_components': [component], 'observed_count': 0,
        'recovery': recovery, 'provider_handoff_observed': False,
        'provider_mutation_performed': False, 'provider_handoff_verified': False,
        'release_authorized': False, 'external_successor_verified': False,
    }
    snapshot['plan']['requested_at'] = '2020-01-01T00:00:00+00:00'
    snapshot['approval']['approved_at'] = '2020-01-01T00:00:00+00:00'
    snapshot['readback'] = receipt
    snapshot['readback_history'] = [receipt]
    snapshot['execution_history'] = []

    ready = project_native_release_readiness(**snapshot)
    assert ready['restart_required'] is True
    assert ready['restart_zero_transfer_recheck_required'] is True
    assert ready['restart_blocked_by_readback'] is False
    assert ready['release_admitted'] is False

    snapshot['readback_history'] = [
        receipt, {**receipt, 'status': 'partial_handoff_recovery_required'},
    ]
    blocked = project_native_release_readiness(**snapshot)
    assert blocked['restart_required'] is False
    assert blocked['restart_blocked_by_readback'] is True

    snapshot['readback_history'] = [receipt]
    snapshot['execution_history'] = [{
        'plan_sha256': 'a' * 64, 'status': 'partial_handoff_recovery_required',
    }]
    blocked_execution = project_native_release_readiness(**snapshot)
    assert blocked_execution['restart_required'] is False
    assert blocked_execution['restart_blocked_by_readback'] is True



def test_current_independent_review_never_offers_restart():
    projection = project_native_release_readiness(**evidence())
    assert projection["approval_recorded"] is True
    assert projection["approval_expired"] is False
    assert projection["restart_required"] is False


def test_existing_ui_restart_is_explicit_and_scoped_by_original_requester():
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    source = (root / "app/templates/kubernetes/tenant/partials/_tenant_management_detail.html").read_text()
    route = (root / "app/kubernetes/tenant/routes.py").read_text()
    assert "native_cycle.approval_expired" in source
    assert "native_cycle.restart_blocked_by_readback" in source
    assert "row.release_handoff_plan.requested_by == current_user.id" in source
    assert "name=\"confirm_handoff_restart\"" in source
    assert "Restart Expired Handoff Plan" in source
    assert "restart_expired_tenant_release_handoff_route" in source
    assert "@permission_required('tenant.manage')" in route
    assert "@permission_required('integrations.manage')" in route
    assert "restart_expired_native_release_handoff_plan_committed(" in route


def test_platform_admin_handoff_counts_only_current_provider_evidence():
    snapshot = evidence()
    snapshot['plan'].update({
        'handoff_fingerprint': 'scope-hash', 'provider_identity': ['immutable-uid'],
        'successor_owner': 'platform-team',
    })
    snapshot['approval']['status'] = 'acknowledged_pending_provider_handoff'
    snapshot['successor_acceptance'] = {
        'status': 'platform_admin_handoff_accepted',
        'authority_mode': 'platform_admin_governed',
        'plan_sha256': 'a' * 64, 'handoff_fingerprint': 'scope-hash',
        'provider_identity': ['immutable-uid'], 'successor_owner': 'platform-team',
        'reviewed_by': 12, 'verified_provider_identity': True,
        'consent_verified': True, 'resource_authority_verified': True,
        'accepted_at': datetime.now(UTC).isoformat(),
    }
    snapshot['handoff_execution'] = {
        'status': 'provider_handoff_verified', 'authority_mode': 'platform_admin_governed',
        'plan_sha256': 'a' * 64, 'handoff_fingerprint': 'scope-hash',
        'provider_authority_verified': True, 'external_successor_verified': False,
        'provider_handoff_verified': True,
        'verified_count': 2, 'expected_component_count': 2,
    }
    result = project_native_release_readiness(**snapshot)
    assert result['verified_successor_acceptance'] is True
    assert result['provider_transfer_verified'] is True
    assert result['completed_count'] == 4
    snapshot['successor_acceptance']['authority_mode'] = 'external_bearer_successor'
    changed = project_native_release_readiness(**snapshot)
    assert changed['verified_successor_acceptance'] is False


def test_legacy_bearer_acceptance_not_used_by_new_platform_admin_readiness():
    snapshot = evidence()
    snapshot['successor_acceptance'] = {
        'plan_sha256': 'a' * 64,
        'status': 'verified_explicit_successor_acceptance',
        'consent_verified': True, 'resource_authority_verified': True,
        'accepted_at': datetime.now(UTC).isoformat(),
    }
    result = project_native_release_readiness(**snapshot)
    assert result['verified_successor_acceptance'] is False
    assert result['stages'][2]['complete'] is False

"""Issue #4800: completed review Plan ≠ approved/usable Kubespray operation."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.infrastructure_automation.kubernetes import plan_currentness as subject
from app.infrastructure_automation.kubernetes.plan_review import (
    PLAN_OPERATION,
    PLAN_RESULT_TYPE,
    KubesprayPlanReview,
)

_NOW = datetime(2026, 11, 16, 10, 0, tzinfo=UTC)


def _fixture():
    connection = SimpleNamespace(id=7)
    host = SimpleNamespace(id=9, public_id='host-preflight-9', integration_instance_id=7)
    preflight = SimpleNamespace(state='ready_for_review', facts_job_public_id=host.public_id)
    approved_for_review_only = KubesprayPlanReview(
        status='requires_independent_approval',
        reason_code='REVIEW_ONLY',
        plan_fingerprint='a' * 64,
        inventory_fingerprint='b' * 64,
        host_preflight_job_public_id=host.public_id,
        expires_at=(_NOW + timedelta(minutes=2)).isoformat(),
        source_sha='c' * 40,
        execution_environment_digest='sha256:' + 'd' * 64,
    )
    plan_job = SimpleNamespace(
        public_id='plan-job-11',
        integration_instance_id=7,
        integration_type='configuration_automation',
        job_type='infrastructure_automation',
        operation=PLAN_OPERATION,
        queue_name='automation',
        result_type=PLAN_RESULT_TYPE,
        status='succeeded',
        completed_at=_NOW - timedelta(seconds=3),
        result_summary_json=approved_for_review_only.committed_summary(),
    )
    return connection, host, preflight, approved_for_review_only, plan_job


def _check(monkeypatch: pytest.MonkeyPatch, *, plan_job=None, host=None, preflight=None, rebuilt=None, now=_NOW):
    connection, original_host, original_preflight, candidate, original_plan = _fixture()
    monkeypatch.setattr(
        subject,
        'build_kubespray_plan_review',
        lambda connection, host_preflight_job, *, now: rebuilt or candidate,
    )
    return subject.evaluate_kubespray_plan_currentness(
        connection,
        latest_plan_job=original_plan if plan_job is None else plan_job,
        latest_host_preflight=original_preflight if preflight is None else preflight,
        host_preflight_job=original_host if host is None else host,
        now=now,
    )


def test_exact_committed_current_plan_remains_only_reviewable(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _check(monkeypatch)
    assert result.state == 'current_for_review'
    assert result.job_public_id == 'plan-job-11'
    assert result.plan_fingerprint == 'a' * 64
    assert result.expires_at == (_NOW + timedelta(minutes=2)).isoformat()
    assert result.execution_authorized is False
    assert result.presentation()['execution_authorized'] is False
    assert 'approval' not in result.presentation()


def test_no_job_is_not_generated_not_successful(monkeypatch: pytest.MonkeyPatch) -> None:
    connection, host, preflight, candidate, _ = _fixture()
    result = subject.evaluate_kubespray_plan_currentness(
        connection, latest_plan_job=None, latest_host_preflight=preflight, host_preflight_job=host, now=_NOW
    )
    assert result.state == 'not_generated'
    assert result.execution_authorized is False


@pytest.mark.parametrize(
    ('field', 'value'),
    [
        ('integration_instance_id', 8),
        ('integration_type', 'artifact_registry'),
        ('job_type', 'inventory'),
        ('queue_name', 'default'),
        ('operation', 'automation_localhost_host_facts'),
        ('result_type', 'automation_host_facts'),
        ('status', 'failed'),
        ('status', 'queued'),
        ('status', 'cancel_requested'),
        ('completed_at', None),
        ('completed_at', datetime(2026, 11, 16, 10, 0)),
        ('completed_at', _NOW + timedelta(seconds=10)),
    ],
)
def test_wrong_source_or_later_failed_inflight_plan_never_resurrects_old_success(
    monkeypatch: pytest.MonkeyPatch, field: str, value: object
) -> None:
    *_, latest = _fixture()
    setattr(latest, field, value)
    result = _check(monkeypatch, plan_job=latest)
    assert result.state == 'blocked'
    assert result.job_public_id is None
    assert result.execution_authorized is False


@pytest.mark.parametrize(
    ('field', 'value'),
    [
        ('mutation_authorized', True),
        ('approval_status', 'approved'),
        ('execution_status', 'ready'),
        ('source_sha', 'e' * 40),
        ('execution_environment_digest', 'sha256:' + 'f' * 64),
        ('plan_fingerprint', '0' * 64),
        ('host_preflight_job_public_id', 'old-observation'),
        ('upstream_kubespray_commit', '0' * 40),
    ],
)
def test_tampered_or_self_approved_plan_is_never_current(
    monkeypatch: pytest.MonkeyPatch, field: str, value: object
) -> None:
    *_, latest = _fixture()
    latest.result_summary_json[field] = value
    assert _check(monkeypatch, plan_job=latest).state == 'blocked'


def test_unknown_extra_field_cannot_inject_approval(monkeypatch: pytest.MonkeyPatch) -> None:
    *_, latest = _fixture()
    latest.result_summary_json['trusted_approval_token'] = 'fabricated'
    assert _check(monkeypatch, plan_job=latest).state == 'blocked'


def test_plan_expiry_is_strict_and_never_usable_after_deadline(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _check(monkeypatch, now=_NOW + timedelta(minutes=2))
    assert result.state == 'expired'
    assert result.plan_fingerprint is None
    assert result.execution_authorized is False


def test_invalid_expiry_and_expiry_before_job_completion_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    for expiry in ('not-a-timestamp', '', '2026-11-16T10:02:00', (_NOW - timedelta(minutes=1)).isoformat()):
        *_, latest = _fixture()
        latest.result_summary_json['expires_at'] = expiry
        assert _check(monkeypatch, plan_job=latest).state == 'blocked'


def test_current_preflight_and_source_fingerprint_must_match(monkeypatch: pytest.MonkeyPatch) -> None:
    *_, latest = _fixture()
    different = KubesprayPlanReview(
        status='requires_independent_approval',
        reason_code='REVIEW_ONLY',
        plan_fingerprint='e' * 64,
        inventory_fingerprint='b' * 64,
        host_preflight_job_public_id='host-preflight-9',
        expires_at=(_NOW + timedelta(minutes=2)).isoformat(),
        source_sha='c' * 40,
        execution_environment_digest='sha256:' + 'd' * 64,
    )
    assert _check(monkeypatch, plan_job=latest, rebuilt=different).state == 'blocked'
    changed_preflight = SimpleNamespace(state='blocked', facts_job_public_id='host-preflight-9')
    assert _check(monkeypatch, plan_job=latest, preflight=changed_preflight).state == 'blocked'
    replaced = SimpleNamespace(public_id='new-host-10', integration_instance_id=7)
    assert _check(monkeypatch, plan_job=latest, host=replaced).state == 'blocked'

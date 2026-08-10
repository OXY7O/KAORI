from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.governance.tls_certificates.certificate import (
    TLSValidityPolicy,
    classify_certificate_validity,
    hostname_matches_pattern,
)
from app.governance.tls_certificates.results import classify_tls_sync_outcome


def test_validity_policy_preserves_expired_critical_warning_and_healthy_boundaries() -> None:
    now = datetime(2026, 8, 10, 10, 0, tzinfo=UTC)
    policy = TLSValidityPolicy(renewal_window_days=30, critical_window_days=7)

    assert classify_certificate_validity(now - timedelta(seconds=1), now=now, policy=policy)[1] == 'expired'
    assert classify_certificate_validity(now + timedelta(days=7), now=now, policy=policy)[1] == 'critical'
    assert classify_certificate_validity(now + timedelta(days=30), now=now, policy=policy)[1] == 'warning'
    assert classify_certificate_validity(now + timedelta(days=31), now=now, policy=policy)[1] == 'healthy'


def test_hostname_matching_keeps_single_label_wildcard_semantics() -> None:
    assert hostname_matches_pattern('api.example.com', '*.example.com') is True
    assert hostname_matches_pattern('deep.api.example.com', '*.example.com') is False
    assert hostname_matches_pattern('example.com', '*.example.com') is False


def test_tls_sync_outcome_distinguishes_full_partial_and_failed_runs() -> None:
    assert classify_tls_sync_outcome(target_count=2, failed_count=0, warning_count=0) == 'succeeded'
    assert classify_tls_sync_outcome(target_count=2, failed_count=0, warning_count=1) == 'partially_succeeded'
    assert classify_tls_sync_outcome(target_count=2, failed_count=2, warning_count=0) == 'failed'

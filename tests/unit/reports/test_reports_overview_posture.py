from app.reports.overview.service import get_reporting_posture


def test_worker_outage_overrides_clean_history() -> None:
    assert get_reporting_posture({'failed': 0}, {'ready': True}, {'ready': False, 'status': 'offline'}) == {
        'label': 'Degraded',
        'tone': 'warning',
        'reason': 'queue',
    }


def test_unknown_worker_evidence_is_not_ready() -> None:
    assert (
        get_reporting_posture({'failed': 0}, {'ready': True}, {'ready': False, 'status': 'unknown'})['label']
        == 'Needs Review'
    )


def test_storage_unavailable_precedes_worker_and_failed_request_history() -> None:
    assert (
        get_reporting_posture({'failed': 7}, {'ready': False}, {'ready': False, 'status': 'offline'})['reason']
        == 'storage'
    )


def test_healthy_runtime_with_failed_history_still_needs_review() -> None:
    assert (
        get_reporting_posture({'failed': 2}, {'ready': True}, {'ready': True, 'status': 'online'})['reason']
        == 'failed_requests'
    )


def test_healthy_runtime_and_clean_history_is_ready() -> None:
    assert get_reporting_posture({'failed': 0}, {'ready': True}, {'ready': True, 'status': 'online'}) == {
        'label': 'Ready',
        'tone': 'normal',
        'reason': 'ready',
    }

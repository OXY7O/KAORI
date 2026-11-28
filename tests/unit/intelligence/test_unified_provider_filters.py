"""Provider filters remain tab-local and never inherit recommendation origin (#5229)."""

from werkzeug.datastructures import MultiDict

from app.intelligence.alert_intelligence.provider_case_scope import _read_filters


def test_resolved_does_not_inherit_active_workflow():
    args = MultiDict(
        {'source': 'recommendation', 'workflow': 'acknowledged', 'source_state': 'firing', 'q': ' case '}
    )
    assert _read_filters(args, tab='resolved') == {
        'severity': 'all',
        'workflow': 'all',
        'source': 'provider_alert',
        'source_state': 'all',
        'q': 'case',
    }


def test_active_does_not_inherit_recovery_workflow():
    active = _read_filters(MultiDict({'workflow': 'closed', 'source_state': 'conflict'}), tab='active')
    assert active['workflow'] == 'all'
    assert active['source_state'] == 'all'


def test_resolved_filters_preserve_verification_and_conflict():
    filters = _read_filters(
        MultiDict({'workflow': 'verification_pending', 'source_state': 'conflict'}), tab='resolved'
    )
    assert filters['workflow'] == 'verification_pending'
    assert filters['source_state'] == 'conflict'

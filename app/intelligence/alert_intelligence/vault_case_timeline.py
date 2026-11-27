"""Bounded, redacted provider case event projection for the existing incident timeline."""

from __future__ import annotations

from typing import Any

from app.intelligence.alert_intelligence.vault_recovery_state import CLOSURE_EVENT, RECOVERY_EVENT, qualified_recovery_event
from app.intelligence.alert_signals.vault_source import _persisted_utc
from app.models.alert_ops import AlertCase, AlertCaseEvent

_MAX_TIMELINE = 25
_RECENT_TIMELINE = 5
_SOURCE_METADATA = {'source_type': 'provider_alert', 'domain': 'secrets_pki'}
_OPERATOR_METADATA_KEYS = {'source_type', 'domain', 'previous_event_id', 'workflow_state', 'owner_user_id'}
_EVENT_PRESENTATION = {
    RECOVERY_EVENT: ('Provider recovered', 'Explicit provider resolution was admitted.', 'shield-check', 'info'),
    CLOSURE_EVENT: ('Verified and closed', 'Independent operator verified and closed the case.', 'badge-check', 'normal'),
    'provider_alert_admitted': ('Case admitted', 'Qualified source firing was recorded.', 'siren', 'warning'),
    'provider_alert_observed': ('Source observed', 'Fresh firing evidence was admitted.', 'activity', 'info'),
    'provider_alert_source_unknown': ('Source unverified', 'Current firing is unverified; recovery is not proven.', 'circle-help', 'warning'),
    'acknowledged': ('Acknowledged', 'An operator acknowledged the case.', 'user-check', 'info'),
    'assigned': ('Ownership updated', 'An operator updated case ownership.', 'users', 'info'),
    'mitigating': ('Mitigation started', 'The assigned operator began mitigation.', 'activity', 'warning'),
}


def _qualified_event(event: AlertCaseEvent) -> bool:
    metadata = event.metadata_json
    if event.event_type not in _EVENT_PRESENTATION or not isinstance(metadata, dict):
        return False
    if event.event_type in (RECOVERY_EVENT, CLOSURE_EVENT):
        return qualified_recovery_event(event)
    if event.event_type.startswith('provider_alert_'):
        return metadata == _SOURCE_METADATA
    return (
        set(metadata) == _OPERATOR_METADATA_KEYS
        and metadata.get('source_type') == 'provider_alert'
        and metadata.get('domain') == 'secrets_pki'
        and type(metadata.get('previous_event_id')) is int
        and 0 < metadata['previous_event_id'] < event.id
        and metadata.get('workflow_state') in ('open', 'acknowledged', 'mitigating')
        and (metadata.get('owner_user_id') is None or type(metadata['owner_user_id']) is int)
    )


def read_case_timeline(case: AlertCase) -> dict[str, Any]:
    """Called only within the audited exact-instance detail transaction.

    This is a view of recorded events, not independent proof of recovery or
    of every historical audit. Never expose persisted summaries, metadata,
    actor identities, correlation handles or provider data.
    """
    rows = (
        AlertCaseEvent.query.filter_by(case_id=case.id)
        .order_by(AlertCaseEvent.id.desc())
        .limit(_MAX_TIMELINE + 1)
        .all()
    )
    events = []
    for event in rows[:_MAX_TIMELINE]:
        if not _qualified_event(event) or _persisted_utc(event.created_at) is None:
            return {
                'timeline': [],
                'timeline_recent': [],
                'timeline_older': [],
                'timeline_unavailable': True,
                'timeline_truncated': False,
            }
        label, summary, icon, tone = _EVENT_PRESENTATION[event.event_type]
        events.append(
            {
                'label': label,
                'summary': summary,
                'icon': icon,
                'tone': tone,
                'actor': 'Recorded activity',
                'created_at': event.created_at,
            }
        )
    return {
        'timeline': events,
        'timeline_recent': events[:_RECENT_TIMELINE],
        'timeline_older': events[_RECENT_TIMELINE:],
        'timeline_unavailable': False,
        'timeline_truncated': len(rows) > _MAX_TIMELINE,
    }

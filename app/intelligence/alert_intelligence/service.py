from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from werkzeug.datastructures import MultiDict

from app.common.pagination import paginate_sequence
from app.integrations.delivery.notification_channels.service import notification_channel_summary
from app.intelligence.alert_intelligence.lifecycle import active_delivery_silence, get_case
from app.intelligence.alert_intelligence.notifications import case_delivery_rows
from app.intelligence.alert_intelligence.routing import notification_channel_options, routing_policy_rows
from app.intelligence.alert_intelligence.snapshots import load_snapshot_rows
from app.intelligence.alert_intelligence.templates import built_in_templates
from app.models.alert_ops import AlertCase, AlertCaseEvent, AlertSilence
from app.models.cluster import Cluster
from app.models.notification_channel import NotificationDelivery
from app.models.object_storage import ObjectStorageSystem
from app.models.user import User

_VALID_DOMAINS = {'kubernetes', 'object_storage'}
_VALID_TABS = {'overview', 'active', 'routing', 'templates', 'silences', 'history'}
_VALID_SEVERITIES = {'all', 'critical', 'warning', 'info', 'unknown'}
_VALID_WORKFLOW_STATES = {'all', 'open', 'acknowledged', 'mitigating', 'verification_pending'}
_DOMAIN_LABELS = {'kubernetes': 'Kubernetes', 'object_storage': 'Object Storage'}


def get_alert_intelligence_payload(args: MultiDict[str, str]) -> dict[str, Any]:
    clusters = Cluster.query.order_by(Cluster.name.asc()).all()
    systems = ObjectStorageSystem.query.order_by(ObjectStorageSystem.name.asc()).all()
    domain = _selected_domain(args, clusters=clusters, systems=systems)
    assets = _asset_options(domain, clusters=clusters, systems=systems)
    selected_asset_key = _selected_asset_key(args, assets)
    selected_asset_name = next(
        (row['label'] for row in assets if row['value'] == selected_asset_key),
        'All Managed Assets',
    )
    tab = _choice(args.get('tab'), _VALID_TABS, 'overview')
    severity = _choice(args.get('severity'), _VALID_SEVERITIES, 'all')
    workflow = _choice(args.get('workflow'), _VALID_WORKFLOW_STATES, 'all')
    search = str(args.get('q') or '').strip()

    scoped_cases = _case_rows(domain=domain, asset_key=selected_asset_key)
    active_cases = [row for row in scoped_cases if row.workflow_state != 'closed']
    history_cases = [row for row in scoped_cases if row.workflow_state == 'closed']
    filtered_active = _filter_cases(active_cases, severity=severity, workflow=workflow, search=search)
    filtered_history = _filter_cases(history_cases, severity=severity, workflow='all', search=search)
    active_page, active_pagination = paginate_sequence(
        [_serialize_case(row) for row in filtered_active],
        page=args.get('page', 1),
        per_page=args.get('per_page', 5),
    )
    history_page, history_pagination = paginate_sequence(
        [_serialize_case(row) for row in filtered_history],
        page=args.get('history_page', 1),
        per_page=args.get('history_per_page', 5),
    )
    selected_case = _selected_case(args.get('case'), scoped_cases)
    snapshot = _snapshot_context(domain=domain, asset_key=selected_asset_key)
    channel_summary = notification_channel_summary()
    routing = routing_policy_rows()
    routing_page, routing_pagination = paginate_sequence(
        routing,
        page=args.get('routing_page', 1),
        per_page=args.get('routing_per_page', 5),
    )
    selected_policy = _selected_routing_policy(args.get('policy'), routing)
    channels = notification_channel_options()
    templates = built_in_templates()
    active_silences = _active_silence_rows(domain=domain, asset_key=selected_asset_key)
    silence_page, silence_pagination = paginate_sequence(
        active_silences,
        page=args.get('silence_page', 1),
        per_page=args.get('silence_per_page', 5),
    )
    now = datetime.now(UTC)

    return {
        'domain': domain,
        'domain_label': _DOMAIN_LABELS[domain],
        'domain_options': [
            {'value': 'kubernetes', 'label': 'Kubernetes', 'count': len(clusters)},
            {'value': 'object_storage', 'label': 'Object Storage', 'count': len(systems)},
        ],
        'assets': assets,
        'selected_asset_key': selected_asset_key,
        'selected_asset_name': selected_asset_name,
        'tab': tab,
        'snapshot': snapshot,
        'summary': {
            'active': len(active_cases),
            'critical': sum(case.severity == 'critical' for case in active_cases),
            'acknowledged': sum(case.workflow_state == 'acknowledged' for case in active_cases),
            'silenced': len(active_silences),
            'verification_pending': sum(case.workflow_state == 'verification_pending' for case in active_cases),
            'resolved_today': sum(
                bool(case.closed_at and _as_utc(case.closed_at) >= now - timedelta(days=1)) for case in history_cases
            ),
            'delivery_failures': _delivery_failure_count(domain=domain, asset_key=selected_asset_key),
            'postmortem_required': sum(case.postmortem_status in {'required', 'draft'} for case in history_cases),
            'routing_policies': len(routing),
            'channels': channel_summary.get('eligible', 0),
        },
        'filters': {'severity': severity, 'workflow': workflow, 'q': search},
        'active_cases': active_page,
        'active_pagination': active_pagination,
        'history_cases': history_page,
        'history_pagination': history_pagination,
        'selected_case': _serialize_case_detail(selected_case) if selected_case else None,
        'routing_policies': routing_page,
        'routing_pagination': routing_pagination,
        'selected_policy': selected_policy,
        'channel_options': channels,
        'notification': channel_summary,
        'templates': templates,
        'silences': silence_page,
        'silence_pagination': silence_pagination,
        'owner_options': _owner_options(),
        'ownership': {
            'source': 'Prometheus/Alertmanager owns rule evaluation and raw alert state.',
            'collection': 'Background workers collect provider evidence into committed KAORI snapshots.',
            'operations': 'KAORI owns acknowledgement, assignment, delivery silences, notification policy, verification, history, and incident evidence.',
            'channels': 'Integrations → Notification Channels owns provider credentials and destination configuration.',
            'archive': 'Platform Operations → Data Lifecycle owns Local/S3 archive storage and verification.',
        },
    }


def list_active_alert_events() -> list[dict[str, Any]]:
    """Return fresh committed alert evidence eligible for Automation Control materialization."""

    events: list[dict[str, Any]] = []
    assets: tuple[tuple[str, list[Any]], ...] = (
        ('kubernetes', list(Cluster.query.order_by(Cluster.id.asc()).all())),
        ('object_storage', list(ObjectStorageSystem.query.order_by(ObjectStorageSystem.id.asc()).all())),
    )
    for domain, rows in assets:
        for asset in rows:
            alert_rows, status, snapshot = load_snapshot_rows(
                domain=domain,
                asset_key=str(asset.id),
                source='auto',
            )
            if not snapshot.get('available') or snapshot.get('serving_last_good'):
                continue
            if not status.get('connected'):
                continue
            for alert in alert_rows:
                state = str(alert.get('status') or alert.get('state') or 'active').lower()
                if state not in {'firing', 'pending', 'active'}:
                    continue
                events.append(
                    {
                        'domain': domain,
                        'asset_key': str(asset.id),
                        'asset_name': str(asset.name),
                        'alert': dict(alert),
                    }
                )
    return events


def _case_rows(*, domain: str, asset_key: str) -> list[AlertCase]:
    query = AlertCase.query.filter(AlertCase.domain == domain)
    if asset_key != 'all':
        query = query.filter(AlertCase.asset_key == asset_key)
    return query.order_by(AlertCase.first_seen_at.desc(), AlertCase.id.desc()).all()


def _filter_cases(cases: list[AlertCase], *, severity: str, workflow: str, search: str) -> list[AlertCase]:
    rows = cases
    if severity != 'all':
        rows = [case for case in rows if case.severity == severity]
    if workflow != 'all':
        rows = [case for case in rows if case.workflow_state == workflow]
    if search:
        needle = search.casefold()
        rows = [
            case
            for case in rows
            if needle
            in ' '.join(
                [case.public_id, case.alert_name, case.asset_name, case.namespace or '', case.summary or '']
            ).casefold()
        ]
    return rows


def _serialize_case(case: AlertCase) -> dict[str, Any]:
    silence = active_delivery_silence(case)
    duration_end = case.closed_at or case.source_resolved_at or datetime.now(UTC)
    duration_seconds = max(int((_as_utc(duration_end) - _as_utc(case.first_seen_at)).total_seconds()), 0)
    owner = case.owner
    return {
        'id': case.id,
        'public_id': case.public_id,
        'alert_name': case.alert_name,
        'severity': case.severity,
        'severity_label': case.severity.title(),
        'severity_tone': _severity_tone(case.severity),
        'source_state': case.source_state,
        'source_state_label': case.source_state.replace('_', ' ').title(),
        'workflow_state': case.workflow_state,
        'workflow_label': case.workflow_state.replace('_', ' ').title(),
        'workflow_tone': _workflow_tone(case.workflow_state),
        'asset_name': case.asset_name,
        'asset_key': case.asset_key,
        'asset_type': case.asset_type,
        'namespace': case.namespace or '-',
        'target': case.target or '-',
        'summary': case.summary or '-',
        'owner': str(getattr(owner, 'username', None) or getattr(owner, 'email', None) or 'Unassigned'),
        'first_seen_at': case.first_seen_at,
        'source_resolved_at': case.source_resolved_at,
        'closed_at': case.closed_at,
        'duration': _duration_label(duration_seconds),
        'silenced': silence is not None,
        'silence_until': silence.ends_at if silence else None,
        'postmortem_status': case.postmortem_status,
        'archive_artifact_id': case.archive_artifact_id,
        'archive_compacted_at': case.archive_compacted_at,
    }


def _serialize_case_detail(case: AlertCase) -> dict[str, Any]:
    base = _serialize_case(case)
    timeline = [
        {
            'event_type': event.event_type,
            'label': event.event_type.replace('_', ' ').title(),
            'summary': event.summary,
            'actor': str(
                getattr(event.actor, 'username', None) or getattr(event.actor, 'email', None) or 'KAORI Worker'
            ),
            'metadata': dict(event.metadata_json or {}),
            'created_at': event.created_at,
        }
        for event in AlertCaseEvent.query.filter_by(case_id=case.id)
        .order_by(AlertCaseEvent.created_at.asc(), AlertCaseEvent.id.asc())
        .all()
    ]
    base.update(
        {
            'labels': dict(case.labels_json or {}),
            'evidence': dict(case.evidence_json or {}),
            'receiver': case.receiver or '-',
            'resolution_summary': case.resolution_summary or '',
            'remediation_steps': list(case.remediation_steps_json or []),
            'verification_evidence': case.verification_evidence or '',
            'change_reference': case.change_reference or '',
            'ticket_reference': case.ticket_reference or '',
            'postmortem_required': case.postmortem_required,
            'postmortem': dict(case.postmortem_json or {}),
            'timeline': timeline,
            'deliveries': case_delivery_rows(case),
        }
    )
    return base


def _snapshot_context(*, domain: str, asset_key: str) -> dict[str, Any]:
    if asset_key == 'all':
        return {
            'available': True,
            'label': 'Committed Case Registry',
            'tone': 'normal',
            'serving_last_good': False,
            'generated_at': None,
            'last_attempt_at': None,
            'refresh_owner': 'Alert Operations Worker',
        }
    _rows, _status, snapshot = load_snapshot_rows(domain=domain, asset_key=asset_key, source='auto')
    return snapshot


def _active_silence_rows(*, domain: str, asset_key: str) -> list[dict[str, Any]]:
    now = datetime.now(UTC)
    query = AlertSilence.query.join(AlertCase, AlertCase.id == AlertSilence.case_id).filter(
        AlertCase.domain == domain,
        AlertSilence.starts_at <= now,
        AlertSilence.ends_at > now,
        AlertSilence.revoked_at.is_(None),
    )
    if asset_key != 'all':
        query = query.filter(AlertCase.asset_key == asset_key)
    return [
        {
            'id': row.id,
            'case_id': row.case.public_id,
            'alert_name': row.case.alert_name,
            'asset_name': row.case.asset_name,
            'severity': row.case.severity,
            'reason': row.reason,
            'starts_at': row.starts_at,
            'ends_at': row.ends_at,
            'created_by': str(
                getattr(row.created_by, 'username', None) or getattr(row.created_by, 'email', None) or 'Unknown'
            ),
        }
        for row in query.order_by(AlertSilence.ends_at.asc()).all()
    ]


def _delivery_failure_count(*, domain: str, asset_key: str) -> int:
    query = NotificationDelivery.query.filter(
        NotificationDelivery.event_type.in_(('alert_ops.firing', 'alert_ops.resolved')),
        NotificationDelivery.domain == domain,
        NotificationDelivery.status == 'failed',
    )
    if asset_key != 'all':
        query = query.filter(NotificationDelivery.asset_key == asset_key)
    return int(query.count())


def _owner_options() -> list[dict[str, Any]]:
    return [
        {
            'id': row.id,
            'label': str(row.username or row.email or f'User {row.id}'),
        }
        for row in User.query.order_by(User.username.asc(), User.id.asc()).all()
        if bool(getattr(row, 'is_active', True))
    ]


def _selected_routing_policy(value: Any, rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    requested = str(value or '').strip()
    if not requested.isdigit():
        return None
    requested_id = int(requested)
    return next((row for row in rows if int(row.get('id') or 0) == requested_id), None)


def _selected_case(value: Any, rows: list[AlertCase]) -> AlertCase | None:
    requested = str(value or '').strip()
    if not requested:
        return None
    return next((case for case in rows if case.public_id == requested), None) or get_case(requested)


def _selected_domain(args: MultiDict[str, str], *, clusters: list[Cluster], systems: list[ObjectStorageSystem]) -> str:
    requested = str(args.get('domain') or '').strip().lower()
    if requested in _VALID_DOMAINS:
        return requested
    if clusters:
        return 'kubernetes'
    if systems:
        return 'object_storage'
    return 'kubernetes'


def _asset_options(domain: str, *, clusters: list[Cluster], systems: list[ObjectStorageSystem]) -> list[dict[str, str]]:
    records = clusters if domain == 'kubernetes' else systems
    return [
        {'value': 'all', 'label': 'All Managed Assets', 'environment': 'Fleet scope'},
        *[
            {
                'value': str(item.id),
                'label': str(item.name),
                'environment': str(item.environment or '-'),
            }
            for item in records
        ],
    ]


def _selected_asset_key(args: MultiDict[str, str], assets: list[dict[str, str]]) -> str:
    requested = str(args.get('asset') or 'all').strip()
    valid = {item['value'] for item in assets}
    return requested if requested in valid else 'all'


def _choice(value: Any, valid: set[str], default: str) -> str:
    normalized = str(value or '').strip().lower()
    return normalized if normalized in valid else default


def _severity_tone(severity: str) -> str:
    return {'critical': 'critical', 'warning': 'warning', 'info': 'info'}.get(severity, 'unknown')


def _workflow_tone(state: str) -> str:
    return {
        'open': 'critical',
        'acknowledged': 'info',
        'mitigating': 'warning',
        'verification_pending': 'warning',
        'closed': 'normal',
    }.get(state, 'unknown')


def _duration_label(seconds: int) -> str:
    minutes = seconds // 60
    if minutes < 60:
        return f'{minutes}m'
    hours, minutes = divmod(minutes, 60)
    if hours < 24:
        return f'{hours}h {minutes}m'
    days, hours = divmod(hours, 24)
    return f'{days}d {hours}h'


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)

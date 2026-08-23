from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from werkzeug.datastructures import MultiDict

from app.common.pagination import paginate_sequence
from app.integrations.delivery.notification_channels.service import notification_channel_summary
from app.intelligence.alert_intelligence.lifecycle import active_delivery_silence, get_case
from app.intelligence.alert_intelligence.notifications import case_delivery_rows
from app.intelligence.alert_intelligence.routing import notification_channel_options, routing_policy_rows
from app.intelligence.alert_intelligence.templates import built_in_templates
from app.models.alert_ops import AlertCase, AlertCaseEvent, AlertSilence
from app.models.cluster import Cluster
from app.models.notification_channel import NotificationDelivery
from app.models.object_storage import ObjectStorageSystem
from app.models.user import User

_VALID_DOMAINS = {'kubernetes', 'object_storage'}
_VALID_TABS = {'overview', 'active', 'routing', 'templates', 'silences', 'resolved', 'history'}
_VALID_SEVERITIES = {'all', 'critical', 'warning', 'info', 'unknown'}
_VALID_WORKFLOW_STATES = {'all', 'open', 'acknowledged', 'mitigating', 'verification_pending'}
_VALID_SOURCE_TYPES = {'all', 'recommendation'}
_DOMAIN_LABELS = {'kubernetes': 'Kubernetes', 'object_storage': 'Object Storage'}
_VALID_ROUTING_DOMAINS = {'all', 'kubernetes', 'object_storage'}
_VALID_ROUTING_STATUSES = {'all', 'enabled', 'disabled'}


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
    if tab == 'history':
        tab = 'resolved'  # Backward-compatible URL alias; UI semantics are source-resolution based.
    severity = _choice(args.get('severity'), _VALID_SEVERITIES, 'all')
    workflow = _choice(args.get('workflow'), _VALID_WORKFLOW_STATES, 'all')
    source_type = _choice(args.get('source'), _VALID_SOURCE_TYPES, 'all')
    search = str(args.get('q') or '').strip()
    silence_search = str(args.get('silence_q') or '').strip()
    silence_severity = _choice(args.get('silence_severity'), _VALID_SEVERITIES, 'all')
    routing_search = str(args.get('routing_q') or '').strip()
    routing_domain = _choice(args.get('routing_domain'), _VALID_ROUTING_DOMAINS, 'all')
    routing_status = _choice(args.get('routing_status'), _VALID_ROUTING_STATUSES, 'all')

    scoped_cases = _case_rows(domain=domain, asset_key=selected_asset_key)
    active_cases = [
        row for row in scoped_cases if row.source_state in {'firing', 'unknown'} and row.workflow_state != 'closed'
    ]
    history_cases = [row for row in scoped_cases if row.source_state == 'resolved' or row.workflow_state == 'closed']
    filtered_active = _filter_cases(
        active_cases, severity=severity, workflow=workflow, source_type=source_type, search=search
    )
    filtered_history = _filter_cases(
        history_cases, severity=severity, workflow='all', source_type=source_type, search=search
    )
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
    all_routing = routing_policy_rows()
    routing = _filter_routing_policies(
        all_routing,
        search=routing_search,
        domain=routing_domain,
        status=routing_status,
    )
    routing_page, routing_pagination = paginate_sequence(
        routing,
        page=args.get('routing_page', 1),
        per_page=args.get('routing_per_page', 5),
    )
    selected_policy = _selected_routing_policy(args.get('policy'), all_routing)
    channels = notification_channel_options()
    templates = built_in_templates()
    active_silences = _active_silence_rows(
        domain=domain,
        asset_key=selected_asset_key,
        search=silence_search,
        severity=silence_severity,
    )
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
            {'value': 'kubernetes', 'label': 'Kubernetes'},
            {'value': 'object_storage', 'label': 'Object Storage'},
        ],
        'assets': assets,
        'selected_asset_key': selected_asset_key,
        'selected_asset_name': selected_asset_name,
        'tab': tab,
        'snapshot': snapshot,
        'summary': {
            'active': len(active_cases),
            'critical': sum(case.severity == 'critical' and case.source_state == 'firing' for case in active_cases),
            'source_unknown': sum(case.source_state == 'unknown' for case in active_cases),
            'acknowledged': sum(case.workflow_state == 'acknowledged' for case in active_cases),
            'silenced': len(active_silences),
            'verification_pending': sum(case.workflow_state == 'verification_pending' for case in history_cases),
            'resolved_today': sum(
                bool(case.source_resolved_at and _as_utc(case.source_resolved_at) >= now - timedelta(days=1))
                for case in history_cases
            ),
            'resolved_total': len(history_cases),
            'closed': sum(case.workflow_state == 'closed' for case in history_cases),
            'false_positive': sum(case.closure_reason == 'false_positive' for case in history_cases),
            'delivery_failures': _delivery_failure_count(domain=domain, asset_key=selected_asset_key),
            'postmortem_required': sum(case.postmortem_status in {'required', 'draft'} for case in history_cases),
            'routing_policies': len(all_routing),
            'channels': channel_summary.get('eligible', 0),
        },
        'filters': {'severity': severity, 'workflow': workflow, 'source': source_type, 'q': search},
        'silence_filters': {'q': silence_search, 'severity': silence_severity},
        'routing_filters': {'q': routing_search, 'domain': routing_domain, 'status': routing_status},
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
            'source': 'KAORI Rule Catalog owns condition evaluation and severity policy for Alert Management.',
            'collection': 'Recommendation evaluation promotes governed findings into durable KAORI Alert Cases.',
            'operations': 'Alert Intelligence owns acknowledgement, assignment, delivery silences, routing, verification, resolved history, and incident evidence.',
            'channels': 'Integrations → Notification Channels owns provider credentials and destination configuration.',
            'archive': 'Platform Operations → Data Lifecycle owns Local/S3 archive storage and verification.',
        },
    }


def list_active_alert_events() -> list[dict[str, Any]]:
    """Compatibility projection of active KAORI AlertCase records.

    New Automation Control code queries AlertCase directly. This projection intentionally
    excludes raw provider snapshots so no consumer can accidentally bypass KAORI lifecycle.
    """
    rows = (
        AlertCase.query.filter(
            AlertCase.source_type == 'recommendation',
            AlertCase.source_state == 'firing',
            AlertCase.workflow_state != 'closed',
        )
        .order_by(AlertCase.first_seen_at.asc(), AlertCase.id.asc())
        .all()
    )
    return [
        {
            'domain': case.domain,
            'asset_key': case.asset_key,
            'asset_name': case.asset_name,
            'alert': {
                'name': case.alert_name,
                'severity': case.severity,
                'namespace': case.namespace,
                'fingerprint': case.fingerprint or case.case_key,
                'labels': dict(case.labels_json or {}),
                'evidence': {**dict(case.evidence_json or {}), 'alert_case_id': case.public_id},
                'rule_key': case.rule_key,
            },
        }
        for case in rows
    ]


def _case_rows(*, domain: str, asset_key: str) -> list[AlertCase]:
    query = AlertCase.query.filter(
        AlertCase.domain == domain,
        AlertCase.source_type == 'recommendation',
    )
    if asset_key != 'all':
        query = query.filter(AlertCase.asset_key == asset_key)
    return query.order_by(AlertCase.first_seen_at.desc(), AlertCase.id.desc()).all()


def _filter_cases(
    cases: list[AlertCase],
    *,
    severity: str,
    workflow: str,
    source_type: str,
    search: str,
) -> list[AlertCase]:
    rows = cases
    if severity != 'all':
        rows = [case for case in rows if case.severity == severity]
    if workflow != 'all':
        rows = [case for case in rows if case.workflow_state == workflow]
    if source_type != 'all':
        rows = [case for case in rows if case.source_type == source_type]
    if search:
        needle = search.casefold()
        rows = [
            case
            for case in rows
            if needle
            in ' '.join(
                [
                    case.public_id,
                    case.alert_name,
                    case.asset_name,
                    case.namespace or '',
                    case.summary or '',
                    case.source_ref or '',
                    case.rule_key or '',
                ]
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
        'source_type': case.source_type,
        'source_type_label': 'KAORI Recommendation',
        'source_ref': case.source_ref or '',
        'rule_key': case.rule_key or '',
        'source_state': case.source_state,
        'source_state_label': _source_state_label(case),
        'source_state_tone': _source_state_tone(case.source_state),
        'source_state_reason': case.source_state_reason or '',
        'source_state_changed_at': case.source_state_changed_at,
        'routing_state': case.routing_state,
        'routing_state_label': 'Suppressed' if case.routing_state == 'suppressed' else 'Enabled',
        'routing_override_reason': case.routing_override_reason or '',
        'routing_override_note': case.routing_override_note or '',
        'routing_override_at': case.routing_override_at,
        'closure_reason': case.closure_reason or '',
        'closure_label': _closure_label(case.closure_reason),
        'workflow_state': case.workflow_state,
        'workflow_label': case.workflow_state.replace('_', ' ').title(),
        'workflow_tone': _workflow_tone(case.workflow_state),
        'asset_name': case.asset_name,
        'asset_key': case.asset_key,
        'asset_type': case.asset_type,
        'namespace': case.namespace or '-',
        'target': case.target or '-',
        'summary': case.summary or '-',
        'owner_user_id': case.owner_user_id,
        'owner': str(getattr(owner, 'username', None) or getattr(owner, 'email', None) or 'Unassigned'),
        'first_seen_at': case.first_seen_at,
        'acknowledged_at': case.acknowledged_at,
        'acknowledgement_expires_at': case.acknowledgement_expires_at,
        'ack_overdue': bool(
            case.acknowledged_at
            and case.acknowledgement_expires_at
            and case.source_state == 'firing'
            and _as_utc(case.acknowledgement_expires_at) <= datetime.now(UTC)
        ),
        'previous_severity': case.previous_severity or '',
        'severity_changed_at': case.severity_changed_at,
        'source_resolved_at': case.source_resolved_at,
        'closed_at': case.closed_at,
        'duration': _duration_label(duration_seconds),
        'silenced': silence is not None,
        'delivery_state': _delivery_state(case, silence=silence),
        'delivery_label': _delivery_label(case, silence=silence),
        'delivery_tone': _delivery_tone(case, silence=silence),
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
            'icon': _timeline_event_icon(event.event_type),
            'tone': _timeline_event_tone(event.event_type),
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
    evidence = dict(case.evidence_json or {})
    deliveries = case_delivery_rows(case)
    timeline_recent = timeline[-5:]
    timeline_older = timeline[:-5]
    deliveries_recent = deliveries[:5]
    deliveries_older = deliveries[5:]
    delivery_target = str(deliveries[0]['channel']) if deliveries else str(case.receiver or '-')
    manual_promotion = evidence.get('promotion_mode') == 'manual' or any(
        event['event_type'] == 'recommendation_promoted'
        and (
            event['metadata'].get('promotion_mode') == 'manual'
            or 'manually promoted' in str(event['summary'] or '').lower()
        )
        for event in timeline
    )
    base.update(
        {
            'labels': dict(case.labels_json or {}),
            'evidence': evidence,
            'evidence_facts': _evidence_facts(evidence),
            'manual_promotion': manual_promotion,
            'receiver': case.receiver or '-',
            'delivery_target': delivery_target,
            'resolution_summary': case.resolution_summary or '',
            'remediation_steps': list(case.remediation_steps_json or []),
            'verification_evidence': case.verification_evidence or '',
            'change_reference': case.change_reference or '',
            'ticket_reference': case.ticket_reference or '',
            'postmortem_required': case.postmortem_required,
            'postmortem': dict(case.postmortem_json or {}),
            'timeline': timeline,
            'timeline_recent': timeline_recent,
            'timeline_older': timeline_older,
            'deliveries': deliveries,
            'deliveries_recent': deliveries_recent,
            'deliveries_older': deliveries_older,
        }
    )
    return base


def _evidence_facts(evidence: dict[str, Any], *, limit: int = 4) -> list[dict[str, str]]:
    preferred = (
        ('affected_count', 'Affected Assets', 'boxes'),
        ('max_restart_count', 'Highest Restart Count', 'rotate-ccw'),
        ('total_restart_count', 'Total Restarts', 'activity'),
        ('max_restart_pod', 'Highest Impact Pod', 'box'),
        ('threshold_display', 'Rule Threshold', 'gauge'),
        ('observed_total_display', 'Observed Total', 'chart-no-axes-column'),
        ('max_observation_display', 'Peak Observation', 'triangle-alert'),
        ('snapshot_basis', 'Snapshot Basis', 'database'),
        ('evidence_window', 'Evidence Window', 'clock-3'),
        ('usage_percent', 'Usage', 'gauge'),
        ('current_usage_percent', 'Current Usage', 'gauge'),
    )
    rows: list[dict[str, str]] = []
    consumed: set[str] = set()
    for key, label, icon in preferred:
        value = evidence.get(key)
        if value in (None, '', [], {}):
            continue
        rows.append({'label': label, 'value': str(value), 'icon': icon})
        consumed.add(key)
        if len(rows) >= limit:
            return rows

    excluded = {
        'affected_assets',
        'cluster_id',
        'object_storage_system_id',
        'asset_key',
        'promotion_mode',
        'automation_resolution',
        'source',
        'source_type',
        'rule_key',
        'recommendation_key',
        'recommendation_count',
    }
    for key, value in evidence.items():
        if key in consumed or key in excluded or isinstance(value, (dict, list, tuple, set)):
            continue
        rendered = str(value).strip()
        if not rendered or len(rendered) > 96:
            continue
        rows.append(
            {
                'label': key.replace('_', ' ').title(),
                'value': rendered,
                'icon': 'database',
            }
        )
        if len(rows) >= limit:
            break
    return rows


def _timeline_event_icon(event_type: str) -> str:
    normalized = str(event_type or '').strip().lower()
    if 'severity_escalated' in normalized:
        return 'triangle-alert'
    if 'resolved' in normalized or 'closed' in normalized:
        return 'badge-check'
    if 'acknowledged' in normalized or 'assigned' in normalized:
        return 'user-check'
    if 'mitigat' in normalized:
        return 'wrench'
    if 'silence' in normalized:
        return 'bell-off'
    if 'routing' in normalized:
        return 'route'
    if 'notif' in normalized or 'delivery' in normalized:
        return 'send-horizontal'
    if 'source' in normalized and 'unknown' in normalized:
        return 'circle-help'
    if 'recommendation' in normalized or 'promoted' in normalized:
        return 'sparkles'
    return 'activity'


def _timeline_event_tone(event_type: str) -> str:
    normalized = str(event_type or '').strip().lower()
    if 'severity_escalated' in normalized or 'failed' in normalized:
        return 'critical'
    if any(token in normalized for token in ('unknown', 'silence', 'suppress', 'mitigat', 'overdue')):
        return 'warning'
    if any(token in normalized for token in ('resolved', 'closed', 'resumed', 'restored')):
        return 'normal'
    return 'info'


def _snapshot_context(*, domain: str, asset_key: str) -> dict[str, Any]:
    del domain, asset_key
    return {
        'available': True,
        'label': 'KAORI Alert Case Registry',
        'tone': 'normal',
        'serving_last_good': False,
        'generated_at': None,
        'last_attempt_at': None,
        'refresh_owner': 'Recommendation Alert Worker',
    }


def _active_silence_rows(
    *,
    domain: str,
    asset_key: str,
    search: str = '',
    severity: str = 'all',
) -> list[dict[str, Any]]:
    now = datetime.now(UTC)
    query = AlertSilence.query.join(AlertCase, AlertCase.id == AlertSilence.case_id).filter(
        AlertCase.domain == domain,
        AlertSilence.starts_at <= now,
        AlertSilence.ends_at > now,
        AlertSilence.revoked_at.is_(None),
    )
    if asset_key != 'all':
        query = query.filter(AlertCase.asset_key == asset_key)
    if severity != 'all':
        query = query.filter(AlertCase.severity == severity)
    rows = query.order_by(AlertSilence.ends_at.asc()).all()
    result = [
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
        for row in rows
    ]
    needle = search.casefold().strip()
    if not needle:
        return result
    return [
        row
        for row in result
        if needle
        in ' '.join(
            [
                str(row['case_id']),
                str(row['alert_name']),
                str(row['asset_name']),
                str(row['reason']),
                str(row['created_by']),
            ]
        ).casefold()
    ]


def _filter_routing_policies(
    rows: list[dict[str, Any]],
    *,
    search: str,
    domain: str,
    status: str,
) -> list[dict[str, Any]]:
    result = rows
    if domain != 'all':
        result = [row for row in result if domain in {str(value) for value in row.get('domains', [])}]
    if status != 'all':
        enabled = status == 'enabled'
        result = [row for row in result if bool(row.get('enabled')) is enabled]
    needle = search.casefold().strip()
    if not needle:
        return result
    return [
        row
        for row in result
        if needle
        in ' '.join(
            [
                str(row.get('name') or ''),
                ' '.join(str(value) for value in row.get('domains', [])),
                ' '.join(str(value) for value in row.get('severities', [])),
                ' '.join(str(channel.get('name') or '') for channel in row.get('channels', [])),
                ' '.join(f'{key}={value}' for key, value in dict(row.get('matchers') or {}).items()),
            ]
        ).casefold()
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


def _source_state_label(case: AlertCase) -> str:
    if case.source_state == 'unknown':
        if case.source_state_reason == 'source_deleted':
            return 'Unknown · Source Deleted'
        return 'Unknown · Source Unavailable'
    return case.source_state.replace('_', ' ').title()


def _source_state_tone(state: str) -> str:
    return {'firing': 'critical', 'resolved': 'normal', 'unknown': 'warning'}.get(state, 'unknown')


def _closure_label(reason: str | None) -> str:
    return {
        'resolved': 'Resolved',
        'manual_withdrawal': 'Withdrawn',
        'source_decommissioned': 'Source Decommissioned',
        'false_positive': 'False Positive',
    }.get(str(reason or ''), '')


def _delivery_state(case: AlertCase, *, silence: AlertSilence | None) -> str:
    if case.routing_state == 'suppressed':
        return 'suppressed'
    if case.source_state == 'unknown':
        return 'held'
    if silence is not None:
        return 'silenced'
    if case.workflow_state == 'acknowledged' and case.acknowledgement_expires_at:
        if _as_utc(case.acknowledgement_expires_at) > datetime.now(UTC):
            return 'ack_paused'
    return 'routed'


def _delivery_label(case: AlertCase, *, silence: AlertSilence | None) -> str:
    state = _delivery_state(case, silence=silence)
    if state == 'suppressed':
        if case.routing_override_reason == 'policy_ineligible':
            return 'Suppressed · Policy'
        if case.routing_override_reason == 'source_deleted':
            return 'Suppressed · Source Deleted'
        if case.routing_override_reason == 'source_unavailable':
            return 'Held · Source Unavailable'
        return 'Notifications Suppressed'
    return {
        'held': 'Held · Source Unknown',
        'silenced': 'Silenced',
        'ack_paused': 'Repeat Paused',
        'routed': 'Policy Managed',
    }.get(state, 'Policy Managed')


def _delivery_tone(case: AlertCase, *, silence: AlertSilence | None) -> str:
    state = _delivery_state(case, silence=silence)
    return {'suppressed': 'warning', 'held': 'warning', 'silenced': 'warning', 'ack_paused': 'info'}.get(state, 'info')


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

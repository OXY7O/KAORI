from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.integrations.delivery.notification_channels.providers import get_notification_provider
from app.models.alert_ops import AlertCase, AlertRoutingPolicy
from app.models.notification_channel import NotificationChannel

KAORI_ALERT_SOURCE_TYPE = 'recommendation'
_DEFAULT_REPEAT_BY_SEVERITY = {'critical': 5, 'warning': 60, 'info': 240, 'unknown': 60}
_DEFAULT_ACK_TIMEOUT_BY_SEVERITY = {'critical': 15, 'warning': 60, 'info': 240, 'unknown': 60}


@dataclass(frozen=True, slots=True)
class RoutingPolicyConfig:
    name: str
    enabled: bool
    domains: list[str]
    severities: list[str]
    source_types: list[str]
    channel_ids: list[int]
    repeat_interval_minutes: int
    acknowledgement_timeout_minutes: int
    send_resolved: bool
    matchers: dict[str, str]


@dataclass(frozen=True, slots=True)
class FiringRoute:
    policy_id: int | None
    channel_id: int
    repeat_interval_minutes: int
    send_resolved: bool

    @property
    def route_key(self) -> str:
        return f'policy-{self.policy_id}' if self.policy_id is not None else 'default'


def routing_policy_rows() -> list[dict[str, Any]]:
    channels = {row.id: row for row in NotificationChannel.query.all()}
    return [
        {
            'id': policy.id,
            'name': policy.name,
            'enabled': policy.enabled,
            'domains': list(policy.domains_json or []),
            'severities': list(policy.severities_json or []),
            'source_types': list(policy.source_types_json or [KAORI_ALERT_SOURCE_TYPE]),
            'matchers': dict(policy.matchers_json or {}),
            'repeat_interval_minutes': policy.repeat_interval_minutes,
            'acknowledgement_timeout_minutes': policy.acknowledgement_timeout_minutes,
            'send_resolved': policy.send_resolved,
            'channels': [
                {
                    'id': channel_id,
                    'name': channels[channel_id].name,
                    'provider': _provider_label(channels[channel_id].provider_key),
                }
                for channel_id in (policy.channel_ids_json or [])
                if channel_id in channels
            ],
        }
        for policy in AlertRoutingPolicy.query.order_by(AlertRoutingPolicy.name.asc()).all()
    ]


def notification_channel_options() -> list[dict[str, Any]]:
    rows = NotificationChannel.query.order_by(NotificationChannel.name.asc(), NotificationChannel.id.asc()).all()
    result: list[dict[str, Any]] = []
    for channel in rows:
        provider = get_notification_provider(channel.provider_key)
        result.append(
            {
                'id': channel.id,
                'name': channel.name,
                'provider_key': channel.provider_key,
                'provider': _provider_label(channel.provider_key),
                'icon': provider.icon if provider is not None else 'send',
                'destination': channel.destination or '-',
                'status': channel.display_status,
                'eligible': bool(channel.enabled and channel.configured and channel.test_status == 'success'),
            }
        )
    return result


def upsert_routing_policy(
    *,
    policy_id: int | None,
    config: RoutingPolicyConfig,
    actor_user_id: int | None,
) -> AlertRoutingPolicy:
    normalized_name = str(config.name or '').strip()
    if not normalized_name:
        raise ValueError('Routing policy name is required.')
    normalized_domains = sorted({value for value in config.domains if value in {'kubernetes', 'object_storage'}})
    normalized_severities = sorted(
        {value for value in config.severities if value in {'critical', 'warning', 'info', 'unknown'}}
    )
    if not normalized_domains:
        raise ValueError('Select at least one Intelligence domain.')
    if not normalized_severities:
        raise ValueError('Select at least one severity.')

    # KAORI Alert Management currently owns recommendation-origin cases only.
    # Keep source_types_json in the schema so external alert ingestion can be enabled later without a migration.
    normalized_source_types = [KAORI_ALERT_SOURCE_TYPE]
    valid_channels = {
        row.id
        for row in NotificationChannel.query.filter(NotificationChannel.id.in_(config.channel_ids)).all()
        if row.enabled and row.configured and row.test_status == 'success'
    }
    if not valid_channels:
        raise ValueError('Select at least one validated Notification Channel.')
    interval = max(5, min(int(config.repeat_interval_minutes or 60), 1440))
    ack_timeout = max(5, min(int(config.acknowledgement_timeout_minutes or 60), 10080))
    row = None if policy_id is None else AlertRoutingPolicy.query.filter_by(id=policy_id).first()
    if row is None:
        row = AlertRoutingPolicy()
        row.created_by_user_id = actor_user_id
    row.name = normalized_name[:160]
    row.enabled = bool(config.enabled)
    row.domains_json = normalized_domains
    row.severities_json = normalized_severities
    row.source_types_json = normalized_source_types
    row.channel_ids_json = sorted(valid_channels)
    row.repeat_interval_minutes = interval
    row.acknowledgement_timeout_minutes = ack_timeout
    row.send_resolved = bool(config.send_resolved)
    row.matchers_json = {
        str(key): str(value) for key, value in config.matchers.items() if str(key).strip() and str(value).strip()
    }
    row.updated_by_user_id = actor_user_id
    return row


def matching_routing_policies(case: AlertCase) -> list[AlertRoutingPolicy]:
    if case.source_type != KAORI_ALERT_SOURCE_TYPE:
        return []
    policies = AlertRoutingPolicy.query.filter_by(enabled=True).order_by(AlertRoutingPolicy.id.asc()).all()
    return [policy for policy in policies if _policy_matches(policy, case)]


def firing_routes(case: AlertCase) -> list[FiringRoute]:
    """Return independent route/channel schedules; never collapse cadence across channels."""
    if case.source_state != 'firing' or case.routing_state != 'enabled':
        return []
    policies = matching_routing_policies(case)
    if policies:
        routes: list[FiringRoute] = []
        for policy in policies:
            repeat = max(int(policy.repeat_interval_minutes or 60), 5)
            routes.extend(
                FiringRoute(
                    policy_id=policy.id,
                    channel_id=int(channel_id),
                    repeat_interval_minutes=repeat,
                    send_resolved=bool(policy.send_resolved),
                )
                for channel_id in (policy.channel_ids_json or [])
            )
        return routes

    repeat = _DEFAULT_REPEAT_BY_SEVERITY.get(case.severity, 60)
    channels = NotificationChannel.query.filter_by(enabled=True).order_by(NotificationChannel.id.asc()).all()
    return [
        FiringRoute(policy_id=None, channel_id=row.id, repeat_interval_minutes=repeat, send_resolved=True)
        for row in channels
        if row.configured
        and row.test_status == 'success'
        and case.domain in (row.domains or [])
        and (
            'alert_ops.firing' in (row.event_types or [])
            or 'alert_intelligence.active_alert' in (row.event_types or [])
        )
    ]


def acknowledgement_timeout_for_case(case: AlertCase) -> int:
    policies = matching_routing_policies(case)
    if policies:
        return min(max(int(policy.acknowledgement_timeout_minutes or 60), 5) for policy in policies)
    return _DEFAULT_ACK_TIMEOUT_BY_SEVERITY.get(case.severity, 60)


def policy_allows_resolved(case: AlertCase, channel_id: int) -> bool:
    policies = matching_routing_policies(case)
    if not policies:
        return True
    return any(policy.send_resolved and channel_id in (policy.channel_ids_json or []) for policy in policies)


def _policy_matches(policy: AlertRoutingPolicy, case: AlertCase) -> bool:
    if case.domain not in (policy.domains_json or []):
        return False
    if case.severity not in (policy.severities_json or []):
        return False
    source_types = policy.source_types_json or [KAORI_ALERT_SOURCE_TYPE]
    if case.source_type not in source_types:
        return False
    labels = case.labels_json or {}
    for key, expected in (policy.matchers_json or {}).items():
        if str(labels.get(key) or '') != str(expected):
            return False
    return True


def _provider_label(provider_key: str) -> str:
    return {
        'telegram': 'Telegram',
        'email': 'Email',
        'microsoft_teams': 'Microsoft Teams',
    }.get(provider_key, provider_key.replace('_', ' ').title())

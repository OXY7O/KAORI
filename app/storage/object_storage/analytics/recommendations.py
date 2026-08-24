from __future__ import annotations

from typing import Any, TypedDict, cast

from app.storage.object_storage.analytics.analysis import (
    CAPACITY_CRITICAL_PERCENT,
    CAPACITY_WARNING_PERCENT,
    ERROR_CRITICAL_PERCENT,
    ERROR_WARNING_PERCENT,
)


class AnalyticsRecommendation(TypedDict):
    priority: str
    tone: str
    title: str
    description: str
    source_label: str
    icon: str
    target_tab: str
    is_actionable: bool


_CONTEXT_LABELS = {
    'capacity': 'Capacity & Usage',
    'performance': 'Performance',
    'forecast': 'Forecast',
    'top_consumers': 'Top Consumers',
    'alerts': 'Alerts & Anomalies',
}


def _as_dict(value: Any) -> dict[str, Any]:
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}


def _optional_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _recommendation(
    *,
    priority: str,
    tone: str,
    title: str,
    description: str,
    source_label: str,
    icon: str,
    target_tab: str,
    is_actionable: bool = True,
) -> AnalyticsRecommendation:
    return {
        'priority': priority,
        'tone': tone,
        'title': title,
        'description': description,
        'source_label': source_label,
        'icon': icon,
        'target_tab': target_tab,
        'is_actionable': is_actionable,
    }


def empty_recommendation_context() -> dict[str, Any]:
    return {
        'recommendation_cards': [],
        'recommendation_context_key': '',
        'recommendation_context_label': 'Analytics',
        'recommendation_count': 0,
        'recommendation_summary': {
            'total': 0,
            'actionable': 0,
            'highest': 'None',
            'tone': 'normal',
        },
    }


def _context(page_key: str, cards: list[AnalyticsRecommendation]) -> dict[str, Any]:
    actionable = sum(item['is_actionable'] for item in cards)
    tones = {item['tone'] for item in cards if item['is_actionable']}
    if 'critical' in tones:
        highest, tone = 'Critical', 'critical'
    elif 'warning' in tones:
        highest, tone = 'Warning', 'warning'
    elif cards:
        highest, tone = 'Info', 'info'
    else:
        highest, tone = 'None', 'normal'
    return {
        'recommendation_cards': cards,
        'recommendation_context_key': page_key,
        'recommendation_context_label': _CONTEXT_LABELS.get(page_key, 'Analytics'),
        'recommendation_count': actionable,
        'recommendation_summary': {
            'total': len(cards),
            'actionable': actionable,
            'highest': highest,
            'tone': tone,
        },
    }


def build_capacity_recommendations(metrics: dict[str, Any]) -> list[AnalyticsRecommendation]:
    cards: list[AnalyticsRecommendation] = []
    utilization = _optional_float(metrics.get('utilization'))
    capacity_usage = _as_dict(metrics.get('capacity_usage'))
    trend = _as_dict(metrics.get('usage_trend_summary'))

    if not capacity_usage.get('capacity_evidence_available') and utilization is None:
        cards.append(
            _recommendation(
                priority='P3',
                tone='unknown',
                title='Restore Capacity Evidence',
                description='Capacity and usage evidence is incomplete. Refresh the committed Metrics Source snapshot before interpreting headroom.',
                source_label='Capacity & Usage',
                icon='database-zap',
                target_tab='evidence',
                is_actionable=False,
            )
        )
    elif utilization is not None and utilization >= CAPACITY_CRITICAL_PERCENT:
        cards.append(
            _recommendation(
                priority='P1',
                tone='critical',
                title='Protect Critical Capacity Headroom',
                description=f'Physical utilization is {utilization:.1f}%. Validate growth ownership and prepare capacity expansion or demand reduction before additional storage growth.',
                source_label='Capacity & Usage',
                icon='gauge',
                target_tab='summary',
            )
        )
    elif utilization is not None and utilization >= CAPACITY_WARNING_PERCENT:
        cards.append(
            _recommendation(
                priority='P2',
                tone='warning',
                title='Review Capacity Pressure',
                description=f'Physical utilization is {utilization:.1f}%. Review headroom, bucket concentration, and recent growth before approving more demand.',
                source_label='Capacity & Usage',
                icon='gauge',
                target_tab='summary',
            )
        )

    critical_quota = int(capacity_usage.get('quota_critical_count') or 0)
    warning_quota = int(capacity_usage.get('quota_warning_count') or 0)
    unknown_quota = int(capacity_usage.get('quota_unknown_count') or 0)
    if critical_quota:
        cards.append(
            _recommendation(
                priority='P1',
                tone='critical',
                title='Review Critical Bucket Quotas',
                description=f'{critical_quota} bucket(s) are inside the critical quota boundary. Review quota ownership and near-term growth before write demand increases.',
                source_label='Bucket Quota',
                icon='container',
                target_tab='quota',
            )
        )
    elif warning_quota:
        cards.append(
            _recommendation(
                priority='P2',
                tone='warning',
                title='Review Bucket Quota Pressure',
                description=f'{warning_quota} bucket(s) are above the quota review boundary. Validate allocation and growth expectations.',
                source_label='Bucket Quota',
                icon='container',
                target_tab='quota',
            )
        )
    if unknown_quota:
        cards.append(
            _recommendation(
                priority='P3',
                tone='unknown',
                title='Close Bucket Quota Evidence Gaps',
                description=f'{unknown_quota} bucket(s) do not have observed quota state. Treat quota posture as incomplete until inventory evidence is collected.',
                source_label='Bucket Quota',
                icon='scan-search',
                target_tab='quota',
                is_actionable=False,
            )
        )

    direction = str(trend.get('direction') or '').lower()
    if direction == 'increasing' and utilization is not None and utilization >= 75:
        cards.append(
            _recommendation(
                priority='P2',
                tone='warning',
                title='Validate Growth Against Remaining Headroom',
                description='Usage is increasing while physical utilization is already elevated. Confirm whether the current growth rate is expected and sustainable.',
                source_label='Usage Trend',
                icon='chart-no-axes-combined',
                target_tab='trend',
            )
        )
    return cards


def build_performance_recommendations(metrics: dict[str, Any]) -> list[AnalyticsRecommendation]:
    cards: list[AnalyticsRecommendation] = []
    error_ratio = _optional_float(metrics.get('error_ratio'))
    waiting = _optional_float(metrics.get('waiting'))
    offline_nodes = _optional_float(metrics.get('offline_nodes'))
    performance = _as_dict(metrics.get('performance'))

    if offline_nodes is not None and offline_nodes > 0:
        cards.append(
            _recommendation(
                priority='P1',
                tone='critical',
                title='Restore Offline Storage Nodes',
                description=f'{offline_nodes:,.0f} storage node(s) are offline. Validate node health and redundancy before treating request performance as stable.',
                source_label='Storage Node Health',
                icon='server-off',
                target_tab='reliability',
            )
        )
    if error_ratio is None:
        cards.append(
            _recommendation(
                priority='P3',
                tone='unknown',
                title='Restore Request Error Evidence',
                description='Request error ratio is unavailable. Refresh the committed performance snapshot before concluding request health is normal.',
                source_label='Request Health',
                icon='database-zap',
                target_tab='evidence',
                is_actionable=False,
            )
        )
    elif error_ratio >= ERROR_CRITICAL_PERCENT:
        cards.append(
            _recommendation(
                priority='P1',
                tone='critical',
                title='Triage Critical Request Error Pressure',
                description=f'Request error ratio is {error_ratio:.1f}%. Correlate error trend, affected buckets, and storage-node state before increasing traffic.',
                source_label='Request Health',
                icon='circle-alert',
                target_tab='reliability',
            )
        )
    elif error_ratio >= ERROR_WARNING_PERCENT:
        cards.append(
            _recommendation(
                priority='P2',
                tone='warning',
                title='Review Elevated Request Errors',
                description=f'Request error ratio is {error_ratio:.1f}%. Review error direction and bucket-level activity for recurring pressure.',
                source_label='Request Health',
                icon='triangle-alert',
                target_tab='reliability',
            )
        )
    if waiting is not None and waiting > 0:
        cards.append(
            _recommendation(
                priority='P2',
                tone='warning',
                title='Review Waiting Request Pressure',
                description=f'{waiting:,.0f} request(s) are waiting. Compare queue pressure with current request rate and traffic direction.',
                source_label='Request Queue',
                icon='list-restart',
                target_tab='reliability',
            )
        )

    if int(performance.get('bucket_count') or 0) > int(performance.get('bucket_request_evidence_count') or 0):
        cards.append(
            _recommendation(
                priority='P3',
                tone='unknown',
                title='Close Bucket Request Evidence Gaps',
                description='One or more buckets lack request-rate evidence. Validate bucket metric coverage before ranking request activity.',
                source_label='Bucket Activity',
                icon='scan-search',
                target_tab='buckets',
                is_actionable=False,
            )
        )
    return cards


def build_forecast_recommendations(
    metrics: dict[str, Any],
    materialization: dict[str, Any],
) -> list[AnalyticsRecommendation]:
    if not materialization.get('usable'):
        return [
            _recommendation(
                priority='P3',
                tone='unknown',
                title='Refresh Forecast Evidence',
                description='Forecast materialization is missing or stale. Refresh worker evidence before using projected capacity values for planning.',
                source_label='Forecast Worker',
                icon='cpu',
                target_tab='worker',
                is_actionable=False,
            )
        ]

    cards: list[AnalyticsRecommendation] = []
    forecast = _as_dict(metrics.get('forecast'))
    posture = _as_dict(metrics.get('forecast_posture'))
    days_to_capacity = _optional_float(forecast.get('days_to_capacity'))
    growth_per_day = _optional_float(forecast.get('growth_per_day'))
    tone = str(posture.get('tone') or 'unknown')
    if tone == 'critical':
        cards.append(
            _recommendation(
                priority='P1',
                tone='critical',
                title='Prepare Near-Term Capacity Remediation',
                description=(
                    f'Projected capacity exhaustion is {days_to_capacity:.1f} days away.'
                    if days_to_capacity is not None
                    else 'Forecast posture is critical. Validate the projected exhaustion boundary and prepare capacity remediation.'
                ),
                source_label='Forecast Outlook',
                icon='timer',
                target_tab='outlook',
            )
        )
    elif tone == 'warning':
        cards.append(
            _recommendation(
                priority='P2',
                tone='warning',
                title='Review Forecast Capacity Window',
                description=(
                    f'Projected capacity exhaustion is {days_to_capacity:.1f} days away.'
                    if days_to_capacity is not None
                    else 'Forecast posture requires review. Validate growth on a longer history window before scheduling remediation.'
                ),
                source_label='Forecast Outlook',
                icon='chart-spline',
                target_tab='outlook',
            )
        )
    elif growth_per_day is not None and growth_per_day > 0 and days_to_capacity is None:
        cards.append(
            _recommendation(
                priority='P3',
                tone='info',
                title='Track Positive Storage Growth',
                description='Storage usage is growing, but no near-term exhaustion boundary is currently available. Continue validating the trend across longer history windows.',
                source_label='Usage Trend',
                icon='trending-up',
                target_tab='trend',
                is_actionable=False,
            )
        )

    summary = _as_dict(metrics.get('bucket_forecast_summary'))
    critical = int(summary.get('critical_count') or 0)
    warning = int(summary.get('warning_count') or 0)
    gaps = int(summary.get('history_gap_count') or 0)
    if critical:
        cards.append(
            _recommendation(
                priority='P1',
                tone='critical',
                title='Review Critical Bucket Forecasts',
                description=f'{critical} bucket forecast(s) are inside a critical capacity or quota watch boundary.',
                source_label='Bucket Forecasts',
                icon='container',
                target_tab='buckets',
            )
        )
    elif warning:
        cards.append(
            _recommendation(
                priority='P2',
                tone='warning',
                title='Review Bucket Forecast Watch',
                description=f'{warning} bucket forecast(s) require planned capacity or quota review.',
                source_label='Bucket Forecasts',
                icon='container',
                target_tab='buckets',
            )
        )
    if gaps:
        cards.append(
            _recommendation(
                priority='P3',
                tone='unknown',
                title='Improve Bucket Forecast History',
                description=f'{gaps} bucket(s) do not yet have sufficient history for a reliable forecast.',
                source_label='Forecast History',
                icon='history',
                target_tab='worker',
                is_actionable=False,
            )
        )
    return cards


def build_top_consumer_recommendations(metrics: dict[str, Any]) -> list[AnalyticsRecommendation]:
    cards: list[AnalyticsRecommendation] = []
    analysis = _as_dict(metrics.get('bucket_analysis'))
    bucket_count = int(analysis.get('bucket_count') or 0)
    if bucket_count == 0:
        return [
            _recommendation(
                priority='P3',
                tone='unknown',
                title='Collect Consumer Evidence',
                description='No bucket consumer evidence is available for the selected system and time window.',
                source_label='Consumer Records',
                icon='database-zap',
                target_tab='evidence',
                is_actionable=False,
            )
        ]

    share = _optional_float(analysis.get('top_usage_share'))
    if share is not None and share >= 70:
        cards.append(
            _recommendation(
                priority='P2',
                tone='warning',
                title='Review Highly Concentrated Storage Usage',
                description=f'The largest bucket represents {share:.1f}% of known storage usage. Validate ownership, quota protection, and growth concentration.',
                source_label='Storage Leaders',
                icon='layers-3',
                target_tab='storage',
            )
        )
    elif share is not None and share >= 50:
        cards.append(
            _recommendation(
                priority='P3',
                tone='info',
                title='Track Concentrated Storage Usage',
                description=f'The largest bucket represents {share:.1f}% of known storage usage. Monitor whether concentration continues to increase.',
                source_label='Storage Leaders',
                icon='layers-3',
                target_tab='storage',
                is_actionable=False,
            )
        )

    critical_quota = int(analysis.get('critical_quota_count') or 0)
    pressure = int(analysis.get('quota_pressure_count') or 0)
    if critical_quota:
        cards.append(
            _recommendation(
                priority='P1',
                tone='critical',
                title='Prioritize Critical Consumer Quotas',
                description=f'{critical_quota} ranked bucket(s) are inside a critical quota boundary.',
                source_label='Consumer Records',
                icon='gauge',
                target_tab='records',
            )
        )
    elif pressure:
        cards.append(
            _recommendation(
                priority='P2',
                tone='warning',
                title='Review Consumer Quota Pressure',
                description=f'{pressure} ranked bucket(s) are above the quota review boundary.',
                source_label='Consumer Records',
                icon='gauge',
                target_tab='records',
            )
        )

    request_count = int(analysis.get('request_evidence_count') or 0)
    error_count = int(analysis.get('error_evidence_count') or 0)
    if request_count < bucket_count or error_count < bucket_count:
        cards.append(
            _recommendation(
                priority='P3',
                tone='unknown',
                title='Close Consumer Activity Evidence Gaps',
                description='Request or error evidence is incomplete for ranked buckets. Validate bucket-level metric coverage before interpreting activity concentration.',
                source_label='Request Activity',
                icon='scan-search',
                target_tab='activity',
                is_actionable=False,
            )
        )
    return cards


def build_alert_recommendations(
    *,
    alert_posture: dict[str, Any],
    metrics: dict[str, Any],
) -> list[AnalyticsRecommendation]:
    cards: list[AnalyticsRecommendation] = []
    critical = int(alert_posture.get('critical') or 0)
    warning = int(alert_posture.get('warning') or 0)
    if critical:
        cards.append(
            _recommendation(
                priority='P1',
                tone='critical',
                title='Triage Critical Provider Alerts',
                description=f'{critical} critical provider alert(s) are active. Validate affected scope and supporting metric evidence before remediation.',
                source_label='Provider Alerts',
                icon='siren',
                target_tab='records',
            )
        )
    elif warning:
        cards.append(
            _recommendation(
                priority='P2',
                tone='warning',
                title='Review Warning Provider Alerts',
                description=f'{warning} warning provider alert(s) are active. Check recurrence and correlated metric signals.',
                source_label='Provider Alerts',
                icon='bell-ring',
                target_tab='records',
            )
        )

    signals = [_as_dict(item) for item in metrics.get('signals') or [] if isinstance(item, dict)]
    signal_critical = sum(str(item.get('severity') or '').lower() == 'critical' for item in signals)
    signal_warning = sum(str(item.get('severity') or '').lower() == 'warning' for item in signals)
    if signal_critical:
        cards.append(
            _recommendation(
                priority='P1',
                tone='critical',
                title='Investigate Critical Anomaly Signals',
                description=f'{signal_critical} metric-derived signal(s) cross a critical operating boundary. Correlate them with provider alerts and system evidence.',
                source_label='Anomaly Signals',
                icon='radar',
                target_tab='signals',
            )
        )
    elif signal_warning:
        cards.append(
            _recommendation(
                priority='P2',
                tone='warning',
                title='Review Anomaly Signals',
                description=f'{signal_warning} metric-derived signal(s) cross a warning operating boundary. Review the underlying capacity, request, queue, or node evidence.',
                source_label='Anomaly Signals',
                icon='radar',
                target_tab='signals',
            )
        )
    if str(alert_posture.get('tone') or '') == 'unknown' and not signal_critical and not signal_warning:
        cards.append(
            _recommendation(
                priority='P3',
                tone='unknown',
                title='Restore Alert Evidence',
                description='Provider alert posture is unavailable and no actionable anomaly signal is confirmed. Restore source readiness before interpreting the absence of alerts.',
                source_label='Alert Evidence',
                icon='wifi-off',
                target_tab='evidence',
                is_actionable=False,
            )
        )
    return cards


def build_page_recommendation_context(
    *,
    page_key: str,
    metrics: dict[str, Any],
    forecast_materialization: dict[str, Any] | None = None,
    alert_posture: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if page_key == 'capacity':
        cards = build_capacity_recommendations(metrics)
    elif page_key == 'performance':
        cards = build_performance_recommendations(metrics)
    elif page_key == 'forecast':
        cards = build_forecast_recommendations(metrics, forecast_materialization or {})
    elif page_key == 'top_consumers':
        cards = build_top_consumer_recommendations(metrics)
    elif page_key == 'alerts':
        cards = build_alert_recommendations(alert_posture=alert_posture or {}, metrics=metrics)
    else:
        cards = []
    return _context(page_key, cards)


def apply_recommendation_context(context: dict[str, Any], *, page_key: str) -> None:
    context.update(
        build_page_recommendation_context(
            page_key=page_key,
            metrics=_as_dict(context.get('metrics')),
            forecast_materialization=_as_dict(context.get('forecast_materialization')),
            alert_posture=_as_dict(context.get('alert_posture')),
        )
    )

from __future__ import annotations

from dataclasses import dataclass

CAPACITY_WARNING_PERCENT = 85.0
CAPACITY_CRITICAL_PERCENT = 95.0
ERROR_WARNING_PERCENT = 5.0
ERROR_CRITICAL_PERCENT = 10.0
FORECAST_WARNING_DAYS = 90.0
FORECAST_CRITICAL_DAYS = 30.0
RECONCILIATION_ALIGNED_PERCENT = 5.0
RECONCILIATION_REVIEW_PERCENT = 15.0


@dataclass(frozen=True, slots=True)
class TrendSummary:
    sample_count: int
    first_value: float | None
    current_value: float | None
    delta: float | None
    delta_percent: float | None
    growth_per_day: float | None
    direction: str


@dataclass(frozen=True, slots=True)
class EvidenceComparison:
    operational_value: float | None
    inventory_value: float | None
    delta: float | None
    delta_percent: float | None
    status: str
    tone: str


@dataclass(frozen=True, slots=True)
class OperationalPosture:
    status: str
    tone: str
    headline: str
    detail: str


def percentage(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return numerator / denominator * 100.0


def error_ratio(error_rate: float | None, request_rate: float | None) -> float | None:
    if request_rate is None or request_rate <= 0:
        return 0.0 if error_rate == 0 else None
    if error_rate is None:
        return None
    return max(0.0, error_rate / request_rate * 100.0)


def derive_headroom(
    total_bytes: float | None,
    free_bytes: float | None,
    used_bytes: float | None,
) -> tuple[float | None, str]:
    if free_bytes is not None:
        return max(0.0, free_bytes), 'Operational Metric'
    if total_bytes is not None and used_bytes is not None:
        return max(0.0, total_bytes - used_bytes), 'Derived from Capacity − Usage'
    return None, 'Unavailable'


def summarize_trend(points: list[dict[str, float]]) -> TrendSummary:
    valid = [
        point
        for point in points
        if isinstance(point.get('timestamp'), (int, float)) and isinstance(point.get('value'), (int, float))
    ]
    if not valid:
        return TrendSummary(0, None, None, None, None, None, 'unknown')
    first = valid[0]
    last = valid[-1]
    first_value = float(first['value'])
    current_value = float(last['value'])
    delta = current_value - first_value
    delta_percent = percentage(delta, abs(first_value)) if first_value != 0 else None
    growth_per_day: float | None = None
    if len(valid) >= 2:
        elapsed_seconds = float(last['timestamp']) - float(first['timestamp'])
        if elapsed_seconds > 0:
            growth_per_day = delta / (elapsed_seconds / 86400.0)
    epsilon = max(abs(first_value), abs(current_value), 1.0) * 0.001
    if abs(delta) <= epsilon:
        direction = 'stable'
    elif delta > 0:
        direction = 'increasing'
    else:
        direction = 'decreasing'
    return TrendSummary(
        sample_count=len(valid),
        first_value=first_value,
        current_value=current_value,
        delta=delta,
        delta_percent=delta_percent,
        growth_per_day=growth_per_day,
        direction=direction,
    )


def compare_evidence(operational: float | None, inventory: float | int | None) -> EvidenceComparison:
    inventory_value = float(inventory) if inventory is not None else None
    if operational is None or inventory_value is None:
        return EvidenceComparison(operational, inventory_value, None, None, 'Unknown', 'unknown')
    delta = operational - inventory_value
    denominator = max(abs(operational), abs(inventory_value), 1.0)
    delta_percent = abs(delta) / denominator * 100.0
    if delta_percent <= RECONCILIATION_ALIGNED_PERCENT:
        return EvidenceComparison(operational, inventory_value, delta, delta_percent, 'Within Baseline', 'normal')
    if delta_percent <= RECONCILIATION_REVIEW_PERCENT:
        return EvidenceComparison(operational, inventory_value, delta, delta_percent, 'Review Drift', 'warning')
    return EvidenceComparison(operational, inventory_value, delta, delta_percent, 'Material Drift', 'warning')


def capacity_posture(utilization: float | None) -> OperationalPosture:
    if utilization is None:
        return OperationalPosture(
            'Unknown',
            'unknown',
            'Capacity posture cannot be confirmed',
            'Usable capacity and usage evidence are incomplete for the selected system.',
        )
    if utilization >= CAPACITY_CRITICAL_PERCENT:
        return OperationalPosture(
            'Critical',
            'critical',
            'Usable capacity is inside the critical operating boundary',
            f'Utilization is {utilization:.1f}%; protect headroom before additional storage growth is approved.',
        )
    if utilization >= CAPACITY_WARNING_PERCENT:
        return OperationalPosture(
            'Pressure',
            'warning',
            'Usable capacity requires planned remediation',
            f'Utilization is {utilization:.1f}%; review growth direction and highest-consuming buckets.',
        )
    return OperationalPosture(
        'Healthy',
        'normal',
        'Usable capacity remains inside the baseline operating boundary',
        f'Utilization is {utilization:.1f}%; continue monitoring growth and bucket concentration.',
    )


def performance_posture(
    *,
    error_percent: float | None,
    waiting: float | None,
    offline_nodes: float | None,
) -> OperationalPosture:
    if (offline_nodes or 0) > 0 or (error_percent is not None and error_percent >= ERROR_CRITICAL_PERCENT):
        return OperationalPosture(
            'Critical',
            'critical',
            'Service reliability requires immediate triage',
            'Offline storage nodes or critical request error pressure is present in the current evidence.',
        )
    if (waiting or 0) > 0 or (error_percent is not None and error_percent >= ERROR_WARNING_PERCENT):
        return OperationalPosture(
            'Degraded',
            'warning',
            'Request handling is outside the normal baseline',
            'Review error pressure, waiting requests, and throughput direction before increasing demand.',
        )
    if error_percent is None:
        return OperationalPosture(
            'Unknown',
            'unknown',
            'Performance posture cannot be confirmed',
            'Request error evidence is unavailable, so a healthy request-path conclusion would be unsafe.',
        )
    if waiting is None or offline_nodes is None:
        return OperationalPosture(
            'Partial Evidence',
            'unknown',
            'Request reliability is inside baseline but supporting evidence is incomplete',
            'Current error ratio is below the review boundary, but queue or storage-node evidence is unavailable.',
        )
    return OperationalPosture(
        'Healthy',
        'normal',
        'No immediate request-path pressure is indicated',
        'Current request errors, queue pressure, and storage-node evidence remain inside the baseline boundary.',
    )


def forecast_posture(growth_per_day: float | None, days_to_capacity: float | None) -> OperationalPosture:
    if growth_per_day is None:
        return OperationalPosture(
            'Unknown',
            'unknown',
            'Growth direction cannot be established yet',
            'More historical usage samples are required before capacity planning conclusions are reliable.',
        )
    if growth_per_day <= 0:
        return OperationalPosture(
            'Stable',
            'normal',
            'Current history does not indicate positive capacity growth',
            'The selected window is stable or decreasing; continue monitoring longer windows before reducing headroom.',
        )
    if days_to_capacity is not None and days_to_capacity <= FORECAST_CRITICAL_DAYS:
        return OperationalPosture(
            'Critical',
            'critical',
            'Projected capacity exhaustion is inside 30 days',
            'Validate sustained growth and prepare capacity expansion or demand reduction immediately.',
        )
    if days_to_capacity is not None and days_to_capacity <= FORECAST_WARNING_DAYS:
        return OperationalPosture(
            'Review',
            'warning',
            'Projected capacity exhaustion is inside 90 days',
            'Confirm the trend on a longer window and schedule capacity remediation before the operating margin narrows.',
        )
    return OperationalPosture(
        'Healthy',
        'normal',
        'Projected growth remains outside the near-term capacity boundary',
        'Continue monitoring slope changes and the highest-contributing buckets.',
    )

def metric_risk_signals(
    *,
    utilization: float | None,
    error_ratio: float | None,
    waiting: float | None,
    offline_nodes: float | None,
) -> list[dict[str, str]]:
    if all(value is None for value in (utilization, error_ratio, waiting, offline_nodes)):
        return [
            {
                'severity': 'unknown',
                'title': 'Metric Evidence Unavailable',
                'detail': 'Operational risk cannot be evaluated until metric evidence is available.',
            }
        ]

    signals: list[dict[str, str]] = []
    if utilization is not None and utilization >= CAPACITY_CRITICAL_PERCENT:
        signals.append(
            {
                'severity': 'critical',
                'title': 'Capacity Critical',
                'detail': f'Usable capacity is {utilization:.1f}% consumed.',
            }
        )
    elif utilization is not None and utilization >= CAPACITY_WARNING_PERCENT:
        signals.append(
            {
                'severity': 'warning',
                'title': 'Capacity Pressure',
                'detail': f'Usable capacity is {utilization:.1f}% consumed.',
            }
        )
    if error_ratio is not None and error_ratio >= ERROR_CRITICAL_PERCENT:
        signals.append(
            {
                'severity': 'critical',
                'title': 'Request Error Pressure',
                'detail': f'Observed request error ratio is {error_ratio:.1f}%.',
            }
        )
    elif error_ratio is not None and error_ratio >= ERROR_WARNING_PERCENT:
        signals.append(
            {
                'severity': 'warning',
                'title': 'Request Error Increase',
                'detail': f'Observed request error ratio is {error_ratio:.1f}%.',
            }
        )
    if waiting is not None and waiting > 0:
        signals.append(
            {
                'severity': 'warning',
                'title': 'Requests Waiting',
                'detail': f'{waiting:,.0f} requests are currently waiting.',
            }
        )
    if offline_nodes is not None and offline_nodes > 0:
        signals.append(
            {
                'severity': 'critical',
                'title': 'Offline Storage Nodes',
                'detail': f'{offline_nodes:,.0f} storage nodes are offline.',
            }
        )
    if not signals:
        signals.append(
            {
                'severity': 'normal',
                'title': 'No Metric-Derived Risk',
                'detail': (
                    'Current operational metric evidence does not cross the baseline capacity, '
                    'error, queue, or node thresholds.'
                ),
            }
        )
    return signals

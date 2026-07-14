from __future__ import annotations

from typing import Any

from app.dashboards.kubernetes.schema import ConsumerItem, TopConsumersSnapshot
from app.dashboards.kubernetes.utils import safe_optional_float


def top_consumers_snapshot_with_message(
    message: str,
    *,
    source_status: str = 'Unavailable',
) -> TopConsumersSnapshot:
    snapshot = TopConsumersSnapshot()
    snapshot.source_status = source_status
    snapshot.message = message
    return snapshot

def build_top_consumers_snapshot(*, live_cluster: Any | None) -> TopConsumersSnapshot:
    if live_cluster is None:
        return top_consumers_snapshot_with_message('Select a specific cluster to load top consumer snapshots.')

    try:
        from app.analytics.top_consumers.service import TopConsumersService
        from app.analytics.utilization.service import UtilizationService
        from app.prometheus.service import PrometheusService

        utilization = UtilizationService(PrometheusService(live_cluster))
        service = TopConsumersService(utilization)
        payload = service.get_top_consumers_payload(
            selected_namespace='',
            selected_resource='all',
            selected_search='',
            selected_sort='usage_percent',
            selected_focus='',
            page=1,
            per_page=10,
        )
    except Exception as exc:
        return top_consumers_snapshot_with_message(f'Top consumers snapshot unavailable: {exc}')

    rows = payload.get('all_rows') or payload.get('rows') or []
    if not isinstance(rows, list):
        rows = []

    cpu_rows = [row for row in rows if str(row.get('resource_type')) == 'cpu']
    memory_rows = [row for row in rows if str(row.get('resource_type')) == 'memory']

    insight = _build_top_consumers_insight(rows=rows, cpu_rows=cpu_rows, memory_rows=memory_rows)

    snapshot = TopConsumersSnapshot()
    snapshot.cpu = _consumer_items(cpu_rows[:3])
    snapshot.memory = _consumer_items(memory_rows[:3])
    snapshot.source_status = 'Available' if rows else 'Unavailable'
    snapshot.message = (
        'Top consumers loaded from Prometheus.'
        if rows
        else 'No top consumer rows returned by Prometheus.'
    )
    snapshot.insight_title = str(insight['title'])
    snapshot.insight_description = str(insight['description'])
    snapshot.insight_items = list(insight['items'])
    snapshot.missing_request_limit_count = int(insight['missing_request_limit_count'])
    snapshot.high_usage_count = int(insight['high_usage_count'])
    return snapshot

def _consumer_items(rows: list[dict[str, Any]]) -> list[ConsumerItem]:
    items: list[ConsumerItem] = []
    for index, row in enumerate(rows, start=1):
        request_value = safe_optional_float(row.get('request')) or 0.0
        limit_value = safe_optional_float(row.get('limit')) or 0.0
        raw_percent = safe_optional_float(row.get('usage_percent'))

        has_denominator = request_value > 0 or limit_value > 0
        percent = raw_percent if has_denominator else None
        signal_state = _consumer_signal_state(row=row, percent=percent, has_denominator=has_denominator)
        signal_label = _consumer_signal_label(
            request_value=request_value,
            limit_value=limit_value,
            percent=percent,
            signal_state=signal_state,
        )

        items.append(
            ConsumerItem(
                rank=index,
                name=str(row.get('workload') or row.get('pod') or row.get('container') or '-'),
                namespace=str(row.get('namespace') or '-'),
                value=str(row.get('current_display') or row.get('value') or '-'),
                percent=percent,
                request_display=str(row.get('request_display') or '-'),
                limit_display=str(row.get('limit_display') or '-'),
                signal_label=signal_label,
                signal_state=signal_state,
            )
        )
    return items

def _consumer_signal_state(*, row: dict[str, Any], percent: float | None, has_denominator: bool) -> str:
    if not has_denominator or percent is None:
        return 'unknown'

    risk = row.get('risk')
    if isinstance(risk, dict):
        key = str(risk.get('key') or risk.get('level') or '').lower()
        if key in {'critical', 'warning', 'normal'}:
            return key

    if percent >= 90:
        return 'critical'
    if percent >= 75:
        return 'warning'
    return 'normal'

def _consumer_signal_label(
    *,
    request_value: float,
    limit_value: float,
    percent: float | None,
    signal_state: str,
) -> str:
    if request_value <= 0 and limit_value <= 0:
        return 'Usage only'
    if request_value <= 0:
        return 'No request'
    if limit_value <= 0:
        return 'No limit'
    if percent is None:
        return 'Unknown'
    if signal_state == 'critical':
        return 'Critical usage'
    if signal_state == 'warning':
        return 'Warning usage'
    return 'Within range'

def _build_top_consumers_insight(
    *,
    rows: list[dict[str, Any]],
    cpu_rows: list[dict[str, Any]],
    memory_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    if not rows:
        return {
            'title': 'Consumer insights',
            'description': 'No top consumer rows were returned by Prometheus for this cluster.',
            'items': ['Prometheus returned no CPU or memory consumer rows.'],
            'missing_request_limit_count': 0,
            'high_usage_count': 0,
        }

    cpu_memory_rows = [row for row in rows if str(row.get('resource_type') or '').lower() in {'cpu', 'memory'}]

    missing_request_limit = []
    high_usage = []
    namespaces: dict[str, int] = {}

    for row in cpu_memory_rows:
        request_value = safe_optional_float(row.get('request')) or 0.0
        limit_value = safe_optional_float(row.get('limit')) or 0.0
        percent = safe_optional_float(row.get('usage_percent'))
        namespace = str(row.get('namespace') or '-')
        namespaces[namespace] = namespaces.get(namespace, 0) + 1

        if request_value <= 0 or limit_value <= 0:
            missing_request_limit.append(row)

        if percent is not None and percent >= 75 and (request_value > 0 or limit_value > 0):
            high_usage.append(row)

    top_cpu = cpu_rows[0] if cpu_rows else None
    top_memory = memory_rows[0] if memory_rows else None
    dominant_namespace = '-'
    if namespaces:
        dominant_namespace = max(namespaces.items(), key=lambda item: item[1])[0]

    insight_items: list[str] = []
    if top_cpu:
        insight_items.append(f"Highest CPU: {top_cpu.get('workload') or top_cpu.get('pod') or '-'}")
    if top_memory:
        insight_items.append(f"Highest Memory: {top_memory.get('workload') or top_memory.get('pod') or '-'}")
    if dominant_namespace != '-':
        insight_items.append(f'Dominant namespace: {dominant_namespace}')
    if missing_request_limit:
        insight_items.append(f'{len(missing_request_limit)} consumer row(s) missing request or limit context')
    if high_usage:
        insight_items.append(f'{len(high_usage)} consumer row(s) above 75% usage')

    if missing_request_limit:
        description = (
            f'{len(missing_request_limit)} CPU/memory consumer row(s) are missing request or limit context. '
            'Bars are intentionally muted for usage-only rows to avoid misleading risk signals.'
        )
    elif high_usage:
        description = (
            f'{len(high_usage)} CPU/memory consumer row(s) are above the warning threshold. '
            'Open Top Consumers for request, limit, and namespace-level detail.'
        )
    else:
        description = 'Top CPU and memory consumers are within normal range based on available request/limit context.'

    return {
        'title': 'Consumer insights',
        'description': description,
        'items': insight_items[:4],
        'missing_request_limit_count': len(missing_request_limit),
        'high_usage_count': len(high_usage),
    }

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any, Callable

from app.reports.export.xlsx.analytics_schema import (
    AnalyticsChartData,
    AnalyticsChartSeries,
    AnalyticsColumn,
    AnalyticsExportContext,
    AnalyticsMetricSpec,
    AnalyticsMetricValue,
    AnalyticsTableData,
    AnalyticsWorkbookData,
    AnalyticsWorkbookProfile,
)

_GIB = float(1024**3)


def _metric(label: str, *, fmt: str = 'General', unit: str | None = None) -> AnalyticsMetricSpec:
    return AnalyticsMetricSpec(label=label, number_format=fmt, unit=unit)


def _column(
    key: str,
    label: str,
    definition: str,
    *,
    data_type: str = 'text',
    number_format: str | None = None,
    unit: str | None = None,
    width: float = 18.0,
) -> AnalyticsColumn:
    return AnalyticsColumn(
        key=key,
        label=label,
        definition=definition,
        data_type=data_type,  # type: ignore[arg-type]
        number_format=number_format,
        unit=unit,
        width=width,
    )


ANALYTICS_WORKBOOK_PROFILES: dict[str, AnalyticsWorkbookProfile] = {
    'analytics_overview': AnalyticsWorkbookProfile(
        report_type='analytics_overview',
        title='Analytics Overview',
        description='Cross-domain operational analytics posture, trends, alerts, and leading evidence.',
        metric_specs=(
            _metric('CPU Utilization', fmt='0.0"%"'),
            _metric('Memory Utilization', fmt='0.0"%"'),
            _metric('Forecast Peak', fmt='0.0"%"'),
            _metric('Active Alerts', fmt='#,##0'),
        ),
        sheet_names=('Analysis', 'Trends', 'Top Consumers', 'Alerts & Anomalies', 'Recommendations'),
        primary_visual='comparison_bar',
    ),
    'resource_utilization': AnalyticsWorkbookProfile(
        report_type='resource_utilization',
        title='Resource Utilization',
        description='CPU, memory, storage, pod utilization, trends, and leading consumer evidence.',
        metric_specs=(
            _metric('CPU Utilization', fmt='0.0"%"'),
            _metric('Memory Utilization', fmt='0.0"%"'),
            _metric('Storage Utilization', fmt='0.0"%"'),
            _metric('Pod Utilization', fmt='0.0"%"'),
        ),
        sheet_names=('Analysis', 'Trends', 'Top Consumers'),
        primary_visual='line',
    ),
    'capacity_analysis': AnalyticsWorkbookProfile(
        report_type='capacity_analysis',
        title='Capacity Analysis',
        description='Worker capacity, consumption, headroom, allocation, and projected pressure evidence.',
        metric_specs=(
            _metric('CPU Usage', fmt='0.0"%"'),
            _metric('Memory Usage', fmt='0.0"%"'),
            _metric('Pod Usage', fmt='0.0"%"'),
            _metric('Storage Usage', fmt='0.0"%"'),
        ),
        sheet_names=('Analysis', 'Forecast', 'Recommendations'),
        primary_visual='capacity_bar',
    ),
    'storage_analysis': AnalyticsWorkbookProfile(
        report_type='storage_analysis',
        title='Storage Analysis',
        description='Filesystem and persistent storage capacity, usage, free space, lifecycle, and forecast evidence.',
        metric_specs=(
            _metric('PVC Utilization', fmt='0.0"%"'),
            _metric('Persistent Volumes', fmt='#,##0'),
            _metric('Persistent Claims', fmt='#,##0'),
            _metric('Filesystem Records', fmt='#,##0'),
        ),
        sheet_names=('Analysis', 'Breakdown', 'Forecast', 'Recommendations'),
        primary_visual='capacity_bar',
    ),
    'workload_analysis': AnalyticsWorkbookProfile(
        report_type='workload_analysis',
        title='Workload Analysis',
        description='Tenant quota coverage, workload resource mapping, governance findings, and committed recommendations.',
        metric_specs=(
            _metric('Quota Coverage', fmt='0.0"%"'),
            _metric('Near Limit', fmt='#,##0'),
            _metric('Mapped Workloads', fmt='#,##0'),
            _metric('Governance Findings', fmt='#,##0'),
        ),
        sheet_names=('Analysis', 'Breakdown', 'Recommendations'),
        primary_visual='doughnut',
    ),
    'resource_forecast': AnalyticsWorkbookProfile(
        report_type='resource_forecast',
        title='Resource Forecast',
        description='Committed historical and forecast evidence for CPU, memory, storage, and pod growth.',
        metric_specs=(
            _metric('CPU Projection', fmt='0.0"%"'),
            _metric('Memory Projection', fmt='0.0"%"'),
            _metric('Pod Projection', fmt='0.0"%"'),
            _metric('Storage Projection', fmt='0.0"%"'),
        ),
        sheet_names=('Analysis', 'Trends', 'Recommendations'),
        primary_visual='line',
    ),
    'top_consumers': AnalyticsWorkbookProfile(
        report_type='top_consumers',
        title='Top Consumers',
        description='Ranked namespace, workload, and pod resource-consumption evidence for the selected scope.',
        metric_specs=(
            _metric('Displayed Consumers', fmt='#,##0'),
            _metric('CPU Consumers', fmt='#,##0'),
            _metric('Memory Consumers', fmt='#,##0'),
            _metric('Namespaces', fmt='#,##0'),
        ),
        sheet_names=('Top Consumers',),
        primary_visual='ranked_bar',
    ),
    'alerts_anomalies': AnalyticsWorkbookProfile(
        report_type='alerts_anomalies',
        title='Alerts & Anomalies',
        description='Committed alert severity, anomaly evidence, ownership context, and response recommendations.',
        metric_specs=(
            _metric('Active Alerts', fmt='#,##0'),
            _metric('Critical Alerts', fmt='#,##0'),
            _metric('Warning Alerts', fmt='#,##0'),
            _metric('Anomalies', fmt='#,##0'),
        ),
        sheet_names=('Analysis', 'Alerts & Anomalies', 'Recommendations'),
        primary_visual='doughnut',
    ),
    'object_storage_analysis': AnalyticsWorkbookProfile(
        report_type='object_storage_analysis',
        title='Object Storage Analysis',
        description='Capacity, usage, performance, growth, consumer concentration, and alert evidence for one Object Storage system.',
        metric_specs=(
            _metric('Capacity'),
            _metric('Usage'),
            _metric('Headroom'),
            _metric('Utilization'),
        ),
        sheet_names=('Analysis', 'Top Consumers', 'Trends', 'Alerts & Anomalies'),
        primary_visual='ranked_bar',
    ),
}

ANALYTICS_XLSX_REPORT_TYPES = frozenset(ANALYTICS_WORKBOOK_PROFILES)


def _validate_profiles() -> None:
    visual_types = {'line', 'ranked_bar', 'doughnut', 'capacity_bar', 'comparison_bar'}
    for report_type, profile in ANALYTICS_WORKBOOK_PROFILES.items():
        if profile.report_type != report_type:
            raise ValueError(f'Analytics XLSX profile key {report_type!r} does not match profile report type.')
        if len(profile.metric_specs) != 4:
            raise ValueError(f'Analytics XLSX profile {report_type!r} must declare exactly four overview metrics.')
        if not profile.sheet_names:
            raise ValueError(f'Analytics XLSX profile {report_type!r} must declare category-owned sheet names.')
        if profile.primary_visual not in visual_types:
            raise ValueError(f'Analytics XLSX profile {report_type!r} has unsupported primary visual.')
        if len(set(profile.sheet_names)) != len(profile.sheet_names):
            raise ValueError(f'Analytics XLSX profile {report_type!r} declares duplicate sheet names.')


_validate_profiles()


def get_analytics_workbook_profile(report_type: str) -> AnalyticsWorkbookProfile:
    try:
        return ANALYTICS_WORKBOOK_PROFILES[report_type]
    except KeyError as exc:
        raise ValueError(f'Unsupported Analytics Excel report type: {report_type}.') from exc


_Preparer = Callable[[Mapping[str, Any], AnalyticsExportContext, AnalyticsWorkbookProfile], AnalyticsWorkbookData]


def prepare_analytics_workbook_data(
    report_type: str,
    payload: Mapping[str, Any],
    context: AnalyticsExportContext,
) -> AnalyticsWorkbookData:
    if context.report_type != report_type:
        raise ValueError('Analytics export context does not match the requested report type.')
    profile = get_analytics_workbook_profile(report_type)
    preparer = _PREPARERS[report_type]
    return preparer(payload, context, profile)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> list[Mapping[str, Any]]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [item for item in value if isinstance(item, Mapping)]
    return []


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)):
        return float(value)
    if value is None:
        return None
    rendered = str(value).strip().replace(',', '')
    if not rendered or rendered.casefold() in {'n/a', 'na', 'not available', 'unknown', '-'}:
        return None
    token = rendered.split()[0].rstrip('%')
    try:
        return float(token)
    except ValueError:
        return None


def _int(value: Any) -> int:
    number = _number(value)
    return int(number or 0)


def _text(value: Any, fallback: str = 'Not Available') -> str:
    if value is None or value == '':
        return fallback
    return str(value)


def _first(mapping: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value not in (None, ''):
            return value
    return default


def _percent_from_resource(resource: Mapping[str, Any]) -> float | None:
    direct = _first(resource, 'utilization_percent', 'used_percent', 'usage_percent', 'percent')
    direct_number = _number(direct)
    if direct_number is not None:
        return direct_number
    headroom = _number(resource.get('headroom'))
    if headroom is not None and 0 <= headroom <= 100:
        return 100.0 - headroom
    used = _number(resource.get('used'))
    capacity = _number(resource.get('capacity'))
    if used is not None and capacity and capacity > 0:
        return used / capacity * 100.0
    return None


def _metric_value(spec: AnalyticsMetricSpec, value: Any, *, note: str | None = None) -> AnalyticsMetricValue:
    return AnalyticsMetricValue(
        label=spec.label,
        value=value if value not in (None, '') else 'Not Available',
        number_format=spec.number_format,
        unit=spec.unit,
        note=note,
    )


def _table(
    sheet_name: str,
    title: str,
    description: str,
    columns: tuple[AnalyticsColumn, ...],
    rows: Iterable[Mapping[str, Any]],
) -> AnalyticsTableData:
    return AnalyticsTableData(
        sheet_name=sheet_name,
        title=title,
        description=description,
        columns=columns,
        rows=tuple(dict(row) for row in rows),
    )


_RESOURCE_COLUMNS = (
    _column('resource', 'Resource', 'Resource dimension represented by the committed analytics evidence.', width=24),
    _column('current_percent', 'Current %', 'Current committed utilization or pressure percentage.', data_type='percent', number_format='0.0"%"', width=16),
    _column('headroom_percent', 'Headroom %', 'Remaining capacity percentage when available.', data_type='percent', number_format='0.0"%"', width=16),
    _column('status', 'Status', 'Committed status or posture label.', width=22),
)

_TREND_COLUMNS = (
    _column('observation', 'Observation', 'Committed series position in source order.', data_type='integer', number_format='#,##0', width=14),
    _column('timestamp', 'Timestamp', 'Committed timestamp when supplied by the analytics source.', width=22),
    _column('cpu_percent', 'CPU %', 'CPU utilization at this observation.', data_type='percent', number_format='0.0"%"', width=14),
    _column('memory_percent', 'Memory %', 'Memory utilization at this observation.', data_type='percent', number_format='0.0"%"', width=14),
    _column('pods_percent', 'Pods %', 'Pod utilization at this observation.', data_type='percent', number_format='0.0"%"', width=14),
    _column('storage_percent', 'Storage %', 'Storage utilization at this observation.', data_type='percent', number_format='0.0"%"', width=14),
)

_FORECAST_POSTURE_COLUMNS = (
    _column('resource', 'Resource', 'Forecast resource dimension.', width=20),
    _column('current_percent', 'Current %', 'Latest committed observed utilization.', data_type='percent', number_format='0.0"%"', width=16),
    _column('projected_percent', 'Projected %', 'Committed projected utilization at the configured forecast horizon.', data_type='percent', number_format='0.0"%"', width=16),
    _column('change_pp', 'Change (pp)', 'Projected change from the latest observation in percentage points.', data_type='number', number_format='+0.0;-0.0;0.0', unit='pp', width=16),
    _column('trend', 'Trend', 'Committed forecast direction.', width=18),
    _column('confidence', 'Confidence', 'Committed forecast confidence label.', width=18),
)

_RECOMMENDATION_COLUMNS = (
    _column('priority', 'Priority', 'Committed recommendation priority.', width=16),
    _column('recommendation', 'Recommendation', 'Committed recommendation title or action.', width=38),
    _column('evidence', 'Evidence', 'Evidence or description supplied by the analytics source.', width=54),
    _column('affected_scope', 'Affected Scope', 'Affected resource or scope when supplied.', width=34),
    _column('source', 'Source Rule', 'Source rule or analytics domain that produced the recommendation.', width=24),
)


def _recommendation_rows(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    candidates: list[Any] = [
        payload.get('actionable_recommendations'),
        payload.get('recommendations'),
        payload.get('recommendation_cards'),
        _mapping(payload.get('forecast_payload')).get('actionable_recommendations'),
        _mapping(payload.get('forecast_payload')).get('recommendation_cards'),
    ]
    rows: list[dict[str, Any]] = []
    for candidate in candidates:
        if isinstance(candidate, Mapping):
            candidate = candidate.get('items') or candidate.get('rows') or []
        for item in _sequence(candidate):
            title = _first(item, 'title', 'recommendation', 'label')
            if not title:
                continue
            rows.append(
                {
                    'priority': _first(item, 'priority', 'severity', default='Not Available'),
                    'recommendation': title,
                    'evidence': _first(item, 'evidence', 'description', 'detail', default='Not Available'),
                    'affected_scope': _first(item, 'affected_scope', 'resource', 'scope', default='Not Available'),
                    'source': _first(item, 'source_rule', 'source', 'rule', default='Not Available'),
                }
            )
        if rows:
            break
    return rows


def _append_recommendations(
    tables: list[AnalyticsTableData],
    payload: Mapping[str, Any],
) -> None:
    rows = _recommendation_rows(payload)
    if rows:
        tables.append(
            _table(
                'Recommendations',
                'Committed Recommendations',
                'Recommendations already owned by KAORI analytics; the XLSX renderer does not create new actions.',
                _RECOMMENDATION_COLUMNS,
                rows,
            )
        )


def _source_evidence_table(payload: Mapping[str, Any]) -> AnalyticsTableData | None:
    rows = _sequence(payload.get('source_evidence'))
    if not rows:
        return None
    normalized = [
        {
            'source': _first(row, 'source', 'label', default='Unknown Source'),
            'freshness': _first(row, 'freshness', 'status', default='Not Available'),
            'last_collected': _first(row, 'last_collected', 'generated_at', default='Not Available'),
        }
        for row in rows
    ]
    return _table(
        'Raw Data',
        'Source Evidence',
        'Evidence boundary supplied by the canonical analytics payload.',
        (
            _column('source', 'Source', 'Canonical analytics evidence source.', width=38),
            _column('freshness', 'Freshness', 'Freshness or readiness evidence.', width=22),
            _column('last_collected', 'Last Collected', 'Collection timestamp or evidence boundary.', width=24),
        ),
        normalized,
    )


def _leading_percent_readout(metrics: Sequence[AnalyticsMetricValue], noun: str) -> str:
    numeric = [(metric.label, _number(metric.value)) for metric in metrics]
    available = [(label, value) for label, value in numeric if value is not None]
    if not available:
        return f'No committed {noun} percentage evidence is available for the selected reporting boundary.'
    label, value = max(available, key=lambda item: item[1])
    return f'{label} is the leading committed {noun} signal at {value:.1f}%. Review the supporting evidence before taking action.'


def _prepare_resource_utilization(
    payload: Mapping[str, Any],
    context: AnalyticsExportContext,
    profile: AnalyticsWorkbookProfile,
) -> AnalyticsWorkbookData:
    summary = _mapping(payload.get('summary'))
    risk = _mapping(payload.get('risk_assessment'))
    values = (
        _number(summary.get('cpu_utilization')),
        _number(summary.get('memory_utilization')),
        _number(summary.get('storage_utilization')),
        _number(summary.get('pod_utilization')),
    )
    metrics = tuple(_metric_value(spec, value) for spec, value in zip(profile.metric_specs, values, strict=True))
    resources = ('CPU', 'Memory', 'Storage', 'Pods')
    resource_keys = ('cpu', 'memory', 'storage', 'pods')
    analysis_rows = [
        {
            'resource': label,
            'current_percent': value,
            'headroom_percent': (100.0 - value) if value is not None else None,
            'status': _first(_mapping(risk.get(key if key != 'pods' else 'pods')), 'status', 'label', default='Not Available'),
        }
        for label, key, value in zip(resources, resource_keys, values, strict=True)
    ]
    tables: list[AnalyticsTableData] = [
        _table('Analysis', 'Resource Utilization Analysis', 'Current committed utilization and headroom by resource.', _RESOURCE_COLUMNS, analysis_rows)
    ]

    trends = _mapping(payload.get('trends'))
    series_by_key = {key: _sequence(trends.get(key)) for key in ('cpu', 'memory', 'pods', 'storage')}
    trend_count = max((len(rows) for rows in series_by_key.values()), default=0)
    trend_rows: list[dict[str, Any]] = []
    for index in range(trend_count):
        row: dict[str, Any] = {'observation': index + 1, 'timestamp': ''}
        for key in ('cpu', 'memory', 'pods', 'storage'):
            item = series_by_key[key][index] if index < len(series_by_key[key]) else {}
            row[f'{key}_percent'] = _number(_first(item, 'percent', 'value'))
            if not row['timestamp']:
                row['timestamp'] = _first(item, 'timestamp', 'time', 'observed_at', default='')
        trend_rows.append(row)
    if trend_rows:
        tables.append(_table('Trends', 'Utilization Trends', 'Committed utilization series in source order.', _TREND_COLUMNS, trend_rows))

    consumer_rows: list[dict[str, Any]] = []
    for resource, key, unit in (
        ('CPU', 'top_cpu_consumers', 'cores'),
        ('Memory', 'top_memory_consumers', 'GiB'),
    ):
        for item in _sequence(payload.get(key)):
            consumer_rows.append(
                {
                    'resource': resource,
                    'namespace': _first(item, 'namespace', default='Not Available'),
                    'consumer': _first(item, 'pod', 'name', 'workload', default='Not Available'),
                    'value': _number(_first(item, 'value', 'current_usage', 'percent')),
                    'unit': _first(item, 'unit', default=unit),
                }
            )
    if consumer_rows:
        tables.append(
            _table(
                'Top Consumers',
                'Leading Resource Consumers',
                'Committed leading consumer evidence. CPU and memory values retain their source units.',
                (
                    _column('resource', 'Resource', 'Resource signal used for ranking.', width=14),
                    _column('namespace', 'Namespace', 'Kubernetes namespace.', width=28),
                    _column('consumer', 'Consumer', 'Pod, workload, or resource identity.', width=44),
                    _column('value', 'Value', 'Committed resource value.', data_type='number', number_format='#,##0.00', width=16),
                    _column('unit', 'Unit', 'Unit supplied by the source evidence.', width=12),
                ),
                consumer_rows,
            )
        )
    evidence = _source_evidence_table(payload)
    if evidence is not None:
        tables.append(evidence)

    chart = None
    if trend_rows:
        chart = AnalyticsChartData(
            title='Resource Utilization Trend',
            visual_type='line',
            source_sheet='Trends',
            rows=tuple(trend_rows),
            category_key='observation',
            series=tuple(
                AnalyticsChartSeries(key=f'{key}_percent', label=label, number_format='0.0', unit='%')
                for key, label in (('cpu', 'CPU'), ('memory', 'Memory'), ('pods', 'Pods'), ('storage', 'Storage'))
            ),
            value_axis_title='Utilization (%)',
        )
    return AnalyticsWorkbookData(profile, context, metrics, _leading_percent_readout(metrics, 'utilization'), tuple(tables), chart)


def _capacity_rows(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    summary = _mapping(payload.get('capacity_summary'))
    rows: list[dict[str, Any]] = []
    for key, label in (('cpu', 'CPU'), ('memory', 'Memory'), ('pods', 'Pods'), ('storage', 'Storage')):
        item = _mapping(summary.get(key))
        percent = _percent_from_resource(item)
        headroom = _number(item.get('headroom'))
        if headroom is None and percent is not None:
            headroom = max(0.0, 100.0 - percent)
        rows.append(
            {
                'resource': label,
                'current_percent': percent,
                'headroom_percent': headroom,
                'status': _first(_mapping(item.get('status')), 'label', default=_first(item, 'status_label', default='Not Available')),
            }
        )
    return rows


def _prepare_capacity(
    payload: Mapping[str, Any], context: AnalyticsExportContext, profile: AnalyticsWorkbookProfile
) -> AnalyticsWorkbookData:
    rows = _capacity_rows(payload)
    metrics = tuple(_metric_value(spec, row['current_percent']) for spec, row in zip(profile.metric_specs, rows, strict=True))
    tables: list[AnalyticsTableData] = [
        _table('Analysis', 'Capacity & Headroom', 'Current committed capacity pressure and remaining headroom by resource.', _RESOURCE_COLUMNS, rows)
    ]
    forecast_rows: list[dict[str, Any]] = []
    for item in _sequence(_mapping(payload.get('forecast_payload')).get('items')):
        key = _text(item.get('key'), 'Unknown').title()
        forecast_rows.append(
            {
                'resource': key,
                'current_percent': _number(_first(item, 'current_percent', 'historical_percent', 'current')),
                'projected_percent': _number(_first(item, 'projected_percent', 'forecast_percent')),
                'signal_quality': _first(item, 'signal_quality', 'confidence', default='Not Available'),
                'threshold_eta': _first(_mapping(item.get('warning_eta')), 'label', default=_first(item, 'threshold_eta', default='Not Available')),
            }
        )
    if forecast_rows:
        tables.append(
            _table(
                'Forecast',
                'Capacity Forecast',
                'Committed projections supplied by the analytics worker. Excel does not calculate forecasts.',
                (
                    _column('resource', 'Resource', 'Forecast resource.', width=18),
                    _column('current_percent', 'Current %', 'Current committed percentage.', data_type='percent', number_format='0.0"%"', width=15),
                    _column('projected_percent', 'Projected %', 'Committed projected percentage.', data_type='percent', number_format='0.0"%"', width=15),
                    _column('signal_quality', 'Signal Quality', 'Committed forecast evidence quality.', width=18),
                    _column('threshold_eta', 'Threshold ETA', 'Committed threshold timing when available.', width=20),
                ),
                forecast_rows,
            )
        )
    _append_recommendations(tables, payload)
    chart_rows = tuple({'category': row['resource'], 'value': row['current_percent']} for row in rows if row['current_percent'] is not None)
    chart = AnalyticsChartData(
        title='Capacity Utilization by Resource',
        visual_type='capacity_bar',
        source_sheet='Analysis',
        rows=chart_rows,
        series=(AnalyticsChartSeries('value', 'Utilization', '0.0', '%'),),
        value_axis_title='Utilization (%)',
    ) if chart_rows else None
    return AnalyticsWorkbookData(profile, context, metrics, _leading_percent_readout(metrics, 'capacity'), tuple(tables), chart)


def _prepare_storage(
    payload: Mapping[str, Any], context: AnalyticsExportContext, profile: AnalyticsWorkbookProfile
) -> AnalyticsWorkbookData:
    storage = _mapping(payload.get('storage_summary'))
    persistent = _mapping(storage.get('persistent_storage'))
    pv = _mapping(persistent.get('pv'))
    pvc = _mapping(persistent.get('pvc'))
    filesystem = _mapping(storage.get('node_filesystem'))
    filesystem_rows = _sequence(filesystem.get('all_rows') or filesystem.get('rows'))
    pvc_util = _number(_first(pvc, 'used_percent', 'utilization_percent'))
    values = (pvc_util, _int(pv.get('count')), _int(pvc.get('count')), len(filesystem_rows))
    metrics = tuple(_metric_value(spec, value) for spec, value in zip(profile.metric_specs, values, strict=True))
    analysis_rows = [
        {'metric': 'PV Capacity', 'value': _first(pv, 'capacity', default='Not Available'), 'status': 'Committed' if pv else 'Not Available'},
        {'metric': 'Observed Claim Usage', 'value': _first(pv, 'observed_claim_usage', default='Not Available'), 'status': 'Committed' if pv else 'Not Available'},
        {'metric': 'PVC Used', 'value': _first(pvc, 'used', default='Not Available'), 'status': 'Committed' if pvc else 'Not Available'},
        {'metric': 'PVC Free', 'value': _first(pvc, 'free', default='Not Available'), 'status': 'Committed' if pvc else 'Not Available'},
    ]
    tables: list[AnalyticsTableData] = [
        _table(
            'Analysis',
            'Storage Capacity Summary',
            'Committed persistent-storage capacity and usage evidence.',
            (
                _column('metric', 'Metric', 'Storage evidence metric.', width=30),
                _column('value', 'Value', 'Committed display value from analytics.', width=24),
                _column('status', 'Evidence State', 'Availability of the evidence.', width=20),
            ),
            analysis_rows,
        )
    ]
    breakdown_rows: list[dict[str, Any]] = []
    for kind, raw_rows in (
        ('PV', _sequence(persistent.get('pv_all_rows') or persistent.get('pv_rows'))),
        ('PVC', _sequence(persistent.get('pvc_all_rows') or persistent.get('pvc_rows'))),
        ('Filesystem', filesystem_rows),
    ):
        for item in raw_rows:
            identity = _mapping(item.get('identity'))
            breakdown_rows.append(
                {
                    'type': kind,
                    'identity': _first(identity, 'primary', default=_first(item, 'name', 'persistent_volume', 'persistent_volume_claim', 'mountpoint', default='Not Available')),
                    'namespace': _first(item, 'namespace', default='Cluster'),
                    'capacity': _first(item, 'capacity_display', 'capacity', 'size', default='Not Available'),
                    'used': _first(item, 'used_display', 'used', 'usage_display', default='Not Available'),
                    'free': _first(item, 'free_display', 'free', 'available_display', default='Not Available'),
                    'utilization_percent': _number(_first(item, 'used_percent', 'utilization_percent', 'percent')),
                    'status': _first(_mapping(item.get('risk')), 'label', default=_first(item, 'status', 'phase', default='Not Available')),
                }
            )
    if breakdown_rows:
        tables.append(
            _table(
                'Breakdown',
                'Storage Evidence Breakdown',
                'Filesystem, PV, and PVC evidence normalized for review.',
                (
                    _column('type', 'Type', 'Storage evidence type.', width=14),
                    _column('identity', 'Identity', 'Storage resource identity.', width=40),
                    _column('namespace', 'Namespace', 'Namespace or cluster scope.', width=26),
                    _column('capacity', 'Capacity', 'Committed capacity.', width=18),
                    _column('used', 'Used', 'Committed used capacity.', width=18),
                    _column('free', 'Free', 'Committed free capacity.', width=18),
                    _column('utilization_percent', 'Utilization %', 'Committed utilization percentage.', data_type='percent', number_format='0.0"%"', width=16),
                    _column('status', 'Status', 'Lifecycle or risk label.', width=18),
                ),
                breakdown_rows,
            )
        )
    _append_recommendations(tables, payload)
    chart_rows: tuple[Mapping[str, Any], ...] = ()
    free_percent = _number(pvc.get('free_percent'))
    if pvc_util is not None:
        if free_percent is None:
            free_percent = max(0.0, 100.0 - pvc_util)
        chart_rows = ({'category': 'PVC Used', 'value': pvc_util}, {'category': 'PVC Free', 'value': free_percent})
    chart = AnalyticsChartData(
        title='Persistent Claim Capacity Posture',
        visual_type='capacity_bar',
        source_sheet='Analysis',
        rows=chart_rows,
        series=(AnalyticsChartSeries('value', 'Percent', '0.0', '%'),),
        value_axis_title='Percent',
    ) if chart_rows else None
    return AnalyticsWorkbookData(profile, context, metrics, _leading_percent_readout((metrics[0],), 'storage'), tuple(tables), chart)


def _prepare_workload(
    payload: Mapping[str, Any], context: AnalyticsExportContext, profile: AnalyticsWorkbookProfile
) -> AnalyticsWorkbookData:
    quota = _mapping(payload.get('tenant_quota_summary'))
    quota_rows = _sequence(payload.get('tenant_quota_rows') or quota.get('rows'))
    mapping_rows_raw = _sequence(payload.get('workload_mapping_rows') or _mapping(payload.get('workload_mapping_payload')).get('rows'))
    findings = _sequence(payload.get('governance_findings'))
    total = _int(quota.get('scope_total')) or len(quota_rows)
    covered = _int(quota.get('scope_covered'))
    coverage = (covered / total * 100.0) if total else None
    near_limit = _int(_first(quota, 'scope_near_limit_count', 'near_limit_count', default=0))
    values = (coverage, near_limit, len(mapping_rows_raw), len(findings))
    metrics = tuple(_metric_value(spec, value) for spec, value in zip(profile.metric_specs, values, strict=True))
    normalized_quota = [
        {
            'namespace': _first(item, 'namespace', 'name', default='Not Available'),
            'quota_status': _first(_mapping(item.get('quota_status')), 'label', default=_first(item, 'status', default='Not Available')),
            'cpu': _first(item, 'cpu', 'cpu_display', default='Not Available'),
            'memory': _first(item, 'memory', 'memory_display', default='Not Available'),
            'pods': _first(item, 'pods', 'pod_display', default='Not Available'),
        }
        for item in quota_rows
    ]
    tables: list[AnalyticsTableData] = []
    if normalized_quota:
        tables.append(
            _table(
                'Analysis',
                'Tenant Quota Analysis',
                'Committed ResourceQuota coverage and posture by namespace.',
                (
                    _column('namespace', 'Namespace', 'Namespace identity.', width=30),
                    _column('quota_status', 'Quota Status', 'Committed quota coverage status.', width=20),
                    _column('cpu', 'CPU', 'CPU quota evidence.', width=20),
                    _column('memory', 'Memory', 'Memory quota evidence.', width=20),
                    _column('pods', 'Pods', 'Pod quota evidence.', width=18),
                ),
                normalized_quota,
            )
        )
    normalized_mapping = [
        {
            'namespace': _first(item, 'namespace', default='Not Available'),
            'workload': _first(_mapping(item.get('identity')), 'primary', default=_first(item, 'workload', 'name', default='Not Available')),
            'kind': _first(item, 'kind', 'workload_kind', default='Not Available'),
            'requests': _first(item, 'requests', 'request_display', default='Not Available'),
            'limits': _first(item, 'limits', 'limit_display', default='Not Available'),
            'status': _first(_mapping(item.get('risk')), 'label', default=_first(item, 'status', 'qos_class', default='Not Available')),
        }
        for item in mapping_rows_raw
    ]
    if normalized_mapping:
        tables.append(
            _table(
                'Breakdown',
                'Workload Resource Mapping',
                'Committed workload requests, limits, and governance posture.',
                (
                    _column('namespace', 'Namespace', 'Namespace identity.', width=28),
                    _column('workload', 'Workload', 'Workload identity.', width=42),
                    _column('kind', 'Kind', 'Kubernetes workload kind.', width=18),
                    _column('requests', 'Requests', 'Committed request evidence.', width=24),
                    _column('limits', 'Limits', 'Committed limit evidence.', width=24),
                    _column('status', 'Status', 'Governance or QoS evidence.', width=20),
                ),
                normalized_mapping,
            )
        )
    _append_recommendations(tables, payload)
    chart_rows: tuple[Mapping[str, Any], ...] = ()
    if total:
        chart_rows = (
            {'category': 'Quota Covered', 'value': covered},
            {'category': 'Quota Not Covered', 'value': max(total - covered, 0)},
        )
    chart = AnalyticsChartData(
        title='Namespace Quota Coverage',
        visual_type='doughnut',
        source_sheet='Analysis' if normalized_quota else 'Overview',
        rows=chart_rows,
        series=(AnalyticsChartSeries('value', 'Namespaces', '#,##0'),),
    ) if chart_rows else None
    if coverage is None:
        readout = 'No committed tenant quota coverage denominator is available for the selected reporting boundary.'
    else:
        readout = f'{coverage:.1f}% of {total:,} namespace quota records are covered in the committed analytics evidence.'
    return AnalyticsWorkbookData(profile, context, metrics, readout, tuple(tables), chart)


def _forecast_item_percent(item: Mapping[str, Any]) -> float | None:
    return _number(_first(item, 'projected_percent', 'forecast_percent', 'projected'))


def _prepare_forecast(
    payload: Mapping[str, Any], context: AnalyticsExportContext, profile: AnalyticsWorkbookProfile
) -> AnalyticsWorkbookData:
    forecast = _mapping(payload.get('forecast_payload'))
    items = _sequence(forecast.get('items'))
    by_key = {str(item.get('key') or '').casefold(): item for item in items}
    values = tuple(_forecast_item_percent(_mapping(by_key.get(key))) for key in ('cpu', 'memory', 'pods', 'storage'))
    metrics = tuple(_metric_value(spec, value) for spec, value in zip(profile.metric_specs, values, strict=True))
    analysis_rows = [
        {
            'resource': key.title(),
            'current_percent': _number(_first(item, 'current_percent', 'historical_percent', 'current')),
            'projected_percent': _forecast_item_percent(item),
            'signal_quality': _first(item, 'signal_quality', 'confidence', default='Not Available'),
            'threshold_eta': _first(_mapping(item.get('warning_eta')), 'label', default=_first(item, 'threshold_eta', default='Not Available')),
        }
        for key, item in by_key.items()
    ]
    tables: list[AnalyticsTableData] = []
    if analysis_rows:
        tables.append(
            _table(
                'Analysis',
                'Forecast Summary',
                'Committed current and projected resource signals.',
                (
                    _column('resource', 'Resource', 'Forecast resource.', width=18),
                    _column('current_percent', 'Current %', 'Current committed percentage.', data_type='percent', number_format='0.0"%"', width=15),
                    _column('projected_percent', 'Projected %', 'Committed projected percentage.', data_type='percent', number_format='0.0"%"', width=15),
                    _column('signal_quality', 'Signal Quality', 'Committed signal quality.', width=18),
                    _column('threshold_eta', 'Threshold ETA', 'Committed threshold timing.', width=20),
                ),
                analysis_rows,
            )
        )

    preferred_key = next((key for key in ('memory', 'cpu', 'pods', 'storage') if key in by_key), None)
    trend_rows: list[dict[str, Any]] = []
    if preferred_key:
        item = _mapping(by_key[preferred_key])
        historical = _sequence(item.get('historical_points'))
        projected = _sequence(item.get('forecast_points'))
        count = max(len(historical), len(projected))
        for index in range(count):
            hist = historical[index] if index < len(historical) else {}
            proj = projected[index] if index < len(projected) else {}
            trend_rows.append(
                {
                    'observation': index + 1,
                    'historical_percent': _number(_first(hist, 'percent', 'value')),
                    'forecast_percent': _number(_first(proj, 'percent', 'value')),
                    'resource': preferred_key.title(),
                }
            )
    if trend_rows:
        tables.append(
            _table(
                'Trends',
                f'{preferred_key.title()} Forecast Trend',
                'Committed historical and forecast points in source order.',
                (
                    _column('observation', 'Observation', 'Source-order point.', data_type='integer', number_format='#,##0', width=14),
                    _column('resource', 'Resource', 'Forecast resource.', width=16),
                    _column('historical_percent', 'Historical %', 'Committed historical percentage.', data_type='percent', number_format='0.0"%"', width=16),
                    _column('forecast_percent', 'Forecast %', 'Committed forecast percentage.', data_type='percent', number_format='0.0"%"', width=16),
                ),
                trend_rows,
            )
        )
    _append_recommendations(tables, payload)
    chart = None
    if trend_rows:
        chart = AnalyticsChartData(
            title=f'{preferred_key.title()} Historical & Forecast Direction',
            visual_type='line',
            source_sheet='Trends',
            rows=tuple(trend_rows),
            category_key='observation',
            series=(
                AnalyticsChartSeries('historical_percent', 'Historical', '0.0', '%'),
                AnalyticsChartSeries('forecast_percent', 'Forecast', '0.0', '%'),
            ),
            value_axis_title='Percent',
        )
    return AnalyticsWorkbookData(profile, context, metrics, _leading_percent_readout(metrics, 'forecast'), tuple(tables), chart)


def _consumer_identity(item: Mapping[str, Any]) -> str:
    return _text(_first(_mapping(item.get('identity')), 'primary', default=_first(item, 'name', 'pod', 'workload')))


def _prepare_top_consumers(
    payload: Mapping[str, Any], context: AnalyticsExportContext, profile: AnalyticsWorkbookProfile
) -> AnalyticsWorkbookData:
    consumer = _mapping(payload.get('consumer_payload'))
    source_rows = _sequence(consumer.get('all_rows') or consumer.get('rows'))
    rows: list[dict[str, Any]] = []
    for item in source_rows:
        resource = _text(_first(item, 'resource_type', 'resource', 'metric'), 'Unknown').title()
        value = _number(_first(item, 'current_usage', 'value', 'percent'))
        rows.append(
            {
                'resource': resource,
                'namespace': _first(item, 'namespace', default='Not Available'),
                'consumer': _consumer_identity(item),
                'value': value,
                'display_value': _first(item, 'current_display', 'display_value', default=value),
                'unit': _first(item, 'unit', default='Not Available'),
                'status': _first(_mapping(item.get('risk')), 'label', default=_first(item, 'status', default='Not Available')),
            }
        )
    cpu_count = sum(1 for row in rows if str(row['resource']).casefold() == 'cpu')
    memory_count = sum(1 for row in rows if str(row['resource']).casefold() == 'memory')
    namespaces = len({_text(row['namespace']) for row in rows if row['namespace'] not in (None, '', 'Not Available')})
    values = (len(rows), cpu_count, memory_count, namespaces)
    metrics = tuple(_metric_value(spec, value) for spec, value in zip(profile.metric_specs, values, strict=True))
    tables: list[AnalyticsTableData] = []
    if rows:
        tables.append(
            _table(
                'Top Consumers',
                'Top Consumers',
                'Committed consumer ranking evidence; resource units are preserved and not mixed in one chart.',
                (
                    _column('resource', 'Resource', 'Resource signal.', width=14),
                    _column('namespace', 'Namespace', 'Namespace identity.', width=28),
                    _column('consumer', 'Consumer', 'Pod, workload, or resource identity.', width=44),
                    _column('value', 'Numeric Value', 'Committed numeric value.', data_type='number', number_format='#,##0.00', width=16),
                    _column('display_value', 'Display Value', 'Committed formatted value.', width=18),
                    _column('unit', 'Unit', 'Resource-specific unit.', width=12),
                    _column('status', 'Status', 'Committed risk or review state.', width=18),
                ),
                rows,
            )
        )
    preferred = next((resource for resource in ('Memory', 'CPU') if any(row['resource'] == resource for row in rows)), None)
    if preferred is None:
        preferred = next((str(row['resource']) for row in rows), None)
    ranked = [row for row in rows if row['resource'] == preferred and row['value'] is not None]
    ranked.sort(key=lambda row: float(row['value']), reverse=True)
    chart_rows = tuple({'category': row['consumer'], 'value': row['value']} for row in ranked[:8])
    unit = _text(ranked[0].get('unit'), '') if ranked else ''
    chart = AnalyticsChartData(
        title=f'Top {preferred} Consumers',
        visual_type='ranked_bar',
        source_sheet='Top Consumers',
        rows=chart_rows,
        series=(AnalyticsChartSeries('value', preferred or 'Value', '#,##0.00', unit or None),),
        value_axis_title=f'{preferred} ({unit})' if unit and unit != 'Not Available' else preferred,
    ) if chart_rows else None
    if ranked:
        readout = f'{ranked[0]["consumer"]} is the leading displayed {preferred} consumer at {_text(ranked[0]["display_value"], str(ranked[0]["value"]))}.'
    else:
        readout = 'No committed consumer ranking evidence is available for the selected reporting boundary.'
    return AnalyticsWorkbookData(profile, context, metrics, readout, tuple(tables), chart)


def _prepare_alerts(
    payload: Mapping[str, Any], context: AnalyticsExportContext, profile: AnalyticsWorkbookProfile
) -> AnalyticsWorkbookData:
    summary = _mapping(payload.get('summary'))
    alerts = _sequence(payload.get('alerts'))
    anomalies = _sequence(payload.get('anomalies'))
    active = _int(summary.get('active_alerts')) or len(alerts)
    critical = _int(summary.get('critical_alerts'))
    warning = _int(summary.get('warning_alerts'))
    info = _int(summary.get('info_alerts'))
    anomaly_count = _int(_first(summary, 'detected_anomalies', 'anomalies', default=len(anomalies)))
    if critical == 0:
        critical = sum(1 for row in alerts if _text(row.get('severity'), '').casefold() == 'critical')
    if warning == 0:
        warning = sum(1 for row in alerts if _text(row.get('severity'), '').casefold() == 'warning')
    if info == 0:
        info = sum(1 for row in alerts if _text(row.get('severity'), '').casefold() == 'info')
    values = (active, critical, warning, anomaly_count)
    metrics = tuple(_metric_value(spec, value) for spec, value in zip(profile.metric_specs, values, strict=True))
    source_status = _mapping(payload.get('source_status'))
    analysis_rows = [
        {'signal': 'Alert Source', 'value': _first(source_status, 'label', 'status', default='Not Available')},
        {'signal': 'Anomaly Source', 'value': _first(_mapping(payload.get('anomaly_source_status')), 'label', 'status', default='Not Available')},
        {'signal': 'Committed Evidence', 'value': 'Available' if payload.get('committed_evidence_available', True) else 'Unavailable'},
    ]
    tables: list[AnalyticsTableData] = [
        _table(
            'Analysis',
            'Alert Evidence Sources',
            'Source and evidence readiness for the committed alert/anomaly payload.',
            (
                _column('signal', 'Signal', 'Evidence source signal.', width=28),
                _column('value', 'Value', 'Committed evidence state.', width=40),
            ),
            analysis_rows,
        )
    ]
    event_rows: list[dict[str, Any]] = []
    for kind, source in (('Alert', alerts), ('Anomaly', anomalies)):
        for item in source:
            event_rows.append(
                {
                    'type': kind,
                    'name': _first(item, 'name', 'alertname', 'title', 'label', default='Not Available'),
                    'severity': _first(item, 'severity', default='Unknown'),
                    'status': _first(item, 'status', 'state', default='Not Available'),
                    'namespace': _first(item, 'namespace', default='All Namespaces'),
                    'resource': _first(item, 'resource', 'pod', 'workload', default='Not Available'),
                    'started_at': _first(item, 'started_at', 'starts_at', 'timestamp', default='Not Available'),
                }
            )
    if event_rows:
        tables.append(
            _table(
                'Alerts & Anomalies',
                'Alert & Anomaly Records',
                'Committed alert and anomaly evidence. This sheet does not duplicate Alert Intelligence workflow state.',
                (
                    _column('type', 'Type', 'Alert or anomaly evidence type.', width=14),
                    _column('name', 'Signal', 'Alert or anomaly identity.', width=38),
                    _column('severity', 'Severity', 'Committed severity.', width=16),
                    _column('status', 'Status', 'Committed state.', width=16),
                    _column('namespace', 'Namespace', 'Namespace scope.', width=26),
                    _column('resource', 'Resource', 'Affected resource when supplied.', width=38),
                    _column('started_at', 'Started / Observed', 'Committed start or observation timestamp.', width=24),
                ),
                event_rows,
            )
        )
    _append_recommendations(tables, payload)
    severity_rows = tuple(
        {'category': label, 'value': count}
        for label, count in (('Critical', critical), ('Warning', warning), ('Info', info))
        if count > 0
    )
    chart = AnalyticsChartData(
        title='Active Alert Severity',
        visual_type='doughnut',
        source_sheet='Alerts & Anomalies',
        rows=severity_rows,
        series=(AnalyticsChartSeries('value', 'Alerts', '#,##0'),),
    ) if severity_rows else None
    if active or anomaly_count:
        readout = f'{active:,} active alert(s) and {anomaly_count:,} anomaly candidate(s) are committed at the report cut-off; {critical:,} alert(s) are critical.'
    else:
        readout = 'No active alert or anomaly signal is committed for the selected reporting boundary.'
    return AnalyticsWorkbookData(profile, context, metrics, readout, tuple(tables), chart)


def _parse_gib(item: Mapping[str, Any]) -> float | None:
    for key in ('usage_gib', 'size_gib', 'used_gib'):
        value = _number(item.get(key))
        if value is not None:
            return value
    bytes_value = _number(_first(item, 'usage_bytes', 'size_bytes', 'used_bytes'))
    if bytes_value is not None:
        return bytes_value / _GIB
    display = _first(item, 'usage_display', 'size_display', 'current_display')
    number = _number(display)
    if number is None:
        return None
    rendered = _text(display, '').casefold()
    if 'tib' in rendered:
        return number * 1024.0
    if 'mib' in rendered:
        return number / 1024.0
    return number


def _prepare_object_storage(
    payload: Mapping[str, Any], context: AnalyticsExportContext, profile: AnalyticsWorkbookProfile
) -> AnalyticsWorkbookData:
    summary = _mapping(payload.get('summary'))
    values = (
        _first(summary, 'capacity', default='Not Available'),
        _first(summary, 'usage', default='Not Available'),
        _first(summary, 'headroom', default='Not Available'),
        _first(summary, 'utilization', default='Not Available'),
    )
    metrics = tuple(_metric_value(spec, value) for spec, value in zip(profile.metric_specs, values, strict=True))
    capacity = _mapping(payload.get('capacity_usage'))
    performance = _mapping(payload.get('performance'))
    analysis_rows = [
        {'metric': 'Capacity', 'value': _first(capacity, 'capacity_total', default=values[0])},
        {'metric': 'Usage', 'value': _first(capacity, 'usage_total', default=values[1])},
        {'metric': 'Headroom', 'value': _first(capacity, 'capacity_free', default=values[2])},
        {'metric': 'Utilization', 'value': _first(capacity, 'utilization', default=values[3])},
        {'metric': 'Request Rate', 'value': _first(performance, 'request_rate', default='Not Available')},
        {'metric': 'Error Ratio', 'value': _first(performance, 'error_ratio', default='Not Available')},
        {'metric': 'Traffic', 'value': _first(performance, 'traffic', default='Not Available')},
    ]
    tables: list[AnalyticsTableData] = [
        _table(
            'Analysis',
            'Object Storage Analytics Summary',
            'Capacity and request-path evidence for the selected Object Storage system.',
            (
                _column('metric', 'Metric', 'Analytics metric.', width=28),
                _column('value', 'Value', 'Committed analytics value.', width=30),
            ),
            analysis_rows,
        )
    ]
    raw_consumers = _sequence(payload.get('top_consumers') or payload.get('bucket_rows'))
    consumers: list[dict[str, Any]] = []
    for item in raw_consumers:
        consumers.append(
            {
                'bucket': _first(item, 'name', 'bucket', default='Unknown Bucket'),
                'usage_gib': _parse_gib(item),
                'objects': _int(_first(item, 'object_count', 'objects', default=0)),
                'quota': _first(item, 'quota_display', 'quota', default='Not Available'),
                'usage_share': _number(item.get('usage_share')),
            }
        )
    consumers.sort(key=lambda row: float(row['usage_gib'] or 0), reverse=True)
    if consumers:
        tables.append(
            _table(
                'Top Consumers',
                'Object Storage Consumers',
                'Bucket/container usage ranking normalized to GiB when numeric usage evidence is available.',
                (
                    _column('bucket', 'Bucket / Container', 'Bucket or container identity.', width=44),
                    _column('usage_gib', 'Usage GiB', 'Committed usage normalized to GiB.', data_type='number', number_format='#,##0.00', unit='GiB', width=16),
                    _column('objects', 'Objects', 'Committed object count.', data_type='integer', number_format='#,##0', width=16),
                    _column('quota', 'Quota', 'Committed quota evidence.', width=20),
                    _column('usage_share', 'Usage Share %', 'Committed usage share when supplied.', data_type='percent', number_format='0.0"%"', width=16),
                ),
                consumers,
            )
        )
    forecast = _mapping(payload.get('forecast_display'))
    forecast_rows: list[dict[str, Any]] = []
    if forecast:
        series = _sequence(forecast.get('series') or forecast.get('rows'))
        for index, item in enumerate(series, start=1):
            forecast_rows.append(
                {
                    'observation': index,
                    'timestamp': _first(item, 'timestamp', 'date', default=''),
                    'historical_gib': _number(_first(item, 'historical_gib', 'historical', 'current_gib')),
                    'forecast_gib': _number(_first(item, 'forecast_gib', 'forecast', 'projected_gib')),
                }
            )
    if forecast_rows:
        tables.append(
            _table(
                'Trends',
                'Object Storage Growth & Forecast',
                'Committed historical and forecast evidence; Excel does not calculate the forecast.',
                (
                    _column('observation', 'Observation', 'Source-order point.', data_type='integer', number_format='#,##0', width=14),
                    _column('timestamp', 'Timestamp', 'Committed timestamp.', width=22),
                    _column('historical_gib', 'Historical GiB', 'Committed historical usage.', data_type='number', number_format='#,##0.00', unit='GiB', width=18),
                    _column('forecast_gib', 'Forecast GiB', 'Committed forecast usage.', data_type='number', number_format='#,##0.00', unit='GiB', width=18),
                ),
                forecast_rows,
            )
        )
    alert_rows = _sequence(payload.get('alerts'))
    if alert_rows:
        normalized_alerts = [
            {
                'name': _first(item, 'name', 'alertname', 'label', default='Not Available'),
                'severity': _first(item, 'severity', default='Unknown'),
                'status': _first(item, 'status', 'state', default='Not Available'),
                'resource': _first(item, 'resource', 'bucket', default='Not Available'),
            }
            for item in alert_rows
        ]
        tables.append(
            _table(
                'Alerts & Anomalies',
                'Object Storage Alert Evidence',
                'Committed alert evidence associated with the selected Object Storage system.',
                (
                    _column('name', 'Signal', 'Alert identity.', width=38),
                    _column('severity', 'Severity', 'Committed severity.', width=16),
                    _column('status', 'Status', 'Committed alert state.', width=16),
                    _column('resource', 'Resource', 'Affected bucket/system resource.', width=34),
                ),
                normalized_alerts,
            )
        )
    chart_rows = tuple({'category': row['bucket'], 'value': row['usage_gib']} for row in consumers[:8] if row['usage_gib'] is not None)
    chart = AnalyticsChartData(
        title='Top Object Storage Consumers',
        visual_type='ranked_bar',
        source_sheet='Top Consumers',
        rows=chart_rows,
        series=(AnalyticsChartSeries('value', 'Usage', '#,##0.00', 'GiB'),),
        value_axis_title='Usage (GiB)',
    ) if chart_rows else None
    if consumers and consumers[0]['usage_gib'] is not None:
        readout = f'{consumers[0]["bucket"]} is the leading committed storage consumer at {float(consumers[0]["usage_gib"]):.2f} GiB.'
    else:
        readout = 'No committed bucket/container usage ranking is available for the selected reporting boundary.'
    return AnalyticsWorkbookData(profile, context, metrics, readout, tuple(tables), chart)


def _prepare_overview(
    payload: Mapping[str, Any], context: AnalyticsExportContext, profile: AnalyticsWorkbookProfile
) -> AnalyticsWorkbookData:
    resources = _mapping(payload.get('resource_snapshot'))
    cpu = _number(_first(_mapping(resources.get('cpu')), 'percent', 'value'))
    memory = _number(_first(_mapping(resources.get('memory')), 'percent', 'value'))
    forecast = _mapping(payload.get('forecast_snapshot'))

    forecast_rows: list[dict[str, Any]] = []
    for item in _sequence(forecast.get('series')):
        key = str(_first(item, 'key', default='') or '').strip().lower()
        if not key:
            continue
        resource = _mapping(resources.get(key))
        current = _number(_first(item, 'latest_percent', 'current_percent'))
        if current is None:
            current = _number(_first(resource, 'percent', 'value'))
        projected = _number(_first(item, 'projected_percent', 'forecast_percent'))
        if projected is None:
            continue
        label = _first(item, 'label', default='') or {
            'cpu': 'CPU',
            'memory': 'Memory',
            'storage': 'Storage',
            'pods': 'Pods',
        }.get(key, key.replace('_', ' ').title())
        change = round(projected - current, 2) if current is not None else None
        forecast_rows.append(
            {
                'resource': str(label),
                'current_percent': current,
                'projected_percent': projected,
                'change_pp': change,
                'trend': _first(item, 'trend', default=_first(forecast, f'{key}_trend', default='Unknown')),
                'confidence': _first(item, 'confidence', default='Not Available'),
            }
        )

    forecast_peak = _number(_first(forecast, 'highest_projected_percent', 'projected_percent'))
    if forecast_peak is None and forecast_rows:
        forecast_peak = max(
            row['projected_percent'] for row in forecast_rows if row['projected_percent'] is not None
        )

    alerts = _mapping(payload.get('alerts_snapshot'))
    alert_detail = _mapping(payload.get('alert_detail'))
    alert_summary = _mapping(alert_detail.get('summary'))
    active_alerts = _int(
        _first(
            alert_summary,
            'active_alerts',
            default=_first(
                alerts,
                'firing_alerts',
                default=sum(
                    _int(_first(alerts, key, f'{key}_alerts'))
                    for key in ('critical', 'warning', 'info')
                ),
            ),
        )
    )
    values = (cpu, memory, forecast_peak, active_alerts)
    metrics = tuple(_metric_value(spec, value) for spec, value in zip(profile.metric_specs, values, strict=True))

    analysis_rows: list[dict[str, Any]] = []
    for key, label in (('cpu', 'CPU'), ('memory', 'Memory'), ('pods', 'Pods'), ('storage', 'Storage')):
        item = _mapping(resources.get(key))
        value = _number(_first(item, 'percent', 'value'))
        if item or value is not None:
            analysis_rows.append(
                {
                    'resource': label,
                    'current_percent': value,
                    'headroom_percent': (100.0 - value) if value is not None else None,
                    'status': _first(item, 'status', 'label', default='Not Available'),
                }
            )

    tables: list[AnalyticsTableData] = []
    if analysis_rows:
        tables.append(
            _table(
                'Analysis',
                'Cross-Domain Resource Posture',
                'Committed resource snapshot across the selected analytics boundary.',
                _RESOURCE_COLUMNS,
                analysis_rows,
            )
        )
    if forecast_rows:
        tables.append(
            _table(
                'Trends',
                'Current & Projected Resource Posture',
                'Committed latest observations and backend-owned forecast projections by resource.',
                _FORECAST_POSTURE_COLUMNS,
                forecast_rows,
            )
        )

    consumers = _mapping(payload.get('top_consumers'))
    consumer_rows: list[dict[str, Any]] = []
    for resource in ('memory', 'cpu'):
        for item in _sequence(consumers.get(resource)):
            consumer_rows.append(
                {
                    'resource': resource.title(),
                    'namespace': _first(item, 'namespace', default='Not Available'),
                    'consumer': _first(item, 'name', 'pod', 'workload', default='Not Available'),
                    'display_value': _first(item, 'display_value', 'current_display', default='Not Available'),
                    'percent': _number(_first(item, 'percent', 'value')),
                }
            )
    if consumer_rows:
        tables.append(
            _table(
                'Top Consumers',
                'Leading Consumer Signals',
                'Committed consumer signals from the analytics overview payload.',
                (
                    _column('resource', 'Resource', 'Resource signal.', width=14),
                    _column('namespace', 'Namespace', 'Namespace identity.', width=28),
                    _column('consumer', 'Consumer', 'Consumer identity.', width=44),
                    _column('display_value', 'Display Value', 'Committed formatted value.', width=18),
                    _column('percent', 'Percent', 'Committed percentage when supplied.', data_type='percent', number_format='0.0"%"', width=15),
                ),
                consumer_rows,
            )
        )

    alert_rows = _sequence(alert_detail.get('alerts'))
    if alert_rows:
        tables.append(
            _table(
                'Alerts & Anomalies',
                'Active Alert Evidence',
                'Committed alert records included in the analytics overview.',
                (
                    _column('name', 'Signal', 'Alert identity.', width=38),
                    _column('severity', 'Severity', 'Committed severity.', width=16),
                    _column('status', 'Status', 'Committed state.', width=16),
                    _column('namespace', 'Namespace', 'Namespace scope.', width=26),
                ),
                [
                    {
                        'name': _first(item, 'name', 'alertname', 'label', default='Not Available'),
                        'severity': _first(item, 'severity', default='Unknown'),
                        'status': _first(item, 'status', 'state', default='Not Available'),
                        'namespace': _first(item, 'namespace', default='All Namespaces'),
                    }
                    for item in alert_rows
                ],
            )
        )

    _append_recommendations(tables, payload)
    chart = None
    if forecast_rows:
        chart = AnalyticsChartData(
            title='Current vs Projected Resource Posture',
            visual_type='comparison_bar',
            source_sheet='Trends',
            rows=tuple(forecast_rows),
            category_key='resource',
            series=(
                AnalyticsChartSeries('current_percent', 'Current', '0.0', '%'),
                AnalyticsChartSeries('projected_percent', 'Projected', '0.0', '%'),
            ),
            value_axis_title='Percent',
        )

    if forecast_peak is not None:
        resource_label = str(_first(forecast, 'highest_projected_resource', default='Forecast Peak') or 'Forecast Peak')
        readout = (
            f'{resource_label} is the leading committed analytics projection at {forecast_peak:.1f}%. '
            'Review the Current vs Projected evidence before taking action.'
        )
    else:
        readout = _leading_percent_readout(metrics[:2], 'analytics')

    return AnalyticsWorkbookData(profile, context, metrics, readout, tuple(tables), chart)


_PREPARERS: dict[str, _Preparer] = {
    'analytics_overview': _prepare_overview,
    'resource_utilization': _prepare_resource_utilization,
    'capacity_analysis': _prepare_capacity,
    'storage_analysis': _prepare_storage,
    'workload_analysis': _prepare_workload,
    'resource_forecast': _prepare_forecast,
    'top_consumers': _prepare_top_consumers,
    'alerts_anomalies': _prepare_alerts,
    'object_storage_analysis': _prepare_object_storage,
}

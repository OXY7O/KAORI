from __future__ import annotations

from typing import Any

from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Spacer

from app.analytics.storage.service import StorageAnalysisService
from app.analytics.utilization.service import UtilizationService
from app.analytics.utilization.service import (
    get_selected_cluster as get_utilization_selected_cluster,
)
from app.cluster.constants import get_environment_label
from app.intelligence.recommendation_engine import build_storage_actionable_recommendations
from app.models.report import Report
from app.prometheus.service import PrometheusService
from app.reports.export.helpers import (
    _format_resource_number,
    _pdf_value,
    build_key_value_table,
    build_pdf_table,
    build_single_section_content,
    build_status_banner,
)


def build_storage_analysis_pdf_sections(
    report: Report,
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    payload = get_report_storage_analysis_payload(
        report,
    )

    if payload.get('_error'):
        return build_storage_analysis_error_section(
            payload,
            styles,
        )

    sections = report.sections_as_list()

    if not sections:
        sections = [
            'executive_summary',
            'filesystem_summary',
            'persistent_volume_summary',
            'persistent_volume_claims',
            'storage_risk',
            'operational_recommendations',
        ]

    story: list[Any] = [
        Paragraph(
            'Storage Analysis Data',
            styles['section_title'],
        ),
        Paragraph(
            (
                'This section is rendered from the Storage Analysis service. '
                'Filesystem usage, PersistentVolume capacity, and PersistentVolumeClaim usage '
                'are rendered as separate storage perspectives because they come from different Kubernetes and node metrics.'  # noqa: E501
            ),
            styles['normal'],
        ),
        Spacer(
            1,
            0.25 * cm,
        ),
    ]

    if 'executive_summary' in sections:
        story.extend(
            build_storage_executive_summary(
                report,
                payload,
                styles,
            )
        )

    if 'filesystem_summary' in sections:
        story.extend(
            build_storage_filesystem_summary_section(
                payload,
                styles,
            )
        )

    if 'persistent_volume_summary' in sections:
        story.extend(
            build_storage_persistent_volume_section(
                payload,
                styles,
            )
        )

    if 'persistent_volume_claims' in sections:
        story.extend(
            build_storage_pvc_section(
                payload,
                styles,
            )
        )

    if 'storage_risk' in sections:
        story.extend(
            build_storage_risk_section(
                payload,
                styles,
            )
        )

    if 'operational_recommendations' in sections:
        story.extend(
            build_storage_recommendations_section(
                payload,
                styles,
            )
        )

    rendered_sections = {
        'executive_summary',
        'filesystem_summary',
        'persistent_volume_summary',
        'persistent_volume_claims',
        'storage_risk',
        'operational_recommendations',
    }

    for section in sections:
        if section in rendered_sections:
            continue

        story.extend(
            build_single_section_content(
                section,
                styles,
            )
        )

    return story


def get_report_storage_analysis_payload(
    report: Report,
) -> dict[str, Any]:
    try:
        cluster = get_utilization_selected_cluster(
            report.cluster_id,
        )

        if not cluster:
            return {
                '_error': 'No cluster configured for Storage Analysis report.',
            }

        prometheus = PrometheusService(
            cluster,
        )

        utilization_service = UtilizationService(
            prometheus,
        )

        storage_service = StorageAnalysisService(
            utilization_service,
            PrometheusConsumer(cluster),
        )

        prometheus_status = storage_service.get_prometheus_status()

        storage_summary = storage_service.get_storage_capacity_summary(
            selected_namespace=report.namespace or '',
            selected_node='',
            selected_pvc_search='',
            selected_pvc_status='',
            selected_pvc_storage_class='',
            pvc_page=1,
            pvc_per_page=1000,
            selected_pv_search='',
            selected_pv_status='',
            selected_pv_storage_class='',
            pv_page=1,
            pv_per_page=1000,
        )

        namespace_options = storage_service.get_storage_namespace_options()

        return {
            'cluster': {
                'id': str(
                    getattr(
                        cluster,
                        'id',
                        '',
                    )
                ),
                'name': str(
                    getattr(
                        cluster,
                        'name',
                        'Unknown Cluster',
                    )
                ),
                'environment': get_environment_label(getattr(cluster, 'environment', None), empty=''),
                'status': str(
                    getattr(
                        cluster,
                        'status',
                        '',
                    )
                    or ''
                ),
            },
            'selected_namespace': report.namespace or 'All Namespaces',
            'selected_time_range': report.period or '24h',
            'prometheus_status': prometheus_status,
            'storage_summary': storage_summary,
            'namespace_options': namespace_options,
        }

    except Exception as exc:
        return {
            '_error': str(
                exc,
            ),
        }


def build_storage_analysis_error_section(
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    return [
        Paragraph(
            'Storage Analysis Data',
            styles['section_title'],
        ),
        build_status_banner(
            'Storage payload unavailable',
            (
                'KAORI could not load the Storage Analysis payload while rendering this PDF. '
                f'Error: {payload.get("_error", "Unknown error")}'
            ),
        ),
    ]


def build_storage_executive_summary(
    report: Report,
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    cluster = (
        payload.get(
            'cluster',
        )
        or {}
    )

    prometheus_status = (
        payload.get(
            'prometheus_status',
        )
        or {}
    )

    namespace_options = payload.get(
        'namespace_options',
        [],
    )

    rows = [
        [
            'Selected Cluster',
            cluster.get(
                'name',
                'Unknown Cluster',
            ),
        ],
        [
            'Cluster ID',
            cluster.get(
                'id',
                report.cluster_id or '-',
            ),
        ],
        [
            'Namespace Scope',
            payload.get(
                'selected_namespace',
                'All Namespaces',
            ),
        ],
        [
            'Time Range',
            payload.get(
                'selected_time_range',
                report.period or '24h',
            ),
        ],
        [
            'Storage Scope',
            'Filesystem /var, Kubernetes PersistentVolume, and PersistentVolumeClaim metrics.',
        ],
        [
            'Namespace Options',
            len(
                namespace_options,
            )
            if isinstance(
                namespace_options,
                list,
            )
            else 0,
        ],
        [
            'Prometheus Status',
            prometheus_status.get(
                'label',
                'Unknown',
            ),
        ],
        [
            'Prometheus Message',
            prometheus_status.get(
                'description',
                '-',
            ),
        ],
    ]

    return [
        Paragraph(
            'Executive Summary',
            styles['small_section_title'],
        ),
        build_key_value_table(
            rows,
            styles,
        ),
        Spacer(
            1,
            0.3 * cm,
        ),
    ]


def build_storage_filesystem_summary_section(
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    storage_summary = (
        payload.get(
            'storage_summary',
        )
        or {}
    )

    node_filesystem = storage_summary.get(
        'node_filesystem',
        {},
    )

    summary = node_filesystem.get(
        'summary',
        {},
    )

    rows = [
        [
            'Metric',
            'Value',
        ],
        [
            'Capacity',
            _pdf_value(
                summary.get(
                    'capacity',
                    '-',
                )
            ),
        ],
        [
            'Used',
            _pdf_value(
                summary.get(
                    'used',
                    '-',
                )
            ),
        ],
        [
            'Free',
            _pdf_value(
                summary.get(
                    'free',
                    '-',
                )
            ),
        ],
        [
            'Usage Percent',
            f'{_format_resource_number(summary.get("usage_percent", 0))}%',
        ],
        [
            'Free Percent',
            f'{_format_resource_number(summary.get("free_percent", 0))}%',
        ],
        [
            'Highest Usage',
            f'{_format_resource_number(summary.get("highest_usage", 0))}%',
        ],
        [
            'Highest Node',
            _pdf_value(
                summary.get(
                    'highest_node',
                    '-',
                )
            ),
        ],
    ]

    story: list[Any] = [
        Paragraph(
            'Filesystem Summary',
            styles['small_section_title'],
        ),
        Paragraph(
            'Filesystem usage is based on node filesystem metrics for mountpoint /var.',
            styles['small'],
        ),
        Spacer(
            1,
            0.15 * cm,
        ),
        build_key_value_table(
            rows[1:],
            styles,
        ),
        Spacer(
            1,
            0.25 * cm,
        ),
    ]

    story.extend(
        build_storage_filesystem_rows_section(
            node_filesystem,
            styles,
        )
    )

    return story


def build_storage_filesystem_rows_section(
    node_filesystem: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    rows = [
        [
            'Node / Instance',
            'Mountpoint',
            'Capacity',
            'Used',
            'Free',
            'Usage',
            'Risk',
        ],
    ]

    node_rows = node_filesystem.get(
        'rows',
        [],
    )

    if isinstance(
        node_rows,
        list,
    ):
        for row in node_rows[:10]:
            if not isinstance(
                row,
                dict,
            ):
                continue

            risk = row.get(
                'risk',
                {},
            )

            risk_label = '-'

            if isinstance(
                risk,
                dict,
            ):
                risk_label = _pdf_value(
                    risk.get(
                        'label',
                        '-',
                    )
                )

            rows.append(
                [
                    _pdf_value(
                        row.get(
                            'node',
                            '-',
                        )
                    ),
                    _pdf_value(
                        row.get(
                            'mountpoint',
                            '-',
                        )
                    ),
                    _pdf_value(
                        row.get(
                            'capacity',
                            '-',
                        )
                    ),
                    _pdf_value(
                        row.get(
                            'used',
                            '-',
                        )
                    ),
                    _pdf_value(
                        row.get(
                            'free',
                            '-',
                        )
                    ),
                    f'{_format_resource_number(row.get("usage_percent", 0))}%',
                    risk_label,
                ]
            )

    if (
        len(
            rows,
        )
        == 1
    ):
        rows.append(
            [
                '-',
                '-',
                '-',
                '-',
                '-',
                '-',
                'No filesystem row data available.',
            ]
        )

    return [
        Paragraph(
            'Filesystem Detail',
            styles['small_section_title'],
        ),
        build_pdf_table(
            rows,
            styles,
            col_widths=[
                3.6 * cm,
                2.2 * cm,
                2.2 * cm,
                2.2 * cm,
                2.2 * cm,
                1.8 * cm,
                2.0 * cm,
            ],
        ),
        Spacer(
            1,
            0.3 * cm,
        ),
    ]


def build_storage_persistent_volume_section(
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    persistent_storage = (
        payload.get(
            'storage_summary',
        )
        or {}
    ).get(
        'persistent_storage',
        {},
    )

    pv_summary = persistent_storage.get(
        'pv',
        {},
    )

    rows = [
        [
            'Metric',
            'Value',
        ],
        [
            'PV Count',
            _pdf_value(
                pv_summary.get(
                    'count',
                    0,
                )
            ),
        ],
        [
            'PV Capacity',
            _pdf_value(
                pv_summary.get(
                    'capacity',
                    '-',
                )
            ),
        ],
        [
            'PVC Used',
            _pdf_value(
                pv_summary.get(
                    'used',
                    '-',
                )
            ),
        ],
        [
            'PVC Free',
            _pdf_value(
                pv_summary.get(
                    'free',
                    '-',
                )
            ),
        ],
        [
            'Used Percent',
            f'{_format_resource_number(pv_summary.get("used_percent", 0))}%',
        ],
        [
            'Free Percent',
            f'{_format_resource_number(pv_summary.get("free_percent", 0))}%',
        ],
    ]

    story: list[Any] = [
        Paragraph(
            'Persistent Volume Summary',
            styles['small_section_title'],
        ),
        Paragraph(
            'PersistentVolume capacity is based on Kubernetes PV capacity metrics. Used/free values are derived from PVC volume stats where available.',  # noqa: E501
            styles['small'],
        ),
        Spacer(
            1,
            0.15 * cm,
        ),
        build_key_value_table(
            rows[1:],
            styles,
        ),
        Spacer(
            1,
            0.25 * cm,
        ),
    ]

    story.extend(
        build_storage_pv_rows_section(
            persistent_storage,
            styles,
        )
    )

    return story


def build_storage_pv_rows_section(
    persistent_storage: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    rows = [
        [
            'PV Name',
            'Status',
            'Capacity',
            'StorageClass',
            'Claim',
            'Reclaim',
            'Risk',
        ],
    ]

    pv_rows = persistent_storage.get(
        'pv_rows',
        [],
    )

    if isinstance(
        pv_rows,
        list,
    ):
        for row in pv_rows[:10]:
            if not isinstance(
                row,
                dict,
            ):
                continue

            risk = row.get(
                'risk',
                {},
            )

            risk_label = '-'

            if isinstance(
                risk,
                dict,
            ):
                risk_label = _pdf_value(
                    risk.get(
                        'label',
                        '-',
                    )
                )

            rows.append(
                [
                    _pdf_value(
                        row.get(
                            'name',
                            '-',
                        )
                    ),
                    _pdf_value(
                        row.get(
                            'status',
                            '-',
                        )
                    ),
                    _pdf_value(
                        row.get(
                            'capacity',
                            '-',
                        )
                    ),
                    _pdf_value(
                        row.get(
                            'storage_class',
                            '-',
                        )
                    ),
                    _pdf_value(
                        row.get(
                            'claim',
                            '-',
                        )
                    ),
                    _pdf_value(
                        row.get(
                            'reclaim_policy',
                            '-',
                        )
                    ),
                    risk_label,
                ]
            )

    if (
        len(
            rows,
        )
        == 1
    ):
        rows.append(
            [
                '-',
                '-',
                '-',
                '-',
                '-',
                '-',
                'No PV row data available.',
            ]
        )

    return [
        Paragraph(
            'Persistent Volume Detail',
            styles['small_section_title'],
        ),
        build_pdf_table(
            rows,
            styles,
            col_widths=[
                3.8 * cm,
                2.0 * cm,
                2.2 * cm,
                2.5 * cm,
                3.0 * cm,
                1.8 * cm,
                1.7 * cm,
            ],
        ),
        Spacer(
            1,
            0.3 * cm,
        ),
    ]


def build_storage_pvc_section(
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    persistent_storage = (
        payload.get(
            'storage_summary',
        )
        or {}
    ).get(
        'persistent_storage',
        {},
    )

    pvc_summary = persistent_storage.get(
        'pvc',
        {},
    )

    rows = [
        [
            'Metric',
            'Value',
        ],
        [
            'PVC Count',
            _pdf_value(
                pvc_summary.get(
                    'count',
                    0,
                )
            ),
        ],
        [
            'Requested',
            _pdf_value(
                pvc_summary.get(
                    'requested',
                    '-',
                )
            ),
        ],
        [
            'Used',
            _pdf_value(
                pvc_summary.get(
                    'used',
                    '-',
                )
            ),
        ],
        [
            'Free',
            _pdf_value(
                pvc_summary.get(
                    'free',
                    '-',
                )
            ),
        ],
        [
            'Used Percent',
            f'{_format_resource_number(pvc_summary.get("used_percent", 0))}%',
        ],
        [
            'Free Percent',
            f'{_format_resource_number(pvc_summary.get("free_percent", 0))}%',
        ],
    ]

    story: list[Any] = [
        Paragraph(
            'Persistent Volume Claims',
            styles['small_section_title'],
        ),
        Paragraph(
            'PVC summary compares requested storage against kubelet volume used/free metrics where available.',
            styles['small'],
        ),
        Spacer(
            1,
            0.15 * cm,
        ),
        build_key_value_table(
            rows[1:],
            styles,
        ),
        Spacer(
            1,
            0.25 * cm,
        ),
    ]

    story.extend(
        build_storage_pvc_rows_section(
            persistent_storage,
            styles,
        )
    )

    return story


def build_storage_pvc_rows_section(
    persistent_storage: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    rows = [
        [
            'Namespace',
            'PVC Name',
            'Status',
            'StorageClass',
            'Requested',
            'Used',
            'Risk',
        ],
    ]

    pvc_rows = persistent_storage.get(
        'pvc_rows',
        [],
    )

    if isinstance(
        pvc_rows,
        list,
    ):
        for row in pvc_rows[:10]:
            if not isinstance(
                row,
                dict,
            ):
                continue

            risk = row.get(
                'risk',
                {},
            )

            risk_label = '-'

            if isinstance(
                risk,
                dict,
            ):
                risk_label = _pdf_value(
                    risk.get(
                        'label',
                        '-',
                    )
                )

            rows.append(
                [
                    _pdf_value(
                        row.get(
                            'namespace',
                            '-',
                        )
                    ),
                    _pdf_value(
                        row.get(
                            'name',
                            '-',
                        )
                    ),
                    _pdf_value(
                        row.get(
                            'status',
                            '-',
                        )
                    ),
                    _pdf_value(
                        row.get(
                            'storage_class',
                            '-',
                        )
                    ),
                    _pdf_value(
                        row.get(
                            'requested',
                            '-',
                        )
                    ),
                    _pdf_value(
                        row.get(
                            'used',
                            '-',
                        )
                    ),
                    risk_label,
                ]
            )

    if (
        len(
            rows,
        )
        == 1
    ):
        rows.append(
            [
                '-',
                '-',
                '-',
                '-',
                '-',
                '-',
                'No PVC row data available.',
            ]
        )

    return [
        Paragraph(
            'Persistent Volume Claim Detail',
            styles['small_section_title'],
        ),
        build_pdf_table(
            rows,
            styles,
            col_widths=[
                2.8 * cm,
                3.5 * cm,
                1.9 * cm,
                2.7 * cm,
                2.0 * cm,
                1.8 * cm,
                1.5 * cm,
            ],
        ),
        Spacer(
            1,
            0.3 * cm,
        ),
    ]


def build_storage_risk_section(
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    persistent_storage = (
        payload.get(
            'storage_summary',
        )
        or {}
    ).get(
        'persistent_storage',
        {},
    )

    node_filesystem = (
        payload.get(
            'storage_summary',
        )
        or {}
    ).get(
        'node_filesystem',
        {},
    )

    pvc_rows = persistent_storage.get(
        'pvc_rows',
        [],
    )

    pv_rows = persistent_storage.get(
        'pv_rows',
        [],
    )

    filesystem_rows = node_filesystem.get(
        'rows',
        [],
    )

    risk_summary = build_storage_risk_summary_rows(
        filesystem_rows=filesystem_rows,
        pvc_rows=pvc_rows,
        pv_rows=pv_rows,
    )

    return [
        Paragraph(
            'Storage Risk',
            styles['small_section_title'],
        ),
        build_pdf_table(
            risk_summary,
            styles,
            col_widths=[
                4.8 * cm,
                3.0 * cm,
                8.4 * cm,
            ],
        ),
        Spacer(
            1,
            0.3 * cm,
        ),
    ]


def build_storage_risk_summary_rows(
    *,
    filesystem_rows: Any,
    pvc_rows: Any,
    pv_rows: Any,
) -> list[list[Any]]:
    fs_risk_count = count_storage_rows_by_risk(
        filesystem_rows,
        risk_labels=[
            'watch',
            'high',
            'critical',
        ],
    )

    pvc_risk_count = count_storage_rows_by_risk(
        pvc_rows,
        risk_labels=[
            'warning',
            'watch',
            'high',
            'critical',
        ],
    )

    pv_risk_count = count_storage_rows_by_risk(
        pv_rows,
        risk_labels=[
            'watch',
            'critical',
            'unknown',
        ],
    )

    return [
        [
            'Risk Area',
            'Count',
            'Description',
        ],
        [
            'Filesystem Risk',
            fs_risk_count,
            'Filesystem rows with Watch, High, or Critical risk label.',
        ],
        [
            'PVC Risk',
            pvc_risk_count,
            'PVC rows with Warning, Watch, High, or Critical risk label.',
        ],
        [
            'PV Risk',
            pv_risk_count,
            'PV rows with Watch, Critical, or Unknown risk label.',
        ],
    ]


def count_storage_rows_by_risk(
    rows: Any,
    risk_labels: list[str],
) -> int:
    if not isinstance(
        rows,
        list,
    ):
        return 0

    count = 0

    allowed = {label.lower() for label in risk_labels}

    for row in rows:
        if not isinstance(
            row,
            dict,
        ):
            continue

        risk = row.get(
            'risk',
            {},
        )

        if not isinstance(
            risk,
            dict,
        ):
            continue

        label = str(
            risk.get(
                'label',
                '',
            )
        ).lower()

        if label in allowed:
            count += 1

    return count


def build_storage_recommendations_section(
    payload: dict[str, Any],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    recommendations = build_storage_actionable_recommendations(
        payload,
    )

    rows = [
        [
            'No',
            'Recommendation',
            'Priority',
            'Source',
        ],
    ]

    for index, item in enumerate(
        recommendations,
        start=1,
    ):
        rows.append(
            [
                str(
                    index,
                ),
                _pdf_value(
                    item.get(
                        'title',
                        '-',
                    )
                ),
                _pdf_value(
                    item.get(
                        'priority',
                        '-',
                    )
                ),
                _pdf_value(
                    item.get(
                        'source_label',
                        item.get(
                            'source',
                            '-',
                        ),
                    )
                ),
            ]
        )

        rows.append(
            [
                '',
                _pdf_value(
                    item.get(
                        'description',
                        '-',
                    )
                ),
                'Actionable'
                if item.get(
                    'is_actionable',
                    'No',
                )
                == 'Yes'
                else 'Context',
                '',
            ]
        )

    return [
        Paragraph(
            'Actionable Recommendations from Storage Analysis',
            styles['small_section_title'],
        ),
        Paragraph(
            (
                'Recommendations are derived from filesystem usage, PVC capacity, PVC status, '
                'PV lifecycle state, and storage risk signals. Static report guidance is used only as fallback context.'
            ),
            styles['small'],
        ),
        Spacer(
            1,
            0.15 * cm,
        ),
        build_pdf_table(
            rows,
            styles,
            col_widths=[
                1.2 * cm,
                8.0 * cm,
                3.0 * cm,
                4.0 * cm,
            ],
        ),
        Spacer(
            1,
            0.3 * cm,
        ),
    ]


def build_storage_recommendations(
    *,
    filesystem_rows: Any,
    pvc_rows: Any,
    pv_rows: Any,
) -> list[dict[str, str]]:
    fs_risk_count = count_storage_rows_by_risk(
        filesystem_rows,
        risk_labels=[
            'watch',
            'high',
            'critical',
        ],
    )

    pvc_risk_count = count_storage_rows_by_risk(
        pvc_rows,
        risk_labels=[
            'warning',
            'watch',
            'high',
            'critical',
        ],
    )

    pv_risk_count = count_storage_rows_by_risk(
        pv_rows,
        risk_labels=[
            'watch',
            'critical',
            'unknown',
        ],
    )

    recommendations: list[dict[str, str]] = []

    if fs_risk_count > 0:
        recommendations.append(
            {
                'label': (
                    f'Review {fs_risk_count} filesystem risk item(s). '
                    'Prioritize nodes with high /var usage before workload placement or image growth causes pressure.'
                ),
                'priority': 'Warning',
            }
        )

    if pvc_risk_count > 0:
        recommendations.append(
            {
                'label': (
                    f'Review {pvc_risk_count} PVC risk item(s). '
                    'Check PVC status, used capacity, and namespace ownership before expansion.'
                ),
                'priority': 'Warning',
            }
        )

    if pv_risk_count > 0:
        recommendations.append(
            {
                'label': (
                    f'Review {pv_risk_count} PV risk item(s). '
                    'Check Available, Released, Failed, or Unknown PV states and reclaim policy.'
                ),
                'priority': 'Warning',
            }
        )

    if not recommendations:
        recommendations.extend(
            [
                {
                    'label': 'No critical storage risk detected. Continue regular filesystem, PV, and PVC monitoring.',
                    'priority': 'Normal',
                },
                {
                    'label': 'Review namespaces with growing PVC usage before they reach warning threshold.',
                    'priority': 'Info',
                },
                {
                    'label': 'Validate storage class and reclaim policy for PVs used by critical workloads.',
                    'priority': 'Info',
                },
            ]
        )

    return recommendations

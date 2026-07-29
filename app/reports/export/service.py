from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from flask import current_app
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
)

from app.extensions.db import db
from app.models.report import Report
from app.reports.export.constants import (
    DEFAULT_RECOMMENDATIONS,
    REAL_DATA_REPORT_TYPES,
    REAL_DATA_SECTION_MAP,
    REPORT_DOMAIN_LABELS,
    REPORT_TYPE_DESCRIPTIONS,
    REPORT_TYPE_LABELS,
    REPORT_TYPE_RECOMMENDATIONS,
    REQUIRES_SINGLE_CLUSTER_REPORT_TYPES,
    SECTION_LABELS,
    SOURCE_KIND_LABELS,
)
from app.reports.export.helpers import (
    build_key_value_table,
    build_single_section_content,
    build_status_banner,
    format_datetime,
    format_period,
    safe_text,
    slugify,
)
from app.reports.export.sections.alerts import build_alerts_anomalies_pdf_sections
from app.reports.export.sections.analytics import build_analytics_overview_pdf_sections
from app.reports.export.sections.capacity import build_capacity_analysis_pdf_sections
from app.reports.export.sections.forecast import build_resource_forecast_pdf_sections
from app.reports.export.sections.storage import build_storage_analysis_pdf_sections
from app.reports.export.sections.top_consumers import build_top_consumers_pdf_sections
from app.reports.export.sections.utilization import build_resource_utilization_pdf_sections
from app.reports.export.sections.workload import build_workload_analysis_pdf_sections
from app.reports.export.styles import (
    build_pdf_styles,
    default_grid_table_style,
    default_metadata_table_style,
    draw_page_footer,
)
from app.reports.storage.naming import build_report_object_key
from app.reports.storage.service import (
    build_report_download_path,
    report_file_exists,
    save_report_file,
)


def is_real_data_report(
    report: Report,
) -> bool:
    return report.report_type in REAL_DATA_REPORT_TYPES


def requires_single_cluster(
    report: Report,
) -> bool:
    return report.report_type in REQUIRES_SINGLE_CLUSTER_REPORT_TYPES


def should_block_all_clusters_real_data_report(
    report: Report,
) -> bool:
    return (
        requires_single_cluster(
            report,
        )
        and not report.cluster_id
    )


def generate_pdf_for_report(
    report_id: int,
) -> tuple[bool, str]:
    report = db.session.get(
        Report,
        report_id,
    )

    if report is None:
        return False, 'Report not found.'

    previous_status = report.status
    previous_file_path = report.file_path
    previous_file_size_bytes = report.file_size_bytes
    previous_artifact_available = bool(
        previous_file_path,
    ) and report_file_exists(
        previous_file_path,
    )

    staging_path: Path | None = None

    try:
        report.status = 'generating'
        report.error_message = None
        db.session.commit()

        staging_path = build_report_output_path(
            report,
        )

        renderer_used = render_report_pdf(
            report,
            staging_path,
        )

        object_key = build_report_object_key(
            report,
        )
        stored_file = save_report_file(
            source_path=staging_path,
            object_key=object_key,
        )

        report.file_path = stored_file.uri
        report.file_size_bytes = stored_file.size_bytes
        report.status = 'ready'
        report.error_message = None

        db.session.commit()

        if previous_status == 'ready' and previous_artifact_available:
            return (
                True,
                (
                    f'PDF report regenerated successfully with {format_renderer_label(renderer_used)}. '
                    'Previous artifact is retained until cleanup policy is enabled.'
                ),
            )

        return True, f'PDF report generated successfully with {format_renderer_label(renderer_used)}.'

    except Exception:
        current_app.logger.exception(
            'Report PDF generation failed for report %s.',
            report_id,
        )
        db.session.rollback()

        failed_report = db.session.get(
            Report,
            report_id,
        )

        user_message = (
            'KAORI could not render the PDF artifact. Review report scope, integration readiness, '
            'and worker logs before retrying.'
        )

        if failed_report is not None:
            if previous_status == 'ready' and previous_artifact_available:
                failed_report.status = 'ready'
                failed_report.file_path = previous_file_path
                failed_report.file_size_bytes = previous_file_size_bytes
                failed_report.error_message = (
                    'Regeneration failed. The existing ready artifact was retained. '
                    f'{user_message}'
                )
            else:
                failed_report.status = 'failed'
                failed_report.error_message = user_message

            db.session.commit()

        if previous_status == 'ready' and previous_artifact_available:
            return False, f'Regeneration failed. The existing artifact was retained. {user_message}'

        return False, user_message

    finally:
        if staging_path is not None and staging_path.exists():
            staging_path.unlink(
                missing_ok=True,
            )


def get_download_file_path(
    report_id: int,
) -> tuple[bool, str, Path | None]:
    report = db.session.get(
        Report,
        report_id,
    )

    if report is None:
        return False, 'Report not found.', None

    if report.status not in ['ready', 'archived']:
        return False, 'Report is not ready or archived for download.', None

    if not report.file_path:
        return False, 'Report file path is not available.', None

    try:
        if not report_file_exists(
            report.file_path,
        ):
            return False, 'Report file does not exist in configured storage.', None

        file_path = build_report_download_path(
            report.file_path,
        )
    except Exception:  # External storage errors are converted to user-facing feedback.
        current_app.logger.warning(
            'Unable to access report artifact for download.',
            exc_info=True,
        )
        return (
            False,
            'Report storage is temporarily unavailable. Restore storage connectivity and try again.',
            None,
        )

    if not file_path.exists():
        return False, 'Report file is not available for download.', None

    return True, 'Report file is ready.', file_path


def build_report_output_path(
    report: Report,
) -> Path:
    staging_dir = get_report_staging_dir()
    staging_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = datetime.now(
        UTC,
    ).strftime(
        '%Y%m%d%H%M%S',
    )

    safe_name = slugify(
        report.name,
    )

    return staging_dir / f'report-{report.id}-{safe_name}-{timestamp}.pdf'


def get_report_staging_dir() -> Path:
    configured_path = current_app.config.get(
        'REPORT_RENDER_STAGING_DIR',
    )

    if configured_path:
        staging_dir = Path(
            configured_path,
        )

        if not staging_dir.is_absolute():
            staging_dir = (
                Path(
                    current_app.root_path,
                ).parent
                / staging_dir
            )

        return staging_dir

    return (
        Path(
            current_app.instance_path,
        )
        / 'report-render-staging'
    )


def get_report_storage_dir() -> Path:
    configured_path = current_app.config.get(
        'REPORT_LOCAL_STORAGE_DIR',
    )

    if configured_path:
        return Path(
            configured_path,
        )

    return Path(
        current_app.instance_path,
    )




def render_report_pdf(
    report: Report,
    output_path: Path,
) -> str:
    from app.reports.export.renderers.registry import render_report_pdf as render_with_configured_renderer

    return render_with_configured_renderer(
        report,
        output_path,
    )


def format_renderer_label(renderer_name: str) -> str:
    labels = {
        'weasyprint': 'WeasyPrint HTML/PDF',
        'reportlab': 'ReportLab Legacy',
        'reportlab-fallback': 'ReportLab Legacy fallback',
    }
    return labels.get(renderer_name, renderer_name.replace('-', ' ').title())


def render_reportlab_pdf(
    report: Report,
    output_path: Path,
) -> None:
    doc = SimpleDocTemplate(
        str(
            output_path,
        ),
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.7 * cm,
        bottomMargin=1.8 * cm,
        title=report.name,
        author='KAORI',
    )

    styles = build_pdf_styles()
    story: list[Any] = []

    story.extend(
        build_report_cover(
            report,
            styles,
        )
    )

    story.append(
        Spacer(
            1,
            0.35 * cm,
        )
    )

    story.extend(
        build_reader_overview(
            report,
            styles,
        )
    )

    story.append(
        PageBreak(),
    )

    story.extend(
        build_report_data_sections(
            report,
            styles,
        )
    )

    story.append(
        Spacer(
            1,
            0.35 * cm,
        )
    )

    story.extend(
        build_sections_summary(
            report,
            styles,
        )
    )

    story.append(
        Spacer(
            1,
            0.4 * cm,
        )
    )

    story.extend(
        build_report_type_summary(
            report,
            styles,
        )
    )

    story.append(
        Spacer(
            1,
            0.4 * cm,
        )
    )

    if not is_real_data_report(
        report,
    ):
        story.extend(
            build_sections_content(
                report,
                styles,
            )
        )

        story.append(
            Spacer(
                1,
                0.4 * cm,
            )
        )

    story.extend(
        build_recommendation_block(
            report,
            styles,
        )
    )

    doc.build(
        story,
        onFirstPage=draw_page_footer,
        onLaterPages=draw_page_footer,
    )


def build_report_cover(
    report: Report,
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    report_type = REPORT_TYPE_LABELS.get(
        report.report_type,
        report.report_type,
    )

    generated_at = datetime.now(
        UTC,
    ).strftime(
        '%d %b %Y %H:%M UTC',
    )

    description = REPORT_TYPE_DESCRIPTIONS.get(
        report.report_type,
        'Kubernetes operational report generated by KAORI.',
    )

    renderer_description = (
        'Real-data PDF renderer active. This report type is connected to the current analytics/reporting service payload.'  # noqa: E501
        if is_real_data_report(
            report,
        )
        else 'Structured generic PDF renderer active. This report type uses prepared section content until a dedicated renderer is added.'  # noqa: E501
    )

    return [
        Paragraph(
            'KAORI',
            styles['title'],
        ),
        Paragraph(
            'Kubernetes Operational Report',
            styles['subtitle'],
        ),
        HRFlowable(
            width='100%',
            thickness=1,
            color=colors.HexColor(
                '#cbd5e1',
            ),
            spaceBefore=6,
            spaceAfter=14,
        ),
        Paragraph(
            safe_text(
                report.name,
            ),
            styles['section_title'],
        ),
        Paragraph(
            f'{safe_text(report_type)} • Generated at {safe_text(generated_at)}',
            styles['subtitle'],
        ),
        Paragraph(
            safe_text(
                description,
            ),
            styles['normal'],
        ),
        Spacer(
            1,
            0.3 * cm,
        ),
        build_status_banner(
            'Renderer Status',
            renderer_description,
        ),
    ]


def build_reader_overview(
    report: Report,
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    """Build a plain-language overview before the technical tables.

    The goal is to make the PDF readable without requiring the user to open the
    dashboard UI first. This page explains scope, purpose, and how to interpret
    the selected sections in business/operations language.
    """
    report_type = REPORT_TYPE_LABELS.get(
        report.report_type,
        report.report_type,
    )

    scope = 'All clusters' if not report.cluster_id else f'Cluster {report.cluster_id}'
    namespace = report.namespace or 'All namespaces'
    period = format_period(
        report.period,
    )
    sections = report.sections_as_list()
    section_labels = [
        SECTION_LABELS.get(
            section,
            section.replace('_', ' ').title(),
        )
        for section in sections
    ]

    overview_rows = [
        [
            'What this report answers',
            get_plain_language_report_goal(report.report_type),
        ],
        [
            'Who can read it',
            'Operations, platform, infrastructure, application owner, and management users who need a concise operational health and risk summary.',
        ],
        [
            'Report family',
            f'{REPORT_DOMAIN_LABELS.get(getattr(report, "report_domain", ""), "KAORI Kubernetes Reports")} / {SOURCE_KIND_LABELS.get(getattr(report, "source_kind", ""), "Kubernetes")}',
        ],
        [
            'Report scope',
            f'{scope}; {namespace}; {period}.',
        ],
        [
            'How to read it',
            'Start with the executive summary and risk sections, then use the detail tables only when you need evidence for follow-up action.',
        ],
        [
            'Important caveat',
            'This report is a generated operational snapshot. Validate critical decisions against live cluster data when handling incidents or change approvals.',
        ],
    ]

    selected_sections = ', '.join(section_labels) if section_labels else 'No sections selected.'

    return [
        Paragraph(
            'Reader Overview',
            styles['section_title'],
        ),
        Paragraph(
            safe_text(
                f'This {report_type} PDF is designed to be read as a standalone report. It summarizes the selected inventory and analytics context so the reader does not need to open the dashboard UI first. The report engine is domain-aware: KAORI Kubernetes Reports currently owns Kubernetes reports, while KAORI Server Reports is reserved for future VM and HCI reports.'
            ),
            styles['normal'],
        ),
        Spacer(
            1,
            0.25 * cm,
        ),
        build_key_value_table(
            overview_rows,
            styles,
        ),
        Spacer(
            1,
            0.25 * cm,
        ),
        build_status_banner(
            'Selected content',
            f'{len(sections)} section(s): {selected_sections}',
        ),
        Spacer(
            1,
            0.35 * cm,
        ),
        Paragraph(
            'Report Metadata',
            styles['section_title'],
        ),
        *build_metadata_table_body(
            report,
            styles,
        ),
        Spacer(
            1,
            0.35 * cm,
        ),
        *build_export_status_summary(
            report,
            styles,
        ),
    ]


def get_plain_language_report_goal(report_type: str) -> str:
    goals = {
        'analytics_overview': 'Gives a management-friendly summary of cluster health, resource posture, risk, and recommended follow-up.',
        'resource_utilization': 'Explains whether CPU, memory, storage, and pod capacity are being used normally or showing pressure.',
        'capacity_analysis': 'Explains whether the cluster still has enough worker capacity and schedulable headroom for future workload growth.',
        'storage_analysis': 'Explains storage consumption, persistent volume/PVC posture, and storage risks that may affect applications.',
        'workload_analysis': 'Explains whether workloads have healthy resource governance, including request and limit coverage.',
        'resource_forecast': 'Explains expected capacity pressure and growth direction so teams can plan before saturation happens.',
        'top_consumers': 'Identifies the namespaces, workloads, or pods that contribute most to resource consumption.',
        'alerts_anomalies': 'Summarizes alert and anomaly posture so teams can prioritize operational response.',
    }
    return goals.get(
        report_type,
        REPORT_TYPE_DESCRIPTIONS.get(
            report_type,
            'Summarizes Kubernetes operational context for review and follow-up.',
        ),
    )


def build_metadata_table(
    report: Report,
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    metadata = [
        [
            'Report ID',
            str(
                report.id,
            ),
        ],
        [
            'Report Type',
            REPORT_TYPE_LABELS.get(
                report.report_type,
                report.report_type,
            ),
        ],
        [
            'Cluster',
            report.cluster_id or 'All Clusters',
        ],
        [
            'Namespace',
            report.namespace or 'All Namespaces',
        ],
        [
            'Period',
            format_period(
                report.period,
            ),
        ],
        [
            'Output Format',
            report.output_format.upper(),
        ],
        [
            'Export Status',
            'Ready after generation',
        ],
        [
            'Selected Sections',
            str(
                len(
                    report.sections_as_list(),
                )
            ),
        ],
        [
            'Created At',
            format_datetime(
                report.created_at,
            ),
        ],
    ]

    return [
        Paragraph(
            'Report Metadata',
            styles['section_title'],
        ),
        *build_metadata_table_body(
            report,
            styles,
            metadata,
        ),
    ]


def build_metadata_table_body(
    report: Report,
    styles: dict[str, ParagraphStyle],
    metadata: list[list[Any]] | None = None,
) -> list[Any]:
    if metadata is None:
        metadata = [
            [
                'Report ID',
                str(
                    report.id,
                ),
            ],
            [
                'Report Domain',
                REPORT_DOMAIN_LABELS.get(
                    getattr(report, 'report_domain', ''),
                    'KAORI Kubernetes Reports',
                ),
            ],
            [
                'Source Kind',
                SOURCE_KIND_LABELS.get(
                    getattr(report, 'source_kind', ''),
                    'Kubernetes',
                ),
            ],
            [
                'Report Type',
                REPORT_TYPE_LABELS.get(
                    report.report_type,
                    report.report_type,
                ),
            ],
            [
                'Cluster',
                report.cluster_id or 'All Clusters',
            ],
            [
                'Namespace',
                report.namespace or 'All Namespaces',
            ],
            [
                'Period',
                format_period(
                    report.period,
                ),
            ],
            [
                'Output Format',
                report.output_format.upper(),
            ],
            [
                'Selected Sections',
                str(
                    len(
                        report.sections_as_list(),
                    )
                ),
            ],
        ]

    table = Table(
        metadata,
        colWidths=[
            4.2 * cm,
            12.0 * cm,
        ],
    )

    table.setStyle(
        default_metadata_table_style(),
    )

    return [
        table,
    ]


def build_export_status_summary(
    report: Report,
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    rows = [
        [
            'Stage',
            'Status',
            'Description',
        ],
        [
            'Request record',
            'Ready',
            'Report request metadata has been persisted in the database.',
        ],
        [
            'PDF renderer',
            'Active',
            'ReportLab renderer generated this structured PDF artifact.',
        ],
        [
            'Artifact storage',
            'Configured backend',
            'Generated artifact is saved through the active report storage backend.',
        ],
        [
            'Download readiness',
            'Ready after export',
            'Download is available after storage URI and file size metadata are updated.',
        ],
    ]

    table = Table(
        rows,
        colWidths=[
            4.0 * cm,
            3.5 * cm,
            8.7 * cm,
        ],
        repeatRows=1,
    )

    table.setStyle(
        default_grid_table_style(),
    )

    return [
        Paragraph(
            'Export Status Summary',
            styles['section_title'],
        ),
        table,
    ]


def build_report_type_summary(
    report: Report,
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    report_type = REPORT_TYPE_LABELS.get(
        report.report_type,
        report.report_type,
    )

    description = REPORT_TYPE_DESCRIPTIONS.get(
        report.report_type,
        'Kubernetes operational report generated by KAORI.',
    )

    data_integration_status = (
        'Connected to analytics service payload'
        if is_real_data_report(
            report,
        )
        else 'Prepared for analytics service payload integration in the next phase'
    )

    rows = [
        [
            'Report Type',
            report_type,
        ],
        [
            'Purpose',
            description,
        ],
        [
            'Rendering Mode',
            'Structured ReportLab renderer',
        ],
        [
            'Data Integration',
            data_integration_status,
        ],
    ]

    table = Table(
        rows,
        colWidths=[
            4.2 * cm,
            12.0 * cm,
        ],
    )

    table.setStyle(
        default_metadata_table_style(),
    )

    return [
        Paragraph(
            'Report Type Summary',
            styles['section_title'],
        ),
        table,
    ]


def build_sections_summary(
    report: Report,
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    story: list[Any] = [
        Paragraph(
            'Selected Report Sections',
            styles['section_title'],
        )
    ]

    sections = report.sections_as_list()

    if not sections:
        story.append(
            Paragraph(
                'No sections selected.',
                styles['normal'],
            )
        )
        return story

    real_data_sections = REAL_DATA_SECTION_MAP.get(
        report.report_type,
        set(),
    )

    section_rows = [
        [
            'No',
            'Section',
            'Renderer Status',
        ]
    ]

    for index, section in enumerate(
        sections,
        start=1,
    ):
        section_rows.append(
            [
                str(
                    index,
                ),
                SECTION_LABELS.get(
                    section,
                    section.replace(
                        '_',
                        ' ',
                    ).title(),
                ),
                'Real Data' if section in real_data_sections else 'Prepared',
            ]
        )

    table = Table(
        section_rows,
        colWidths=[
            1.4 * cm,
            10.8 * cm,
            4.0 * cm,
        ],
        repeatRows=1,
    )

    table.setStyle(
        default_grid_table_style(),
    )

    story.append(
        table,
    )

    return story


def build_sections_content(
    report: Report,
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    sections = report.sections_as_list()

    if not sections:
        return [
            Paragraph(
                'Section Content',
                styles['section_title'],
            ),
            Paragraph(
                'No section content was generated because this report request has no selected sections.',
                styles['normal'],
            ),
        ]

    story: list[Any] = [
        Paragraph(
            'Section Content',
            styles['section_title'],
        ),
        Paragraph(
            (
                'The following sections are rendered using structured placeholder content. '
                'Real metrics, tables, charts, and recommendations will be connected from '
                'Analytics services in the next implementation phase.'
            ),
            styles['normal'],
        ),
        Spacer(
            1,
            0.25 * cm,
        ),
    ]

    for section in sections:
        story.extend(
            build_single_section_content(
                section,
                styles,
            )
        )

    return story


def build_report_data_sections(
    report: Report,
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    if should_block_all_clusters_real_data_report(
        report,
    ):
        return build_single_cluster_required_section(
            report,
            styles,
        )

    if report.report_type == 'analytics_overview':
        return build_analytics_overview_pdf_sections(
            report,
            styles,
        )

    if report.report_type == 'resource_utilization':
        return build_resource_utilization_pdf_sections(
            report,
            styles,
        )

    if report.report_type == 'capacity_analysis':
        return build_capacity_analysis_pdf_sections(
            report,
            styles,
        )

    if report.report_type == 'storage_analysis':
        return build_storage_analysis_pdf_sections(
            report,
            styles,
        )

    if report.report_type == 'workload_analysis':
        return build_workload_analysis_pdf_sections(
            report,
            styles,
        )

    if report.report_type == 'resource_forecast':
        return build_resource_forecast_pdf_sections(
            report,
            styles,
        )

    if report.report_type == 'top_consumers':
        return build_top_consumers_pdf_sections(
            report,
            styles,
        )

    if report.report_type == 'alerts_anomalies':
        return build_alerts_anomalies_pdf_sections(
            report,
            styles,
        )

    return build_sections_content(
        report,
        styles,
    )


def build_single_cluster_required_section(
    report: Report,
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    report_type = REPORT_TYPE_LABELS.get(
        report.report_type,
        report.report_type,
    )

    rows = [
        [
            'Requested Scope',
            'All Clusters',
        ],
        [
            'Report Type',
            report_type,
        ],
        [
            'Current Status',
            'Single cluster required',
        ],
        [
            'Reason',
            (
                'This report type loads Prometheus-backed analytics from one selected cluster at a time. '
                'KAORI blocked silent fallback to a default cluster so the PDF does not show misleading data.'
            ),
        ],
        [
            'Required Action',
            'Regenerate this report with a specific cluster selected.',
        ],
        [
            'Supported All Clusters Report',
            REPORT_TYPE_LABELS.get(
                'analytics_overview',
                'Analytics Overview',
            ),
        ],
    ]

    return [
        Paragraph(
            'Single Cluster Required',
            styles['section_title'],
        ),
        Paragraph(
            (
                'This PDF was generated with All Clusters scope, but the selected report type '
                'currently requires a specific cluster for real-data rendering.'
            ),
            styles['normal'],
        ),
        Spacer(
            1,
            0.25 * cm,
        ),
        build_status_banner(
            'All Clusters blocked',
            (
                'To avoid incorrect output, KAORI did not fallback to the first/default cluster. '
                'Please select one cluster and regenerate the PDF.'
            ),
        ),
        Spacer(
            1,
            0.25 * cm,
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


def build_recommendation_block(
    report: Report,
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    recommendations = REPORT_TYPE_RECOMMENDATIONS.get(
        report.report_type,
        DEFAULT_RECOMMENDATIONS,
    )

    rows = [
        [
            'No',
            'Recommendation',
        ]
    ]

    for index, recommendation in enumerate(
        recommendations,
        start=1,
    ):
        rows.append(
            [
                str(
                    index,
                ),
                recommendation,
            ]
        )

    table = Table(
        rows,
        colWidths=[
            1.4 * cm,
            14.8 * cm,
        ],
        repeatRows=1,
    )

    table.setStyle(
        default_grid_table_style(),
    )

    return [
        Paragraph(
            'Operational Recommendations',
            styles['section_title'],
        ),
        table,
        Spacer(
            1,
            0.3 * cm,
        ),
        Paragraph(
            'Generated by KAORI Reports module.',
            styles['small'],
        ),
    ]

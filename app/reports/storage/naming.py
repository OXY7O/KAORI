from __future__ import annotations

import re
from datetime import UTC, datetime
from uuid import uuid4

from app.extensions.db import db
from app.models.cluster import Cluster
from app.models.report import Report
from app.reports.catalog import OUTPUT_FORMAT_SPECS, require_selected_cluster
from app.reports.reference import report_reference_filename

PERIOD_SLUGS = {
    '24h': 'last-24-hours',
    '7d': 'last-7-days',
    '30d': 'last-30-days',
    '90d': 'last-90-days',
    'month': 'this-month',
    'snapshot': 'current-snapshot',
}


_slug_pattern = re.compile(r'[^a-z0-9]+')


def slugify_storage_part(
    value: object,
    fallback: str = 'unknown',
) -> str:
    text = str(value or '').strip().lower()

    if not text:
        text = fallback

    text = text.replace('_', '-')
    text = _slug_pattern.sub('-', text)
    text = text.strip('-')

    return text or fallback


def get_report_domain_slug(
    report: Report,
) -> str:
    return slugify_storage_part(
        getattr(report, 'report_domain', None) or 'kubernetes',
        fallback='kubernetes',
    )


def get_report_source_kind_slug(
    report: Report,
) -> str:
    return slugify_storage_part(
        getattr(report, 'source_kind', None) or 'kubernetes',
        fallback='kubernetes',
    )


def get_report_cluster_slug(
    report: Report,
) -> str:
    require_selected_cluster(report)
    cluster_name = get_report_cluster_name(
        report,
    )

    return slugify_storage_part(
        cluster_name or report.cluster_id,
        fallback='unknown-cluster',
    )


def get_report_cluster_name(
    report: Report,
) -> str | None:
    cluster = getattr(
        report,
        'cluster',
        None,
    )

    if cluster is not None:
        name = getattr(
            cluster,
            'name',
            None,
        )

        if name:
            return str(
                name,
            )

    if not report.cluster_id:
        return None

    db_cluster = db.session.get(
        Cluster,
        report.cluster_id,
    )

    if db_cluster is None:
        return None

    return str(
        db_cluster.name,
    )


def get_report_type_slug(
    report: Report,
) -> str:
    return slugify_storage_part(
        report.report_type,
        fallback='report',
    )


def get_report_namespace_slug(
    report: Report,
) -> str:
    return slugify_storage_part(
        report.namespace or 'all-namespaces',
        fallback='all-namespaces',
    )


def get_report_period_slug(
    report: Report,
) -> str:
    period = report.period or '24h'

    return PERIOD_SLUGS.get(
        period,
        slugify_storage_part(
            period,
            fallback='period',
        ),
    )


def build_report_object_key(
    report: Report,
    generated_at: datetime | None = None,
) -> str:
    timestamp_dt = generated_at or datetime.now(
        UTC,
    )

    year = timestamp_dt.strftime(
        '%Y',
    )
    month = timestamp_dt.strftime(
        '%m',
    )
    timestamp = timestamp_dt.strftime(
        '%Y%m%d%H%M%S',
    )

    report_domain_slug = get_report_domain_slug(
        report,
    )
    source_kind_slug = get_report_source_kind_slug(
        report,
    )
    report_type_slug = get_report_type_slug(
        report,
    )
    cluster_slug = get_report_cluster_slug(
        report,
    )
    namespace_slug = get_report_namespace_slug(
        report,
    )
    period_slug = get_report_period_slug(
        report,
    )
    short_uuid = uuid4().hex[:8]
    report_reference = report_reference_filename(report, generated_at=timestamp_dt)

    output_format = str(getattr(report, 'output_format', '') or '').strip().lower()
    try:
        extension = OUTPUT_FORMAT_SPECS[output_format].extension
    except KeyError as exc:
        raise ValueError(f'Unsupported report output format: {output_format!r}.') from exc
    filename = f'{report_reference}-{cluster_slug}-{namespace_slug}-{period_slug}-{timestamp}-{short_uuid}{extension}'

    return '/'.join(
        [
            'reports',
            report_domain_slug,
            source_kind_slug,
            year,
            month,
            cluster_slug,
            report_type_slug,
            filename,
        ]
    )

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from time import monotonic
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import current_app
from sqlalchemy import case, func

from app.artifact_storage.service import StorageProfile, build_storage_profile
from app.common.celery_queue_health import get_queue_readiness
from app.models.archive import (
    ACTIVE_ARCHIVE_STATUSES,
    ARCHIVE_STATUS_CLEANUP_PARTIAL,
    ARCHIVE_STATUS_FAILED,
    ARCHIVE_STATUS_PURGE_FAILED,
    ARCHIVE_STATUS_READY,
    ArchiveArtifact,
)
from app.models.job import JobExecution
from app.models.lifecycle import DataLifecyclePolicy
from app.platform_operations.data_lifecycle.retention import generated_report_presentation as generated_report_ui
from app.platform_operations.data_lifecycle.retention import storage_presentation as storage_ui
from app.platform_operations.data_lifecycle.retention.domains import DOMAIN_FACTORIES, get_archive_domain
from app.platform_operations.data_lifecycle.retention.policy_service import (
    default_schedule_hour,
    default_schedule_minute,
    get_policy,
)
from app.platform_operations.data_lifecycle.retention.service import paginate_archives, preview_retention
from app.platform_operations.data_lifecycle.retention.types import RetentionPolicy

_ARCHIVE_PER_PAGE_OPTIONS = (5, 10, 25, 50)
_ARCHIVE_STATUS_OPTIONS = (
    'pending',
    'archiving',
    'verifying',
    'cleaning',
    'ready',
    'cleanup_partial',
    'failed',
    'purge_failed',
    'expired',
)
_ARCHIVE_TRIGGER_OPTIONS = ('manual', 'scheduled', 'cli')
_ARCHIVE_MODE_OPTIONS = ('archive_only', 'archive_and_cleanup')
_ARCHIVE_STORAGE_OPTIONS = ('local', 's3')
_STATUS_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}


def build_domain_retention_context(
    domain_name: str,
    *,
    include_preview: bool = False,
    feedback: dict[str, Any] | None = None,
    poll_once: bool = False,
    policy: RetentionPolicy | None = None,
    stored_policy: DataLifecyclePolicy | None = None,
) -> dict[str, Any]:
    domain = get_archive_domain(domain_name)
    effective_policy = policy or domain.build_policy()
    stored = stored_policy if stored_policy is not None else get_policy(domain.name)
    schedule_enabled, schedule_hour, schedule_minute, operation_mode = _policy_execution_settings(
        domain.name,
        effective_policy,
        stored,
    )
    schedule_timezone = str(current_app.config.get('CELERY_TIMEZONE', 'UTC') or 'UTC')
    scheduler_enabled = bool(current_app.config.get('DATA_LIFECYCLE_SCHEDULER_ENABLED', True))
    preview = preview_retention(domain.name) if include_preview else None
    archive_posture = _build_archive_posture(domain.name)
    worker = _cached_status('retention-worker', 12.0, _inspect_retention_worker)
    active_lifecycle_jobs = JobExecution.query.filter(
        JobExecution.job_type == 'data_lifecycle',
        JobExecution.scope_key == domain.name,
        JobExecution.status.in_(('queued', 'running', 'retrying', 'cancel_requested')),
    ).count()

    return {
        'domain': domain.name,
        'domain_label': _domain_label(domain.name),
        'domain_icon': _domain_icon(domain.name),
        'source_model': domain.source_model,
        'coverage': _domain_coverage(domain.name),
        'coverage_note': _domain_coverage_note(domain.name),
        'exclusion_note': _domain_exclusion_note(domain.name),
        'operation_mode': operation_mode,
        'enabled': bool(stored.enabled) if stored is not None else False,
        'retention_days': effective_policy.retention_days,
        'archive_retention_days': effective_policy.archive_retention_days,
        'batch_size': effective_policy.batch_size,
        'protect_unreviewed': effective_policy.protect_unreviewed,
        'protected_max_days': effective_policy.protected_max_days,
        'schedule_enabled': schedule_enabled,
        'schedule_hour': schedule_hour,
        'schedule_minute': schedule_minute,
        'schedule_timezone': schedule_timezone,
        'scheduler_enabled': scheduler_enabled,
        'next_schedule_label': _next_schedule_label(
            enabled=schedule_enabled and scheduler_enabled,
            hour=schedule_hour,
            minute=schedule_minute,
            timezone_name=schedule_timezone,
        ),
        'queue_name': str(current_app.config.get('RETENTION_CELERY_QUEUE', 'maintenance') or 'maintenance'),
        'worker': worker,
        'archive_format': 'JSONL.GZ + manifest JSON',
        'preview': _serialize_preview(preview) if preview is not None else None,
        'posture': archive_posture,
        'has_active_archives': archive_posture['active_count'] > 0,
        'active_lifecycle_jobs': int(active_lifecycle_jobs or 0),
        'feedback': feedback,
        'poll_once': bool(poll_once),
    }


def build_activity_retention_context(**kwargs) -> dict[str, Any]:
    return build_domain_retention_context('operational_activity', **kwargs)


def build_data_lifecycle_context(
    *,
    selected_domain: str = 'operational_activity',
    active_tab: str = 'policies',
    include_preview: bool = False,
    archive_page: int = 1,
    archive_per_page: int = 5,
    archive_status: str = 'all',
    archive_trigger: str = 'all',
    archive_mode: str = 'all',
    archive_storage: str = 'all',
    archive_search: str = '',
    archive_domain: str = 'all',
    feedback: dict[str, Any] | None = None,
    poll_once: bool = False,
) -> dict[str, Any]:
    supported = tuple(sorted(DOMAIN_FACTORIES))
    selected = selected_domain if selected_domain in supported else supported[0]
    active = active_tab if active_tab in {'policies', 'history', 'storage'} else 'policies'
    stored_map = {
        item.domain: item for item in DataLifecyclePolicy.query.filter(DataLifecyclePolicy.domain.in_(supported)).all()
    }
    posture_map = _build_domain_posture_summaries(supported)
    enabled_domain_count = sum(int(bool(stored_map[name].enabled)) for name in supported if name in stored_map)
    context: dict[str, Any] = {
        'active_tab': active,
        'selected_domain': selected,
        'managed_domain_count': len(supported),
        'enabled_domain_count': enabled_domain_count,
        'active_archive_total': sum(int(item['active_count']) for item in posture_map.values()),
        'failed_archive_total': sum(int(item['failed_count']) for item in posture_map.values()),
        'scheduler_enabled': bool(current_app.config.get('DATA_LIFECYCLE_SCHEDULER_ENABLED', True)),
        'feedback': feedback,
    }

    if active == 'policies':
        policies = {name: get_archive_domain(name).build_policy() for name in supported}
        selected_context = build_domain_retention_context(
            selected,
            include_preview=include_preview,
            feedback=feedback,
            poll_once=poll_once,
            policy=policies[selected],
            stored_policy=stored_map.get(selected),
        )
        selected_context['storage_contract'] = _build_selected_storage_contract(selected)
        selected_preview_count = (selected_context.get('preview') or {}).get('record_count')
        domain_cards = []
        for name in supported:
            policy = policies[name]
            stored = stored_map.get(name)
            schedule_enabled, schedule_hour, schedule_minute, operation_mode = _policy_execution_settings(
                name,
                policy,
                stored,
            )
            posture = posture_map.get(name, {'active_count': 0, 'failed_count': 0, 'total_archives': 0})
            domain_cards.append(
                {
                    'name': name,
                    'label': _domain_label(name),
                    'icon': _domain_icon(name),
                    'description': _domain_description(name),
                    'source_model': get_archive_domain(name).source_model,
                    'coverage': _domain_coverage(name),
                    'coverage_note': _domain_coverage_note(name),
                    'enabled': bool(stored.enabled) if stored is not None else False,
                    'hot_retention_days': policy.retention_days,
                    'archive_retention_days': policy.archive_retention_days,
                    'batch_size': policy.batch_size,
                    'operation_mode': operation_mode,
                    'schedule_enabled': schedule_enabled,
                    'schedule_hour': schedule_hour,
                    'schedule_minute': schedule_minute,
                    'eligible_count': selected_preview_count if name == selected else None,
                    'active_count': posture['active_count'],
                    'failed_count': posture['failed_count'],
                    'total_archives': posture['total_archives'],
                    'settings': dict(policy.settings or {}),
                }
            )
        selected_context.update(context)
        selected_context['domains'] = domain_cards
        return selected_context

    if active == 'history':
        history_filters = _normalize_archive_filters(
            status=archive_status,
            trigger_type=archive_trigger,
            operation_mode=archive_mode,
            storage_backend=archive_storage,
            search=archive_search,
        )
        history_domain = archive_domain if archive_domain in supported else 'all'
        history_pagination = paginate_archives(
            domain_name=None if history_domain == 'all' else history_domain,
            page=archive_page,
            per_page=archive_per_page,
            status=history_filters['status'],
            trigger_type=history_filters['trigger_type'],
            operation_mode=history_filters['operation_mode'],
            storage_backend=history_filters['storage_backend'],
            search=history_filters['search'],
        )
        total = int(history_pagination.total or 0)
        context.update(
            {
                'history_archives': [
                    _serialize_archive(item)
                    | {
                        'domain': item.domain,
                        'domain_label': _domain_label(item.domain),
                        'domain_icon': _domain_icon(item.domain),
                    }
                    for item in history_pagination.items
                ],
                'history_filters': history_filters | {'domain': history_domain},
                'history_filter_options': {
                    'domains': tuple({'value': name, 'label': _domain_label(name)} for name in supported),
                    'statuses': _ARCHIVE_STATUS_OPTIONS,
                    'triggers': _ARCHIVE_TRIGGER_OPTIONS,
                    'modes': _ARCHIVE_MODE_OPTIONS,
                    'storage_backends': _ARCHIVE_STORAGE_OPTIONS,
                },
                'history_pagination': {
                    'page': history_pagination.page,
                    'pages': max(int(history_pagination.pages or 0), 1),
                    'per_page': history_pagination.per_page,
                    'total': total,
                    'start_item': ((history_pagination.page - 1) * history_pagination.per_page + 1) if total else 0,
                    'end_item': min(history_pagination.page * history_pagination.per_page, total),
                    'has_prev': history_pagination.has_prev,
                    'has_next': history_pagination.has_next,
                    'prev_num': history_pagination.prev_num,
                    'next_num': history_pagination.next_num,
                    'allowed_per_page': _ARCHIVE_PER_PAGE_OPTIONS,
                },
            }
        )
        return context

    storage_profile = build_storage_profile('archive')
    last_verified = _latest_verified_archive_for_profile(storage_profile, supported)
    context.update(
        {
            'storage': storage_ui.build_storage_context(storage_profile, last_verified),
            'worker': _cached_status('retention-worker', 12.0, _inspect_retention_worker),
            'queue_name': str(current_app.config.get('RETENTION_CELERY_QUEUE', 'maintenance') or 'maintenance'),
            'archive_format': 'JSONL.GZ + manifest JSON',
            'purge_batch_size': max(
                25,
                min(int(current_app.config.get('ARCHIVE_PURGE_BATCH_SIZE', 250) or 250), 2500),
            ),
        }
    )
    return context


def _policy_execution_settings(
    domain_name: str,
    policy: RetentionPolicy,
    stored: DataLifecyclePolicy | None,
) -> tuple[bool, int, int, str]:
    if stored is not None:
        return (
            bool(stored.schedule_enabled),
            int(stored.schedule_hour),
            int(stored.schedule_minute),
            str(stored.operation_mode or 'archive_and_cleanup'),
        )
    return (
        False,
        default_schedule_hour(domain_name),
        default_schedule_minute(domain_name),
        'archive_and_cleanup',
    )


def _latest_verified_archive_for_profile(
    profile: StorageProfile,
    domain_names: tuple[str, ...],
) -> ArchiveArtifact | None:
    candidates = (
        ArchiveArtifact.query.filter(
            ArchiveArtifact.domain.in_(domain_names),
            ArchiveArtifact.storage_backend == profile.backend,
            ArchiveArtifact.status.in_([ARCHIVE_STATUS_READY, ARCHIVE_STATUS_CLEANUP_PARTIAL]),
            ArchiveArtifact.verified_at.is_not(None),
        )
        .order_by(ArchiveArtifact.verified_at.desc(), ArchiveArtifact.id.desc())
        .yield_per(100)
    )
    return next((item for item in candidates if storage_ui.artifact_matches_storage_profile(item, profile)), None)


def _domain_label(name: str) -> str:
    return {
        'operational_activity': 'Activity Audit',
        'job_execution': 'Job Executions',
        'runtime_observation': 'Runtime Observations',
        'analytics_snapshot': 'Analytics Snapshots',
        'generated_report': generated_report_ui.GENERATED_REPORT_LABEL,
        'alert_incident': 'Alert Incidents',
    }.get(name, name.replace('_', ' ').title())


def _domain_icon(name: str) -> str:
    return {
        'operational_activity': 'scroll-text',
        'job_execution': 'workflow',
        'runtime_observation': 'activity',
        'analytics_snapshot': 'chart-no-axes-combined',
        'generated_report': generated_report_ui.GENERATED_REPORT_ICON,
        'alert_incident': 'siren',
    }.get(name, 'database')


def _domain_description(name: str) -> str:
    return {
        'operational_activity': 'Activity Audit and persistent user notifications.',
        'job_execution': 'Canonical queue, progress, results, and worker metadata.',
        'runtime_observation': 'Kubernetes, Object Storage, Metrics Source, and Alertmanager runtime evidence.',
        'analytics_snapshot': 'Reusable analytics and forecast materialization snapshots.',
        'generated_report': generated_report_ui.GENERATED_REPORT_DESCRIPTION,
        'alert_incident': 'Closed Alert Operations cases, operator evidence, notification delivery, and postmortem records.',
    }.get(name, 'KAORI operational data domain.')


def _domain_coverage(name: str) -> tuple[dict[str, str], ...]:
    return {
        'operational_activity': (
            {
                'icon': 'scroll-text',
                'label': 'Activity Audit Table',
                'description': 'All persisted administrative and operational activity records.',
            },
            {
                'icon': 'bell',
                'label': 'Notification Center',
                'description': 'Persistent user-targeted notifications share the same source table.',
            },
            {
                'icon': 'shield-check',
                'label': 'Authentication Audit',
                'description': 'Authentication events remain lifecycle-managed with the audit stream.',
            },
        ),
        'job_execution': (
            {
                'icon': 'workflow',
                'label': 'Jobs & Executions',
                'description': 'Terminal execution records, subscribers, results, and worker evidence.',
            },
        ),
        'runtime_observation': (
            {
                'icon': 'boxes',
                'label': 'Kubernetes',
                'description': 'Recent Runtime Observations for Kubernetes integration targets.',
            },
            {
                'icon': 'gauge',
                'label': 'Metrics Source',
                'description': 'Recent runtime observations for registered Metrics Sources.',
            },
            {
                'icon': 'bell-ring',
                'label': 'Alertmanager',
                'description': 'Recent Runtime Observations for Alertmanager integration targets.',
            },
            {
                'icon': 'database',
                'label': 'Object Storage · MinIO',
                'description': 'Recent Runtime Observations for managed MinIO Object Storage integration targets.',
            },
        ),
        'generated_report': generated_report_ui.GENERATED_REPORT_COVERAGE,
        'alert_incident': (
            {
                'icon': 'siren',
                'label': 'Closed Alert Cases',
                'description': 'Verified closed cases retain searchable identity while heavy evidence moves to governed archive storage.',
            },
            {
                'icon': 'list-tree',
                'label': 'Incident Timeline',
                'description': 'Detection, acknowledgement, assignment, silence, remediation, source resolution, and closure evidence.',
            },
            {
                'icon': 'send',
                'label': 'Notification Delivery',
                'description': 'Firing and resolved channel-delivery evidence is preserved with the incident archive.',
            },
            {
                'icon': 'file-text',
                'label': 'Postmortem Evidence',
                'description': 'Required or completed postmortem context and action-item evidence remain part of the case record.',
            },
        ),
        'analytics_snapshot': (
            {
                'icon': 'chart-spline',
                'label': 'Analytics Materialization',
                'description': 'Capacity, utilization, storage, workload, top-consumer, and alert datasets.',
            },
            {
                'icon': 'line-chart',
                'label': 'Forecast History',
                'description': 'Reusable forecast snapshots stored in the shared analytics snapshot table.',
            },
            {
                'icon': 'layout-dashboard',
                'label': 'Dashboard Evidence',
                'description': 'Shared materialized alert evidence reused by Kubernetes dashboards.',
            },
        ),
    }.get(name, ())


def _domain_coverage_note(name: str) -> str | None:
    return {
        'operational_activity': 'One retention policy governs the shared notifications table; the user inbox and Activity Audit are different views over the same persisted records.',
        'job_execution': 'Execution payloads remain domain-owned; lifecycle archives canonical execution metadata and result references.',
        'runtime_observation': 'The policy is provider-neutral. Kubernetes, Object Storage, Metrics Source, Alertmanager, and future integrations using IntegrationRuntimeObservation share the same lifecycle boundary.',
        'analytics_snapshot': 'Cleanup applies only after a snapshot is outside both its stale-serve window and the configured hot-retention boundary.',
        'generated_report': generated_report_ui.GENERATED_REPORT_COVERAGE_NOTE,
        'alert_incident': 'Only Closed cases are archive-eligible. KAORI preserves the case index in PostgreSQL for History search after evidence compaction.',
    }.get(name)


def _domain_exclusion_note(name: str) -> str | None:
    return {
        'operational_activity': 'Transient toasts are not persisted and therefore are not lifecycle-managed.',
        'job_execution': 'Domain datasets referenced by a job are not deleted by the Job Executions retention policy.',
        'runtime_observation': 'Full provider configuration and credentials are not part of runtime-observation archives.',
        'analytics_snapshot': 'Pending or still-serveable snapshots are protected from archive cleanup.',
        'generated_report': generated_report_ui.GENERATED_REPORT_EXCLUSION_NOTE,
        'alert_incident': 'Open, acknowledged, mitigating, and verification-pending cases are never selected for archive cleanup.',
    }.get(name)


def _build_selected_storage_contract(name: str) -> dict[str, Any]:
    profile = build_storage_profile('archive')
    return _domain_storage_contract(
        name,
        source_model=get_archive_domain(name).source_model,
        archive_storage=storage_ui.build_storage_contract_context(profile),
    )


def _domain_storage_contract(
    name: str,
    *,
    source_model: str,
    archive_storage: dict[str, Any],
) -> dict[str, Any]:
    source_label = 'PostgreSQL'
    source_detail = source_model
    archive_content = 'JSONL.GZ data + manifest JSON'
    archive_detail = 'Structured lifecycle evidence only; no provider credentials or binary supplements.'

    if name == 'generated_report':
        source_label = 'PostgreSQL + Reports Artifact Storage'
        source_detail = 'reports metadata plus retained PDF, XLSX, or CSV artifacts'
        archive_content = 'JSONL.GZ + manifest + report artifacts'
        archive_detail = 'Ready and manually Archived report binaries are copied and checksum-verified.'
    elif name == 'runtime_observation':
        archive_detail = 'Provider-neutral runtime evidence uses the shared archive target; no integration-specific archive bucket is created.'
    elif name == 'analytics_snapshot':
        archive_detail = (
            'Materialized analytics payloads are archived as structured evidence after serve-window protection ends.'
        )
    elif name == 'job_execution':
        archive_detail = (
            'Execution metadata and result references are archived; domain-owned result datasets are not copied.'
        )
    elif name == 'operational_activity':
        archive_detail = 'Activity and persistent notification evidence share the same structured archive bundle.'
    elif name == 'alert_incident':
        archive_detail = (
            'Closed alert-case evidence is stored as JSONL.GZ plus manifest and checksum; the searchable case index remains in PostgreSQL.'
        )

    return {
        'hot_source_label': source_label,
        'hot_source_detail': source_detail,
        'archive_provider_label': archive_storage['provider_label'],
        'archive_location': archive_storage['location'],
        'archive_content': archive_content,
        'archive_detail': archive_detail,
    }


def _normalize_archive_filters(
    *,
    status: str,
    trigger_type: str,
    operation_mode: str,
    storage_backend: str,
    search: str,
) -> dict[str, str]:
    normalized_status = status if status in _ARCHIVE_STATUS_OPTIONS else 'all'
    normalized_trigger = trigger_type if trigger_type in _ARCHIVE_TRIGGER_OPTIONS else 'all'
    normalized_mode = operation_mode if operation_mode in _ARCHIVE_MODE_OPTIONS else 'all'
    normalized_storage = storage_backend if storage_backend in _ARCHIVE_STORAGE_OPTIONS else 'all'
    return {
        'status': normalized_status,
        'trigger_type': normalized_trigger,
        'operation_mode': normalized_mode,
        'storage_backend': normalized_storage,
        'search': str(search or '').strip(),
    }


def _build_domain_posture_summaries(domain_names: tuple[str, ...]) -> dict[str, dict[str, int]]:
    rows = (
        ArchiveArtifact.query.filter(ArchiveArtifact.domain.in_(domain_names))
        .with_entities(
            ArchiveArtifact.domain,
            func.count(ArchiveArtifact.id),
            func.sum(case((ArchiveArtifact.status.in_(tuple(ACTIVE_ARCHIVE_STATUSES)), 1), else_=0)),
            func.sum(
                case(
                    (ArchiveArtifact.status.in_((ARCHIVE_STATUS_FAILED, ARCHIVE_STATUS_PURGE_FAILED)), 1),
                    else_=0,
                )
            ),
        )
        .group_by(ArchiveArtifact.domain)
        .all()
    )
    return {
        str(domain): {
            'total_archives': int(total or 0),
            'active_count': int(active or 0),
            'failed_count': int(failed or 0),
        }
        for domain, total, active, failed in rows
    }


def _build_archive_posture(domain_name: str) -> dict[str, Any]:
    domain_query = ArchiveArtifact.query.filter(ArchiveArtifact.domain == domain_name)
    last_run = domain_query.order_by(
        ArchiveArtifact.created_at.desc(),
        ArchiveArtifact.id.desc(),
    ).first()
    last_verified = (
        domain_query.filter(
            ArchiveArtifact.status.in_([ARCHIVE_STATUS_READY, ARCHIVE_STATUS_CLEANUP_PARTIAL]),
            ArchiveArtifact.verified_at.is_not(None),
        )
        .order_by(
            ArchiveArtifact.verified_at.desc(),
            ArchiveArtifact.id.desc(),
        )
        .first()
    )
    aggregate = domain_query.with_entities(
        func.count(ArchiveArtifact.id).label('total_archives'),
        func.sum(case((ArchiveArtifact.status.in_(tuple(ACTIVE_ARCHIVE_STATUSES)), 1), else_=0)).label('active_count'),
        func.sum(
            case((ArchiveArtifact.status.in_((ARCHIVE_STATUS_FAILED, ARCHIVE_STATUS_PURGE_FAILED)), 1), else_=0)
        ).label('failed_count'),
        func.coalesce(
            func.sum(
                case(
                    (
                        ArchiveArtifact.status.in_([ARCHIVE_STATUS_READY, ARCHIVE_STATUS_CLEANUP_PARTIAL]),
                        ArchiveArtifact.size_bytes,
                    ),
                    else_=0,
                )
            ),
            0,
        ).label('stored_bytes'),
    ).one()
    stored_bytes = int(aggregate.stored_bytes or 0)

    return {
        'total_archives': int(aggregate.total_archives or 0),
        'active_count': int(aggregate.active_count or 0),
        'failed_count': int(aggregate.failed_count or 0),
        'stored_bytes': stored_bytes,
        'stored_size_label': _format_size(int(stored_bytes)),
        'last_run': _serialize_last_run(last_run),
        'last_verified': last_verified,
        'last_verified_at': last_verified.verified_at if last_verified else None,
    }


def _serialize_last_run(artifact: ArchiveArtifact | None) -> dict[str, Any] | None:
    if artifact is None:
        return None
    return {
        'id': artifact.id,
        'status': artifact.status,
        'trigger_type': artifact.trigger_type,
        'operation_mode': artifact.operation_mode,
        'record_count': artifact.record_count,
        'cleanup_deleted_count': artifact.cleanup_deleted_count,
        'created_at': artifact.created_at,
        'completed_at': artifact.completed_at,
    }


def _serialize_preview(preview: dict[str, Any]) -> dict[str, Any]:
    boundary = preview['boundary']
    return {
        'record_count': boundary.record_count,
        'selected_at': boundary.selected_at,
        'cutoff_at': boundary.cutoff_at,
        'range_start': boundary.range_start,
        'range_end': boundary.range_end,
        'maximum_record_id': boundary.maximum_record_id,
        'protected_record_count': boundary.protected_record_count,
        'estimated_uncompressed_bytes': preview['estimated_uncompressed_bytes'],
        'estimated_size_label': _format_size(preview['estimated_uncompressed_bytes']),
    }


def _serialize_archive(artifact: ArchiveArtifact) -> dict[str, Any]:
    metadata = artifact.metadata_json or {}
    storage_locator = metadata.get('storage_locator') if isinstance(metadata, dict) else None
    return {
        'id': artifact.id,
        'short_id': artifact.id.split('-')[0],
        'status': artifact.status,
        'trigger_type': artifact.trigger_type,
        'operation_mode': artifact.operation_mode,
        'record_count': artifact.record_count,
        'cleanup_deleted_count': artifact.cleanup_deleted_count,
        'storage_backend': artifact.storage_backend,
        'storage_label': storage_ui.archive_storage_label(artifact.storage_backend, storage_locator),
        'size_bytes': int(artifact.size_bytes or 0) + int(metadata.get('supplemental_size_bytes') or 0),
        'size_label': _format_size(int(artifact.size_bytes or 0) + int(metadata.get('supplemental_size_bytes') or 0)),
        'supplemental_count': len(metadata.get('supplemental_artifacts') or []),
        'checksum_sha256': artifact.checksum_sha256,
        'checksum_short': artifact.checksum_sha256[:12] if artifact.checksum_sha256 else None,
        'range_start': artifact.range_start,
        'range_end': artifact.range_end,
        'created_at': artifact.created_at,
        'completed_at': artifact.completed_at,
        'verified_at': artifact.verified_at,
        'error_message': artifact.error_message,
        'error_summary': _archive_error_summary(artifact.error_message),
        'celery_task_id': artifact.celery_task_id,
        'is_downloadable': artifact.is_downloadable,
        'is_verifiable': artifact.is_verifiable,
    }


def _inspect_retention_worker() -> dict[str, Any]:
    queue_name = str(current_app.config.get('RETENTION_CELERY_QUEUE', 'inventory') or 'inventory')
    state = get_queue_readiness(queue_name)
    tone = {
        'normal': 'emerald',
        'warning': 'amber',
        'critical': 'rose',
        'unknown': 'slate',
    }.get(str(state['tone']), 'slate')
    return {
        'status': state['status'],
        'label': state['label'],
        'tone': tone,
        'count': state['worker_count'],
        'queue_ready': state['ready'],
        'detail': state['description'],
        'worker_names': state['worker_names'],
    }


def _cached_status(
    key: str,
    ttl_seconds: float,
    loader: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    now = monotonic()
    cached = _STATUS_CACHE.get(key)
    if cached and now - cached[0] < ttl_seconds:
        return dict(cached[1])
    value = loader()
    _STATUS_CACHE[key] = (now, dict(value))
    return value


def _next_schedule_label(
    *,
    enabled: bool,
    hour: int,
    minute: int,
    timezone_name: str,
) -> str | None:
    if not enabled:
        return None
    try:
        timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        timezone = UTC
    now = datetime.now(timezone)
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate.strftime('%d %b %Y %H:%M %Z')


def _archive_error_summary(message: str | None) -> str | None:
    normalized = str(message or '').strip()
    if not normalized:
        return None

    lowered = normalized.lower()
    if (
        'endpointconnectionerror' in lowered
        or 'could not connect to the endpoint' in lowered
        or 'connection refused' in lowered
        or 'connection timed out' in lowered
        or 'gaierror' in lowered
        or 'name or service not known' in lowered
    ):
        return 'Archive storage could not be reached.'
    if 'checksum' in lowered:
        return 'Archive verification failed.'
    if 'access denied' in lowered or 'forbidden' in lowered or 'permission' in lowered:
        return 'Archive storage access was denied.'
    if 'size verification failed' in lowered or 'size mismatch' in lowered:
        return 'Archive size verification failed.'

    return 'Archive lifecycle failed. Review Activity Audit Log for details.'


def _format_size(value: int | None) -> str:
    size = float(value or 0)
    units = ('B', 'KB', 'MB', 'GB', 'TB')
    unit = units[0]
    for unit in units:
        if size < 1024 or unit == units[-1]:
            break
        size /= 1024
    return f'{size:.1f} {unit}' if unit != 'B' else f'{int(size)} B'

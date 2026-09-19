from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from werkzeug.datastructures import ImmutableMultiDict, MultiDict

from app.common.celery_queue_health import get_queue_readiness
from app.common.inventory_generation import filter_current_generation
from app.extensions.db import db
from app.models.cluster import Cluster
from app.models.inventory import NamespaceInventory
from app.models.object_storage import ObjectStorageSystem
from app.models.report import Report
from app.models.user import User
from app.reports.catalog import (
    OUTPUT_FORMAT_OPTIONS,
    REPORT_TYPE_OPTIONS,
    REQUIRES_SELECTED_CLUSTER_REPORT_TYPES,
    get_allowed_output_formats,
    get_default_output_format,
    get_report_type_spec,
)
from app.reports.catalog import (
    normalize_report_type as normalize_catalog_report_type,
)
from app.reports.generate.form_options import PERIOD_OPTIONS, SECTION_OPTIONS
from app.reports.jobs.queue import get_reports_queue_name
from app.reports.scope import (
    KUBERNETES_CLUSTER_ASSET_TYPE,
    OBJECT_STORAGE_SYSTEM_ASSET_TYPE,
    get_report_namespace_options_by_cluster,
)
from app.reports.storage.service import get_configured_storage_backend_name, get_report_storage_backend_status


def report_requires_selected_cluster(
    report_type: str,
) -> bool:
    return report_type in REQUIRES_SELECTED_CLUSTER_REPORT_TYPES


def _get_section_option_map() -> dict[str, dict[str, str]]:
    return {item['value']: item for item in SECTION_OPTIONS}


def _get_section_options_for_report_type(
    report_type: str,
) -> list[dict[str, str]]:
    section_option_map = _get_section_option_map()

    return [
        section_option_map[section]
        for section in _get_default_sections(
            report_type,
        )
        if section in section_option_map
    ]


def _get_section_options_by_report_type() -> dict[str, list[dict[str, str]]]:
    return {
        item['value']: _get_section_options_for_report_type(
            item['value'],
        )
        for item in REPORT_TYPE_OPTIONS
    }


def _get_selected_section_options(
    report_type: str,
    sections: list[str],
) -> list[dict[str, str]]:
    section_option_map = _get_section_option_map()
    allowed_sections = _get_allowed_sections_for_report_type(
        report_type,
    )

    return [
        section_option_map[section]
        for section in sections
        if section in allowed_sections and section in section_option_map
    ]


def _get_default_sections_by_report_type() -> dict[str, list[str]]:
    return {
        item['value']: list(
            item['default_sections'],
        )
        for item in REPORT_TYPE_OPTIONS
    }


def _get_allowed_sections_for_report_type(
    report_type: str,
) -> set[str]:
    return set(
        _get_default_sections(
            report_type,
        )
    )


def get_generate_report_payload(
    form_state: dict[str, Any] | None = None,
    errors: list[str] | None = None,
) -> dict[str, Any]:
    default_report_type = REPORT_TYPE_OPTIONS[0]['value']

    if form_state is None:
        form_state = build_default_form_state(
            report_type=default_report_type,
        )

    storage_context = _get_storage_generation_context()
    worker_context = get_queue_readiness(get_reports_queue_name())
    selected_report_type = _get_report_type_context(
        form_state['report_type'],
    )
    cluster_options = _get_cluster_options()
    object_storage_system_options = _get_object_storage_system_options()
    namespace_options_by_cluster = _get_namespace_options_by_cluster()
    scope_ready = _scope_is_ready(form_state, selected_report_type)

    return {
        'page_title': 'Generate Report',
        'page_subtitle': (
            'Build governed reports from connected data and approved formats. Analytics: PDF/XLSX/CSV · Inventory: XLSX/CSV.'
        ),
        'clusters': cluster_options,
        'has_clusters': bool(cluster_options),
        'object_storage_systems': object_storage_system_options,
        'has_object_storage_systems': bool(object_storage_system_options),
        'scope_ready': scope_ready,
        'namespace_options_by_cluster': namespace_options_by_cluster,
        'selected_namespace_options': namespace_options_by_cluster.get(
            str(form_state.get('cluster_id') or ''),
            [],
        ),
        'report_type_options': REPORT_TYPE_OPTIONS,
        'report_type_groups': _get_report_type_groups(),
        'period_options': PERIOD_OPTIONS,
        'output_format_options': OUTPUT_FORMAT_OPTIONS,
        'section_options': SECTION_OPTIONS,
        'section_options_by_report_type': _get_section_options_by_report_type(),
        'default_sections_by_report_type': _get_default_sections_by_report_type(),
        'selected_section_options': _get_selected_section_options(
            form_state['report_type'],
            form_state['sections'],
        ),
        'selected_report_type': selected_report_type,
        'single_cluster_required_report_types': sorted(
            REQUIRES_SELECTED_CLUSTER_REPORT_TYPES,
        ),
        'form_state': form_state,
        'preview_report_name': form_state['name'].strip() or build_default_report_name(form_state),
        'errors': errors or [],
        'storage_context': storage_context,
        'generation_allowed': bool(storage_context.get('ready', False)),
        'worker_context': worker_context,
    }


def create_report_request(
    form: MultiDict[str, str] | ImmutableMultiDict[str, str],
    user_id: int | None,
) -> tuple[bool, list[str], Report | None]:
    form_state = get_form_state_from_form(
        form,
    )

    errors = validate_form_state(
        form_state,
    )

    if errors:
        return False, errors, None

    storage_status = get_report_storage_backend_status()
    if not bool(storage_status.get('write_available', False)):
        return (
            False,
            [
                'Artifact storage is unavailable. Report metadata remains accessible, but new report generation is paused until storage connectivity is restored.'
            ],
            None,
        )

    report_spec = get_report_type_spec(form_state['report_type'])
    cluster_id = _parse_cluster_id(form_state['cluster_id']) if report_spec.requires_cluster else None
    object_storage_system_id = (form_state.get('object_storage_system_id') or '').strip()

    report_name = form_state['name'].strip()

    if not report_name:
        report_name = build_default_report_name(
            form_state,
        )

    namespace = form_state['namespace'].strip() or None if report_spec.requires_cluster else None

    report = Report()
    report.name = report_name
    report.report_type = form_state['report_type']
    report.report_domain = report_spec.domain
    report.source_kind = report_spec.source_kind
    report.cluster_id = cluster_id
    report.namespace = namespace
    report.scope_asset_type = report_spec.scope_asset_type
    if report_spec.scope_asset_type == OBJECT_STORAGE_SYSTEM_ASSET_TYPE:
        system = db.session.get(ObjectStorageSystem, object_storage_system_id)
        report.scope_asset_id = object_storage_system_id
        report.scope_asset_label_snapshot = system.name if system is not None else object_storage_system_id
    else:
        cluster = db.session.get(Cluster, cluster_id) if cluster_id else None
        report.scope_asset_id = cluster_id
        report.scope_asset_label_snapshot = cluster.name if cluster is not None else cluster_id
    report.period = form_state['period']
    report.output_format = form_state['output_format']
    report.status = 'requested'
    report.sections = form_state['sections']
    report.generated_by_id = user_id

    if user_id is not None:
        user = db.session.get(
            User,
            user_id,
        )

        if user is not None:
            report.generated_by_username_snapshot = user.username
            report.generated_by_display_name_snapshot = user.display_label
            report.generated_by_auth_source_snapshot = user.auth_source

    report.file_path = None
    report.file_size_bytes = None
    report.error_message = None

    db.session.add(
        report,
    )
    db.session.commit()

    return True, [], report


def build_default_form_state(
    *,
    report_type: str | None = None,
) -> dict[str, Any]:
    normalized_report_type = normalize_report_type(
        report_type,
    )

    return {
        'name': '',
        'cluster_id': '',
        'namespace': '',
        'object_storage_system_id': '',
        'report_type': normalized_report_type,
        'period': _get_default_period(normalized_report_type),
        'output_format': get_report_primary_output_format(normalized_report_type),
        'sections': _get_default_sections(
            normalized_report_type,
        ),
    }


def get_report_primary_output_format(report_type: str) -> str:
    return get_default_output_format(normalize_report_type(report_type))


def get_report_allowed_output_formats(report_type: str) -> tuple[str, ...]:
    return get_allowed_output_formats(normalize_report_type(report_type))


def normalize_report_type(
    value: str | None,
) -> str:
    return normalize_catalog_report_type(value)


def _get_report_type_groups() -> list[dict[str, Any]]:
    domain_labels = {
        'kubernetes': 'Kubernetes',
        'object_storage': 'Object Storage',
    }
    family_labels = {
        'analytics': 'Analytics',
        'inventory': 'Inventory',
    }
    groups: list[dict[str, Any]] = []
    group_indexes: dict[tuple[str, str], int] = {}

    for item in REPORT_TYPE_OPTIONS:
        domain = str(item.get('domain') or 'kubernetes')
        family = str(item.get('family') or 'analytics')
        group_key = (domain, family)
        if group_key not in group_indexes:
            domain_label = domain_labels.get(domain, domain.replace('_', ' ').title())
            family_label = family_labels.get(family, family.replace('_', ' ').title())
            group_indexes[group_key] = len(groups)
            groups.append(
                {
                    'key': f'{domain}:{family}',
                    'label': f'{domain_label} · {family_label}',
                    'domain': domain,
                    'family': family,
                    'options': [],
                }
            )
        groups[group_indexes[group_key]]['options'].append(item)

    return groups


def _get_report_type_context(
    report_type: str,
) -> dict[str, Any]:
    normalized_report_type = normalize_report_type(
        report_type,
    )

    for item in REPORT_TYPE_OPTIONS:
        if item['value'] == normalized_report_type:
            return {
                'value': item['value'],
                'label': item['label'],
                'description': item['description'],
                'icon': item['icon'],
                'section_count': len(
                    item['default_sections'],
                ),
                'family': str(item['family']),
                'primary_format': str(item['primary_format']),
                'allowed_formats': list(item['allowed_formats']),
                'domain': str(item.get('domain') or 'kubernetes'),
                'source_kind': str(item.get('source_kind') or item.get('domain') or 'kubernetes'),
                'scope_asset_type': str(item.get('scope_asset_type') or KUBERNETES_CLUSTER_ASSET_TYPE),
                'requires_cluster': report_requires_selected_cluster(item['value']),
                'scope_label': (
                    'Object Storage System'
                    if item.get('scope_asset_type') == OBJECT_STORAGE_SYSTEM_ASSET_TYPE
                    else 'Kubernetes Cluster'
                ),
                'cluster_scope_label': (
                    'Object Storage System Required'
                    if item.get('scope_asset_type') == OBJECT_STORAGE_SYSTEM_ASSET_TYPE
                    else 'Selected Cluster Required'
                ),
            }

    fallback = REPORT_TYPE_OPTIONS[0]

    return {
        'value': fallback['value'],
        'label': fallback['label'],
        'description': fallback['description'],
        'icon': fallback['icon'],
        'section_count': len(
            fallback['default_sections'],
        ),
        'family': str(fallback['family']),
        'primary_format': str(fallback['primary_format']),
        'allowed_formats': list(fallback['allowed_formats']),
        'domain': str(fallback.get('domain') or 'kubernetes'),
        'source_kind': str(fallback.get('source_kind') or fallback.get('domain') or 'kubernetes'),
        'scope_asset_type': str(fallback.get('scope_asset_type') or KUBERNETES_CLUSTER_ASSET_TYPE),
        'requires_cluster': report_requires_selected_cluster(fallback['value']),
        'scope_label': (
            'Object Storage System'
            if fallback.get('scope_asset_type') == OBJECT_STORAGE_SYSTEM_ASSET_TYPE
            else 'Kubernetes Cluster'
        ),
        'cluster_scope_label': (
            'Object Storage System Required'
            if fallback.get('scope_asset_type') == OBJECT_STORAGE_SYSTEM_ASSET_TYPE
            else 'Selected Cluster Required'
        ),
    }


def _get_storage_generation_context() -> dict[str, Any]:
    try:
        backend_name = get_configured_storage_backend_name()
        backend_status = get_report_storage_backend_status(backend_name)
        is_ready = bool(backend_status.get('write_available', False))
        return {
            'backend': backend_name,
            'label': str(backend_status.get('label') or 'Report storage'),
            'status': str(backend_status.get('status') or 'Needs Review'),
            'tone': str(backend_status.get('tone') or ('blue' if is_ready else 'amber')),
            'description': str(backend_status.get('description') or ''),
            'ready': is_ready,
            'state': str(backend_status.get('state') or 'unknown'),
            'checked_at': backend_status.get('checked_at'),
            'source': str(backend_status.get('source') or 'direct'),
        }
    except Exception:
        return {
            'backend': 'unknown',
            'label': 'Storage backend',
            'status': 'Needs Review',
            'tone': 'amber',
            'description': 'Storage readiness could not be evaluated. Review Reports Storage and server logs.',
            'ready': False,
            'state': 'unknown',
            'checked_at': None,
            'source': 'fallback',
        }


def get_form_state_from_form(
    form: MultiDict[str, str] | ImmutableMultiDict[str, str],
) -> dict[str, Any]:
    report_type = normalize_report_type(
        form.get(
            'report_type',
            REPORT_TYPE_OPTIONS[0]['value'],
        )
    )

    sections = form.getlist(
        'sections',
    )

    if not sections:
        sections = _get_default_sections(
            report_type,
        )

    allowed_sections_for_report = _get_allowed_sections_for_report_type(
        report_type,
    )

    sections = [section for section in sections if section in allowed_sections_for_report]

    report_context = _get_report_type_context(report_type)
    if report_context.get('family') == 'inventory':
        sections = _get_default_sections(report_type)
    elif not sections:
        sections = _get_default_sections(
            report_type,
        )

    period = str(
        form.get(
            'period',
            _get_default_period(report_type),
        )
        or ''
    ).strip()
    if _get_default_period(report_type) == 'snapshot':
        period = 'snapshot'
    elif period == 'snapshot':
        period = '30d'

    return {
        'name': form.get(
            'name',
            '',
        ),
        'cluster_id': form.get(
            'cluster_id',
            '',
        ),
        'namespace': form.get(
            'namespace',
            '',
        ),
        'object_storage_system_id': form.get(
            'object_storage_system_id',
            '',
        ),
        'report_type': report_type,
        'period': period,
        'output_format': str(
            form.get('output_format', get_report_primary_output_format(report_type))
            or get_report_primary_output_format(report_type)
        )
        .strip()
        .lower(),
        'sections': sections,
    }


def validate_form_state(
    form_state: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    report_type = form_state['report_type']

    if report_type not in {item['value'] for item in REPORT_TYPE_OPTIONS}:
        errors.append('Please select a valid report type.')

    report_spec = get_report_type_spec(report_type)
    scope_errors, cluster_exists = _validate_primary_scope(form_state, report_spec)
    errors.extend(scope_errors)
    errors.extend(_validate_period_and_format(form_state, report_type))
    errors.extend(_validate_sections(form_state, report_type))
    errors.extend(_validate_namespace_scope(form_state, report_spec, cluster_exists))
    errors.extend(_validate_object_storage_scope_reference(form_state, report_spec))
    return errors


def _validate_primary_scope(
    form_state: dict[str, Any],
    report_spec: Any,
) -> tuple[list[str], bool]:
    errors: list[str] = []
    cluster_exists = False

    if report_spec.scope_asset_type == KUBERNETES_CLUSTER_ASSET_TYPE:
        cluster_count = db.session.scalar(select(func.count(Cluster.id))) or 0
        if cluster_count == 0:
            errors.append('Add at least one Kubernetes cluster before creating Kubernetes reports or schedules.')
        cluster_id = str(form_state.get('cluster_id') or '').strip()
        if report_spec.requires_cluster and not cluster_id:
            errors.append('A selected Kubernetes cluster is required for this report artifact.')
        if cluster_id:
            cluster_exists = db.session.scalar(select(Cluster.id).where(Cluster.id == cluster_id)) is not None
            if not cluster_exists:
                errors.append('Please select a valid cluster.')
        return errors, cluster_exists

    if report_spec.scope_asset_type == OBJECT_STORAGE_SYSTEM_ASSET_TYPE:
        system_count = db.session.scalar(select(func.count(ObjectStorageSystem.id))) or 0
        if system_count == 0:
            errors.append('Add at least one Object Storage system before creating Object Storage reports or schedules.')
        if not str(form_state.get('object_storage_system_id') or '').strip():
            errors.append('A selected Object Storage system is required for this report artifact.')

    return errors, cluster_exists


def _validate_period_and_format(form_state: dict[str, Any], report_type: str) -> list[str]:
    errors: list[str] = []
    allowed_periods = {item['value'] for item in PERIOD_OPTIONS}
    allowed_output_formats = {item['value'] for item in OUTPUT_FORMAT_OPTIONS}

    if form_state['period'] not in allowed_periods:
        errors.append('Please select a valid report period.')
    if form_state['output_format'] not in allowed_output_formats:
        errors.append('Please select a valid output format.')

    allowed_formats_for_report = get_report_allowed_output_formats(report_type)
    if (
        form_state['output_format'] in allowed_output_formats
        and form_state['output_format'] not in allowed_formats_for_report
    ):
        allowed_label = ' or '.join(value.upper() for value in allowed_formats_for_report)
        errors.append(f'This report type supports only {allowed_label} output.')
    return errors


def _validate_sections(form_state: dict[str, Any], report_type: str) -> list[str]:
    errors: list[str] = []
    selected_sections = form_state['sections']
    allowed_sections = {item['value'] for item in SECTION_OPTIONS}

    if not selected_sections:
        errors.append('Please select at least one report section.')
    if any(section not in allowed_sections for section in selected_sections):
        errors.append('One or more selected report sections are invalid.')

    allowed_sections_for_report = _get_allowed_sections_for_report_type(report_type)
    if any(section not in allowed_sections_for_report for section in selected_sections):
        errors.append('One or more selected sections are not available for this report type.')
    return errors


def _validate_namespace_scope(
    form_state: dict[str, Any],
    report_spec: Any,
    cluster_exists: bool,
) -> list[str]:
    namespace = str(form_state.get('namespace') or '').strip()
    if not namespace:
        return []
    if report_spec.scope_asset_type != KUBERNETES_CLUSTER_ASSET_TYPE:
        return ['Namespace scope is available only for Kubernetes reports.']
    if not form_state['cluster_id']:
        return ['Select a Kubernetes cluster before choosing a namespace.']
    if not cluster_exists:
        return []

    namespace_query = filter_current_generation(
        NamespaceInventory.query,
        NamespaceInventory,
    ).filter(
        NamespaceInventory.cluster_id == form_state['cluster_id'],
        NamespaceInventory.namespace == namespace,
    )
    if namespace_query.with_entities(NamespaceInventory.id).first() is None:
        return ['Please select a namespace available in the current inventory snapshot for this cluster.']
    return []


def _validate_object_storage_scope_reference(form_state: dict[str, Any], report_spec: Any) -> list[str]:
    if report_spec.scope_asset_type != OBJECT_STORAGE_SYSTEM_ASSET_TYPE:
        return []
    system_id = str(form_state.get('object_storage_system_id') or '').strip()
    if system_id and db.session.get(ObjectStorageSystem, system_id) is None:
        return ['Please select a valid Object Storage system.']
    return []


def _get_default_period(report_type: str) -> str:
    return 'snapshot' if get_report_type_spec(report_type).period_mode == 'snapshot' else '30d'


def build_default_report_name(
    form_state: dict[str, Any],
) -> str:
    report_type_label = _get_label_by_value(
        REPORT_TYPE_OPTIONS,
        form_state['report_type'],
    )

    period_label = _get_label_by_value(
        PERIOD_OPTIONS,
        form_state['period'],
    )

    return f'{report_type_label} - {period_label}'


def _get_cluster_options() -> list[dict[str, str]]:
    clusters = (
        db.session.execute(
            select(
                Cluster,
            ).order_by(
                Cluster.name.asc(),
            )
        )
        .scalars()
        .all()
    )

    options: list[dict[str, str]] = []

    for cluster in clusters:
        options.append(
            {
                'value': str(
                    cluster.id,
                ),
                'label': cluster.name,
            }
        )

    return options


def _get_object_storage_system_options() -> list[dict[str, str]]:
    systems = db.session.execute(select(ObjectStorageSystem).order_by(ObjectStorageSystem.name.asc())).scalars().all()
    return [
        {
            'value': str(system.id),
            'label': system.name,
            'environment': system.environment,
            'status': system.status,
        }
        for system in systems
    ]


def _scope_is_ready(form_state: dict[str, Any], report_context: dict[str, Any]) -> bool:
    if report_context.get('scope_asset_type') == OBJECT_STORAGE_SYSTEM_ASSET_TYPE:
        return bool(str(form_state.get('object_storage_system_id') or '').strip())
    return bool(str(form_state.get('cluster_id') or '').strip())


def _get_namespace_options_by_cluster() -> dict[str, list[str]]:
    return get_report_namespace_options_by_cluster()


def _parse_cluster_id(
    value: str,
) -> str | None:
    if not value:
        return None

    return value


def _get_default_sections(
    report_type: str,
) -> list[str]:
    for item in REPORT_TYPE_OPTIONS:
        if item['value'] == report_type:
            return list(
                item['default_sections'],
            )

    return [
        'executive_summary',
        'operational_recommendations',
    ]


def _get_label_by_value(
    options: list[dict[str, Any]],
    value: str,
) -> str:
    for option in options:
        if option['value'] == value:
            return option['label']

    return value

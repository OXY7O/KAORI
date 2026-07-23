from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

from flask import url_for
from sqlalchemy import select
from werkzeug.datastructures import ImmutableMultiDict, MultiDict

from app.common.pagination import PER_PAGE_OPTIONS, build_pagination_window
from app.extensions import db
from app.models.report import ReportTemplate
from app.models.user import User
from app.reports.export.constants import (
    DEFAULT_REPORT_DOMAIN,
    DEFAULT_REPORT_SOURCE_KIND,
    REPORT_DOMAIN_DESCRIPTIONS,
    REPORT_DOMAIN_LABELS,
    SOURCE_KIND_LABELS,
)
from app.reports.generate.service import REPORT_TYPE_OPTIONS, SECTION_OPTIONS

SYSTEM_TEMPLATE_ITEMS: list[dict[str, Any]] = [
    {
        'id': 'analytics_overview',
        'name': 'Analytics Overview Template',
        'report_type': 'analytics_overview',
        'report_type_label': 'Analytics Overview',
        'description': 'High-level analytics summary across utilization, capacity, forecast, top consumers, and alerts.',  # noqa: E501
        'status': 'system',
        'report_domain': DEFAULT_REPORT_DOMAIN,
        'source_kind': DEFAULT_REPORT_SOURCE_KIND,
        'output_format': 'PDF',
        'icon': 'layout-dashboard',
        'sections': [
            'executive_summary',
            'analytics_summary',
            'resource_snapshot',
            'risk_overview',
            'operational_recommendations',
        ],
    },
    {
        'id': 'resource_utilization',
        'name': 'Resource Utilization Template',
        'report_type': 'resource_utilization',
        'report_type_label': 'Resource Utilization',
        'description': 'CPU, memory, storage, pod utilization, and node resource detail for one selected cluster.',
        'status': 'system',
        'report_domain': DEFAULT_REPORT_DOMAIN,
        'source_kind': DEFAULT_REPORT_SOURCE_KIND,
        'output_format': 'PDF',
        'icon': 'activity',
        'sections': [
            'executive_summary',
            'cpu_utilization',
            'memory_utilization',
            'storage_utilization',
            'pod_utilization',
            'node_resource_detail',
            'operational_recommendations',
        ],
    },
    {
        'id': 'capacity_analysis',
        'name': 'Capacity Analysis Template',
        'report_type': 'capacity_analysis',
        'report_type_label': 'Capacity Analysis',
        'description': 'Worker capacity, allocation, schedulable headroom, and pressure risk aligned with the Capacity Analysis generator.',  # noqa: E501
        'status': 'system',
        'report_domain': DEFAULT_REPORT_DOMAIN,
        'source_kind': DEFAULT_REPORT_SOURCE_KIND,
        'output_format': 'PDF',
        'icon': 'database',
        'sections': [
            'executive_summary',
            'worker_capacity_summary',
            'resource_allocation_headroom',
            'capacity_pressure_risk',
            'operational_recommendations',
        ],
    },
    {
        'id': 'storage_analysis',
        'name': 'Storage Analysis Template',
        'report_type': 'storage_analysis',
        'report_type_label': 'Storage Analysis',
        'description': 'Filesystem, persistent volume, PVC, used/free capacity, and storage risk context.',
        'status': 'system',
        'report_domain': DEFAULT_REPORT_DOMAIN,
        'source_kind': DEFAULT_REPORT_SOURCE_KIND,
        'output_format': 'PDF',
        'icon': 'hard-drive',
        'sections': [
            'executive_summary',
            'filesystem_summary',
            'persistent_volume_summary',
            'persistent_volume_claims',
            'storage_risk',
            'operational_recommendations',
        ],
    },
    {
        'id': 'workload_analysis',
        'name': 'Workload Analysis Template',
        'report_type': 'workload_analysis',
        'report_type_label': 'Workload Analysis',
        'description': 'Workload requests, limits, tenant quota posture, governance findings, and resource mapping.',
        'status': 'system',
        'report_domain': DEFAULT_REPORT_DOMAIN,
        'source_kind': DEFAULT_REPORT_SOURCE_KIND,
        'output_format': 'PDF',
        'icon': 'boxes',
        'sections': [
            'executive_summary',
            'tenant_quota_summary',
            'request_limit_coverage',
            'workload_resource_mapping',
            'governance_findings',
            'operational_recommendations',
        ],
    },
    {
        'id': 'resource_forecast',
        'name': 'Resource Forecast Template',
        'report_type': 'resource_forecast',
        'report_type_label': 'Resource Forecast',
        'description': 'Forecast CPU, memory, storage, pod growth, and projected capacity pressure.',
        'status': 'system',
        'report_domain': DEFAULT_REPORT_DOMAIN,
        'source_kind': DEFAULT_REPORT_SOURCE_KIND,
        'output_format': 'PDF',
        'icon': 'line-chart',
        'sections': [
            'executive_summary',
            'forecast_summary',
            'cpu_forecast',
            'memory_forecast',
            'storage_forecast',
            'pod_forecast',
            'capacity_projection',
            'operational_recommendations',
        ],
    },
    {
        'id': 'top_consumers',
        'name': 'Top Consumers Template',
        'report_type': 'top_consumers',
        'report_type_label': 'Top Consumers',
        'description': 'Top namespaces, workloads, pods, and resource hotspot summary.',
        'status': 'system',
        'report_domain': DEFAULT_REPORT_DOMAIN,
        'source_kind': DEFAULT_REPORT_SOURCE_KIND,
        'output_format': 'PDF',
        'icon': 'users',
        'sections': [
            'executive_summary',
            'top_namespace_consumers',
            'top_workload_consumers',
            'top_pod_consumers',
            'resource_hotspots',
            'operational_recommendations',
        ],
    },
    {
        'id': 'alerts_anomalies',
        'name': 'Alerts & Anomalies Template',
        'report_type': 'alerts_anomalies',
        'report_type_label': 'Alerts & Anomalies',
        'description': 'Alert Intelligence report covering alert source health, routing, silence, ownership, incident readiness, anomaly context, and recommendations.',  # noqa: E501
        'status': 'system',
        'report_domain': DEFAULT_REPORT_DOMAIN,
        'source_kind': DEFAULT_REPORT_SOURCE_KIND,
        'output_format': 'PDF',
        'icon': 'triangle-alert',
        'sections': [
            'executive_summary',
            'active_alerts',
            'alert_severity_summary',
            'source_health',
            'routing_grouping',
            'silence_inhibition',
            'ownership_runbook',
            'incident_readiness',
            'anomaly_context',
            'affected_resources',
            'operational_recommendations',
        ],
    },
]

IMPLEMENTED_TEMPLATE_IDS = {item['id'] for item in SYSTEM_TEMPLATE_ITEMS}


def get_report_templates_payload(
    args: MultiDict[str, str] | None = None,
) -> dict[str, Any]:
    selected_filters = get_selected_filters(args)
    all_templates = get_all_template_items()
    filtered_templates = [
        template for template in all_templates if template_matches_filters(template, selected_filters)
    ]
    pagination = build_templates_pagination(args, selected_filters, len(filtered_templates))
    templates = filtered_templates[pagination['offset'] : pagination['offset'] + pagination['per_page']]
    edit_template = get_edit_template_context(args) if args is not None else None

    return {
        'page_title': 'Report Templates',
        'page_subtitle': (
            'Manage reusable infrastructure report templates for Kubernetes today and server or HCI reporting later.'
        ),
        'summary_cards': get_summary_cards(all_templates),
        'filter_options': get_filter_options(),
        'selected_filters': selected_filters,
        'active_filter_count': count_active_filters(selected_filters),
        'templates': templates,
        'template_count': len(templates),
        'pagination': pagination,
        'template_context': get_template_context(),
        'report_architecture_context': get_report_architecture_context(),
        'renderer_readiness': get_renderer_readiness(),
        'create_form': get_template_form_context(),
        'edit_template': edit_template,
        'section_options_by_report_type': get_section_options_by_report_type(),
        'default_sections_by_report_type': get_default_sections_by_report_type(),
    }


def get_all_template_items() -> list[dict[str, Any]]:
    items = [build_system_template_item(template) for template in SYSTEM_TEMPLATE_ITEMS]
    items.extend(build_custom_template_item(template) for template in get_custom_templates())
    return items


def get_custom_templates() -> list[ReportTemplate]:
    return list(
        db.session.execute(
            select(ReportTemplate).order_by(
                ReportTemplate.updated_at.desc(),
                ReportTemplate.name.asc(),
            )
        )
        .scalars()
        .all()
    )


def build_system_template_item(template: dict[str, Any]) -> dict[str, Any]:
    template_id = str(template['id'])
    sections = list(template['sections'])
    return {
        **template,
        'template_key': f'system:{template_id}',
        'source': 'system',
        'database_id': None,
        'sections': get_section_labels(sections),
        'section_values': sections,
        'section_count': len(sections),
        'status_label': format_status_label(str(template['status'])),
        'status_tone': get_status_tone(str(template['status'])),
        'renderer_status': 'Ready' if template_id in IMPLEMENTED_TEMPLATE_IDS else 'Review',
        'renderer_tone': 'green' if template_id in IMPLEMENTED_TEMPLATE_IDS else 'gray',
        'renderer_label': 'PDF renderer ready' if template_id in IMPLEMENTED_TEMPLATE_IDS else 'Renderer needs review',
        'generate_href': build_generate_href(str(template['report_type']), sections),
        'duplicate_href': url_for('reports.duplicate_system_template', template_id=template_id),
        'edit_href': '',
        'delete_href': '',
        'customization_status': 'Read-only system template',
        'updated_label': 'System baseline',
        'created_by_label': 'KAORI Kubernetes Reports',
        'can_edit': False,
        'can_delete': False,
        'can_duplicate': True,
    }


def build_custom_template_item(template: ReportTemplate) -> dict[str, Any]:
    sections = sanitize_sections(template.report_type, template.sections_as_list())
    report_type_label = get_report_type_label(template.report_type)
    status = template.status or 'draft'
    return {
        'id': str(template.id),
        'template_key': f'custom:{template.id}',
        'source': 'custom',
        'database_id': template.id,
        'name': template.name,
        'report_type': template.report_type,
        'report_type_label': report_type_label,
        'description': template.description or 'Custom report template.',
        'status': status,
        'output_format': template.output_format.upper(),
        'icon': get_report_type_icon(template.report_type),
        'sections': get_section_labels(sections),
        'section_values': sections,
        'section_count': len(sections),
        'status_label': format_status_label(status),
        'status_tone': get_status_tone(status),
        'renderer_status': 'Ready',
        'renderer_tone': 'green',
        'renderer_label': 'PDF renderer ready',
        'generate_href': build_generate_href(template.report_type, sections, template.name),
        'duplicate_href': url_for('reports.duplicate_custom_template', template_id=template.id),
        'edit_href': url_for('reports.report_templates', edit_template_id=template.id),
        'delete_href': url_for('reports.delete_report_template', template_id=template.id),
        'customization_status': 'Editable custom template',
        'updated_at': template.updated_at,
        'updated_label': None,
        'created_by_label': template.created_by_display_name_snapshot
        or template.created_by_username_snapshot
        or 'Unknown user',
        'can_edit': True,
        'can_delete': True,
        'can_duplicate': True,
    }


def get_template_form_context(template: ReportTemplate | None = None) -> dict[str, Any]:
    report_type = template.report_type if template else 'analytics_overview'
    sections = (
        sanitize_sections(report_type, template.sections_as_list()) if template else get_default_sections(report_type)
    )
    return {
        'id': template.id if template else None,
        'name': template.name if template else '',
        'description': template.description if template else '',
        'report_type': report_type,
        'status': template.status if template else 'draft',
        'sections': sections,
    }


def get_edit_template_context(args: MultiDict[str, str]) -> dict[str, Any] | None:
    raw_template_id = args.get('edit_template_id', '').strip()
    if not raw_template_id.isdigit():
        return None

    template = db.session.get(ReportTemplate, int(raw_template_id))
    if template is None:
        return None

    return get_template_form_context(template)


def template_matches_filters(template: dict[str, Any], filters: dict[str, str]) -> bool:
    report_type = filters.get('report_type', '')
    status = filters.get('status', '')
    search = filters.get('search', '').strip().lower()

    if report_type and template.get('report_type') != report_type:
        return False

    if status and template.get('status') != status:
        return False

    if search:
        searchable = ' '.join(
            [
                str(template.get('name', '')),
                str(template.get('report_type_label', '')),
                str(template.get('description', '')),
                ' '.join(str(section) for section in template.get('sections', [])),
            ]
        ).lower()
        if search not in searchable:
            return False

    return True


def create_custom_template(
    form: MultiDict[str, str] | ImmutableMultiDict[str, str],
    user_id: int | None,
) -> tuple[bool, list[str], ReportTemplate | None]:
    form_state = get_template_form_state(form)
    errors = validate_template_form_state(form_state)
    if errors:
        return False, errors, None

    template = ReportTemplate()
    apply_template_state(template, form_state)
    apply_template_owner_snapshot(template, user_id)
    db.session.add(template)
    db.session.commit()
    return True, [], template


def update_custom_template(
    template_id: int,
    form: MultiDict[str, str] | ImmutableMultiDict[str, str],
) -> tuple[bool, list[str], ReportTemplate | None]:
    template = db.session.get(ReportTemplate, template_id)
    if template is None:
        return False, ['Custom template was not found.'], None

    form_state = get_template_form_state(form)
    errors = validate_template_form_state(form_state)
    if errors:
        return False, errors, template

    apply_template_state(template, form_state)
    template.updated_at = datetime.now(UTC)
    db.session.commit()
    return True, [], template


def delete_custom_template(template_id: int) -> tuple[bool, str]:
    template = db.session.get(ReportTemplate, template_id)
    if template is None:
        return False, 'Custom template was not found.'

    db.session.delete(template)
    db.session.commit()
    return True, 'Custom template deleted.'


def duplicate_system_template(template_id: str, user_id: int | None) -> tuple[bool, str, ReportTemplate | None]:
    source = next((item for item in SYSTEM_TEMPLATE_ITEMS if item['id'] == template_id), None)
    if source is None:
        return False, 'System template was not found.', None

    template = ReportTemplate()
    template.name = build_copy_name(str(source['name']))
    template.description = str(source['description'])
    template.report_type = str(source['report_type'])
    template.report_domain = str(source.get('report_domain') or DEFAULT_REPORT_DOMAIN)
    template.source_kind = str(source.get('source_kind') or DEFAULT_REPORT_SOURCE_KIND)
    template.status = 'draft'
    template.output_format = 'pdf'
    template.sections = list(source['sections'])
    template.source_template_key = f'system:{template_id}'
    apply_template_owner_snapshot(template, user_id)
    db.session.add(template)
    db.session.commit()
    return True, 'System template duplicated as draft custom template.', template


def duplicate_custom_template(template_id: int, user_id: int | None) -> tuple[bool, str, ReportTemplate | None]:
    source = db.session.get(ReportTemplate, template_id)
    if source is None:
        return False, 'Custom template was not found.', None

    template = ReportTemplate()
    template.name = build_copy_name(source.name)
    template.description = source.description
    template.report_type = source.report_type
    template.report_domain = source.report_domain
    template.source_kind = source.source_kind
    template.status = 'draft'
    template.output_format = source.output_format
    template.sections = source.sections_as_list()
    template.source_template_key = f'custom:{source.id}'
    apply_template_owner_snapshot(template, user_id)
    db.session.add(template)
    db.session.commit()
    return True, 'Custom template duplicated as draft.', template


def get_template_form_state(
    form: MultiDict[str, str] | ImmutableMultiDict[str, str],
) -> dict[str, Any]:
    report_type = normalize_report_type(form.get('report_type', 'analytics_overview'))
    sections = sanitize_sections(report_type, form.getlist('sections'))
    if not sections:
        sections = get_default_sections(report_type)

    return {
        'name': form.get('name', '').strip(),
        'description': form.get('description', '').strip(),
        'report_type': report_type,
        'status': normalize_template_status(form.get('status', 'draft')),
        'sections': sections,
        'output_format': 'pdf',
    }


def validate_template_form_state(form_state: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not form_state['name']:
        errors.append('Template name is required.')
    if len(form_state['name']) > 255:
        errors.append('Template name must be 255 characters or less.')
    if len(form_state['description']) > 1000:
        errors.append('Template description must be 1000 characters or less.')
    if form_state['report_type'] not in get_allowed_report_types():
        errors.append('Please select a valid report type.')
    if form_state['status'] not in {'draft', 'active'}:
        errors.append('Please select a valid template status.')
    if not form_state['sections']:
        errors.append('Please select at least one template section.')
    return errors


def apply_template_state(template: ReportTemplate, form_state: dict[str, Any]) -> None:
    template.name = form_state['name']
    template.description = form_state['description'] or None
    template.report_type = form_state['report_type']
    template.report_domain = DEFAULT_REPORT_DOMAIN
    template.source_kind = DEFAULT_REPORT_SOURCE_KIND
    template.status = form_state['status']
    template.output_format = 'pdf'
    template.sections = form_state['sections']


def apply_template_owner_snapshot(template: ReportTemplate, user_id: int | None) -> None:
    template.created_by_id = user_id
    if user_id is None:
        return

    user = db.session.get(User, user_id)
    if user is None:
        return

    template.created_by_username_snapshot = user.username
    template.created_by_display_name_snapshot = user.display_label
    template.created_by_auth_source_snapshot = user.auth_source


def get_summary_cards(templates: list[dict[str, Any]]) -> list[dict[str, str]]:
    system_templates = sum(1 for template in templates if template['status'] == 'system')
    ready_templates = sum(1 for template in templates if template.get('renderer_status') == 'Ready')
    custom_templates = sum(1 for template in templates if template['status'] in {'active', 'draft'})
    active_custom_templates = sum(1 for template in templates if template['status'] == 'active')
    return [
        {
            'label': 'System Templates',
            'value': str(system_templates),
            'caption': 'Default report definitions from Analytics modules',
            'icon': 'shield-check',
            'tone': 'blue',
        },
        {
            'label': 'PDF Ready',
            'value': str(ready_templates),
            'caption': 'Templates mapped to implemented PDF renderers',
            'icon': 'file-check-2',
            'tone': 'green',
        },
        {
            'label': 'Custom Templates',
            'value': str(custom_templates),
            'caption': f'{active_custom_templates} active custom template(s)',
            'icon': 'pencil-ruler',
            'tone': 'purple',
        },
        {
            'label': 'Total Templates',
            'value': str(len(templates)),
            'caption': 'Visible system and custom definitions',
            'icon': 'layout-template',
            'tone': 'amber',
        },
    ]


def get_filter_options() -> dict[str, list[dict[str, str]]]:
    report_type_options = [{'value': '', 'label': 'All Types'}]
    for option in REPORT_TYPE_OPTIONS:
        report_type_options.append(
            {'value': str(option['value']), 'label': str(option['label']).replace(' Report', '')}
        )

    return {
        'report_types': report_type_options,
        'statuses': [
            {'value': '', 'label': 'All Status'},
            {'value': 'system', 'label': 'System'},
            {'value': 'active', 'label': 'Active'},
            {'value': 'draft', 'label': 'Draft'},
        ],
    }


def get_selected_filters(args: MultiDict[str, str] | None) -> dict[str, str]:
    if args is None:
        return {'report_type': '', 'status': '', 'search': ''}

    report_type = args.get('report_type', '').strip()
    status = args.get('status', '').strip()
    search = args.get('search', '').strip()

    if report_type not in get_allowed_report_types():
        report_type = ''
    if status not in {'system', 'active', 'draft'}:
        status = ''

    return {'report_type': report_type, 'status': status, 'search': search}


def build_templates_pagination(
    args: MultiDict[str, str] | None,
    selected_filters: dict[str, str],
    total_items: int,
) -> dict[str, Any]:
    pagination = build_pagination_window(
        total_items=total_items,
        page=args.get('page') if args is not None else 1,
        per_page=args.get('per_page') if args is not None else PER_PAGE_OPTIONS[0],
    )

    return {
        **pagination.as_dict(),
        'per_page_options': list(PER_PAGE_OPTIONS),
        'has_previous': pagination.has_prev,
        'previous_href': build_templates_page_href(
            selected_filters, pagination.prev_page, pagination.per_page
        ),
        'next_href': build_templates_page_href(
            selected_filters, pagination.next_page, pagination.per_page
        ),
        'label': (
            f'Showing {pagination.start_item} - {pagination.end_item} '
            f'of {pagination.total_items} templates'
        ),
    }


def build_templates_page_href(filters: dict[str, str], page: int, per_page: int) -> str:
    params: dict[str, str] = {'page': str(page), 'per_page': str(per_page)}
    for key in ('report_type', 'status', 'search'):
        value = filters.get(key, '').strip()
        if value:
            params[key] = value
    return f'{url_for("reports.report_templates")}?{urlencode(params)}'


def parse_positive_int(value: str | None, default: int) -> int:
    try:
        parsed = int(value or default)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def count_active_filters(selected_filters: dict[str, str]) -> int:
    return sum(1 for value in selected_filters.values() if value)


def get_report_architecture_context() -> dict[str, Any]:
    return {
        'current_domain_label': REPORT_DOMAIN_LABELS.get(DEFAULT_REPORT_DOMAIN, 'KAORI Kubernetes Reports'),
        'current_source_label': SOURCE_KIND_LABELS.get(DEFAULT_REPORT_SOURCE_KIND, 'Kubernetes'),
        'server_label': REPORT_DOMAIN_LABELS.get('server', 'KAORI Server Reports'),
        'hci_label': REPORT_DOMAIN_LABELS.get('hci', 'KAORI HCI Reports'),
        'server_description': REPORT_DOMAIN_DESCRIPTIONS.get('server', ''),
        'hci_description': REPORT_DOMAIN_DESCRIPTIONS.get('hci', ''),
        'status': 'KAORI Kubernetes Reports ready · KAORI Server Reports and KAORI HCI Reports integration scope',
    }


def get_template_context() -> list[str]:
    return [
        'System templates provide protected defaults for repeatable infrastructure reports and cannot be modified directly.',  # noqa: E501
        'Custom templates store a report type, selected sections, owner snapshot, status, and source template reference.',  # noqa: E501
        'Templates pre-fill Generate Report so users can create consistent PDF artifacts without rebuilding the section checklist every time.',  # noqa: E501
        'Template sections are validated against each report type so the PDF renderer receives a supported output contract.',  # noqa: E501
    ]


def get_renderer_readiness() -> list[dict[str, str]]:
    return [
        {
            'label': 'System template catalog',
            'description': 'Default templates are available for the implemented KAORI Kubernetes Reports report families.',
            'status': 'Ready',
            'tone': 'green',
            'icon': 'check-circle-2',
        },
        {
            'label': 'Custom template workspace',
            'description': 'Custom templates can be created, duplicated, edited, deleted, and used to pre-fill Generate Report.',  # noqa: E501
            'status': 'Ready',
            'tone': 'green',
            'icon': 'pencil-ruler',
        },
        {
            'label': 'PDF output mapping',
            'description': 'Template sections are mapped to ReportLab sections and the corresponding report payload builders.',  # noqa: E501
            'status': 'Ready',
            'tone': 'green',
            'icon': 'file-check-2',
        },
        {
            'label': 'Template ownership',
            'description': 'Custom templates retain creator snapshots, status, source template reference, timestamps, and selected sections.',  # noqa: E501
            'status': 'Ready',
            'tone': 'green',
            'icon': 'git-branch',
        },
    ]


def get_section_options_by_report_type() -> dict[str, list[dict[str, str]]]:
    section_map = {item['value']: item for item in SECTION_OPTIONS}
    return {
        str(option['value']): [section_map[section] for section in option['default_sections'] if section in section_map]
        for option in REPORT_TYPE_OPTIONS
    }


def get_default_sections_by_report_type() -> dict[str, list[str]]:
    return {str(option['value']): list(option['default_sections']) for option in REPORT_TYPE_OPTIONS}


def get_default_sections(report_type: str) -> list[str]:
    for option in REPORT_TYPE_OPTIONS:
        if option['value'] == report_type:
            return list(option['default_sections'])
    return ['executive_summary', 'operational_recommendations']


def sanitize_sections(report_type: str, sections: list[str]) -> list[str]:
    allowed_sections = set(get_default_sections(report_type))
    sanitized = [section for section in sections if section in allowed_sections]
    return sanitized


def get_section_labels(sections: list[str]) -> list[str]:
    section_map = {item['value']: item['label'] for item in SECTION_OPTIONS}
    return [section_map.get(section, section.replace('_', ' ').title()) for section in sections]


def normalize_report_type(value: str | None) -> str:
    value = (value or 'analytics_overview').strip()
    if value not in get_allowed_report_types():
        return 'analytics_overview'
    return value


def normalize_template_status(value: str | None) -> str:
    value = (value or 'draft').strip()
    if value not in {'draft', 'active'}:
        return 'draft'
    return value


def get_allowed_report_types() -> set[str]:
    return {str(item['value']) for item in REPORT_TYPE_OPTIONS}


def get_report_type_label(report_type: str) -> str:
    for option in REPORT_TYPE_OPTIONS:
        if option['value'] == report_type:
            return str(option['label']).replace(' Report', '')
    return report_type.replace('_', ' ').title()


def get_report_type_icon(report_type: str) -> str:
    for option in REPORT_TYPE_OPTIONS:
        if option['value'] == report_type:
            return str(option['icon'])
    return 'layout-template'


def build_generate_href(report_type: str, sections: list[str], name: str | None = None) -> str:
    params: list[tuple[str, str]] = [('report_type', report_type)]
    if name:
        params.append(('name', name))
    params.extend(('sections', section) for section in sections)
    return f'{url_for("reports.generate_report")}?{urlencode(params)}'


def build_copy_name(name: str) -> str:
    return f'{name} Copy'[:255]


def format_status_label(status: str) -> str:
    labels = {
        'system': 'System Ready',
        'active': 'Active',
        'draft': 'Draft',
    }
    return labels.get(status, status.title())


def get_status_tone(status: str) -> str:
    tones = {
        'system': 'blue',
        'active': 'green',
        'draft': 'purple',
    }
    return tones.get(status, 'gray')

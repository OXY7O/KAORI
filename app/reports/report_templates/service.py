from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

from flask import url_for
from sqlalchemy import select
from werkzeug.datastructures import ImmutableMultiDict, MultiDict

from app.common.pagination import PER_PAGE_OPTIONS, build_pagination_window
from app.extensions.db import db
from app.models.report import ReportTemplate
from app.models.user import User
from app.reports.catalog import (
    OUTPUT_FORMAT_OPTIONS,
    REPORT_FAMILY_ANALYTICS,
    REPORT_FAMILY_INVENTORY,
    REPORT_TYPE_OPTIONS,
    REPORT_TYPE_SPECS,
    ReportContractError,
    get_allowed_output_formats,
    get_default_output_format,
    get_report_type_spec,
)
from app.reports.export.constants import (
    DEFAULT_REPORT_DOMAIN,
    DEFAULT_REPORT_SOURCE_KIND,
    REPORT_DOMAIN_DESCRIPTIONS,
    REPORT_DOMAIN_LABELS,
)
from app.reports.generate.service import SECTION_OPTIONS

SYSTEM_TEMPLATE_ITEMS: list[dict[str, Any]] = [
    {
        'id': spec.value,
        'name': f'{spec.label.removesuffix(" Report")} Template',
        'report_type': spec.value,
        'report_type_label': spec.label.removesuffix(' Report'),
        'description': spec.description,
        'status': 'system',
        'report_domain': spec.domain,
        'source_kind': spec.source_kind,
        'output_format': spec.default_format.upper(),
        'allowed_formats': [value.upper() for value in spec.allowed_formats],
        'icon': spec.icon,
        'family': spec.family,
        'sections': list(spec.default_sections),
    }
    for spec in REPORT_TYPE_SPECS
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
    registry_return_url = build_template_registry_url(selected_filters, pagination)
    for template in templates:
        if template['source'] == 'custom':
            template['edit_href'] = build_template_registry_url(
                selected_filters, pagination, edit_template_id=int(template['database_id'])
            )
    edit_template = get_edit_template_context(args) if args is not None else None

    return {
        'page_title': 'Report Templates',
        'page_subtitle': (
            'Manage system templates and custom report structures for Analytics and Inventory formats.'
        ),
        'summary_cards': get_summary_cards(all_templates),
        'posture': get_template_posture(all_templates),
        'filter_options': get_filter_options(),
        'selected_filters': selected_filters,
        'active_filter_count': count_active_filters(selected_filters),
        'registry_return_url': registry_return_url,
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
        'output_format_options': OUTPUT_FORMAT_OPTIONS,
        'allowed_formats_by_report_type': {
            str(option['value']): list(option['allowed_formats']) for option in REPORT_TYPE_OPTIONS
        },
        'report_family_by_report_type': {str(option['value']): str(option['family']) for option in REPORT_TYPE_OPTIONS},
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
        'ownership': 'system',
        'ownership_label': 'System Template',
        'database_id': None,
        'family': str(template.get('family') or get_report_family(template_id)),
        'family_label': get_report_family_label(str(template.get('family') or get_report_family(template_id))),
        'domain_label': REPORT_DOMAIN_LABELS.get(
            str(template.get('report_domain') or DEFAULT_REPORT_DOMAIN), 'Unknown Domain'
        ),
        'sections': get_section_labels(sections),
        'section_values': sections,
        'section_count': len(sections),
        'status_label': format_status_label(str(template['status'])),
        'status_tone': get_status_tone(str(template['status'])),
        'renderer_status': 'Ready' if template_id in IMPLEMENTED_TEMPLATE_IDS else 'Review',
        'renderer_tone': 'green' if template_id in IMPLEMENTED_TEMPLATE_IDS else 'gray',
        'renderer_label': 'Canonical artifact renderer ready'
        if template_id in IMPLEMENTED_TEMPLATE_IDS
        else 'Renderer needs review',
        'generate_href': build_generate_href(
            str(template['report_type']), sections, output_format=str(template['output_format']).lower()
        ),
        'duplicate_href': url_for('reports.duplicate_system_template', template_id=template_id),
        'edit_href': '',
        'delete_href': '',
        'customization_status': 'Read-only system template',
        'updated_label': 'System baseline',
        'created_by_label': 'KAORI System Reports',
        'can_edit': False,
        'can_delete': False,
        'can_duplicate': True,
        'can_generate': True,
    }


def build_custom_template_item(template: ReportTemplate) -> dict[str, Any]:
    sections = sanitize_sections(template.report_type, template.sections_as_list())
    report_type_label = get_report_type_label(template.report_type)
    status = template.status or 'draft'
    family = get_report_family(template.report_type)
    return {
        'id': str(template.id),
        'template_key': f'custom:{template.id}',
        'source': 'custom',
        'ownership': 'custom',
        'ownership_label': 'Custom Template',
        'database_id': template.id,
        'name': template.name,
        'report_type': template.report_type,
        'report_type_label': report_type_label,
        'family': family,
        'family_label': get_report_family_label(family),
        'domain_label': REPORT_DOMAIN_LABELS.get(template.report_domain or DEFAULT_REPORT_DOMAIN, 'Unknown Domain'),
        'description': template.description or 'Custom report template.',
        'status': status,
        'output_format': template.output_format.upper(),
        'allowed_formats': [value.upper() for value in get_allowed_output_formats(template.report_type)],
        'icon': get_report_type_icon(template.report_type),
        'sections': get_section_labels(sections),
        'section_values': sections,
        'section_count': len(sections),
        'status_label': format_status_label(status),
        'status_tone': get_status_tone(status),
        'renderer_status': 'Ready',
        'renderer_tone': 'green',
        'renderer_label': 'Canonical artifact renderer ready',
        'generate_href': build_generate_href(template.report_type, sections, template.name, template.output_format),
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
        'can_generate': status == 'active',
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
        'output_format': template.output_format if template else get_default_output_format(report_type),
        'source_template_key': template.source_template_key if template else f'system:{report_type}',
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
    family = filters.get('family', '')
    domain = filters.get('domain', '')
    ownership = filters.get('ownership', '')
    status = filters.get('status', '')
    output_format = filters.get('output_format', '')
    search = filters.get('search', '').strip().lower()

    if report_type and template.get('report_type') != report_type:
        return False
    if family and template.get('family') != family:
        return False
    if domain and template.get('report_domain') != domain:
        return False
    if ownership and template.get('ownership') != ownership:
        return False
    if status and template.get('status') != status:
        return False
    if output_format and str(template.get('output_format', '')).lower() != output_format:
        return False

    if search:
        searchable = ' '.join(
            [
                str(template.get('name', '')),
                str(template.get('family_label', '')),
                str(template.get('domain_label', '')),
                str(template.get('report_type_label', '')),
                str(template.get('description', '')),
                str(template.get('created_by_label', '')),
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
    template.output_format = get_default_output_format(template.report_type)
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
        'output_format': str(form.get('output_format', get_default_output_format(report_type))).strip().lower(),
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
    if form_state['output_format'] not in get_allowed_output_formats(form_state['report_type']):
        errors.append('Please select an output format supported by the report type.')
    if not form_state['sections']:
        errors.append('Please select at least one template section.')
    return errors


def apply_template_state(template: ReportTemplate, form_state: dict[str, Any]) -> None:
    template.name = form_state['name']
    template.description = form_state['description'] or None
    template.report_type = form_state['report_type']
    spec = get_report_type_spec(template.report_type)
    template.report_domain = spec.domain
    template.source_kind = spec.source_kind
    template.status = form_state['status']
    template.output_format = form_state['output_format']
    template.sections = form_state['sections']
    if template.id is None and not template.source_template_key:
        template.source_template_key = f'system:{form_state["report_type"]}'


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
    system_templates = sum(1 for template in templates if template['ownership'] == 'system')
    custom_templates = sum(1 for template in templates if template['ownership'] == 'custom')
    active_custom_templates = sum(
        1 for template in templates if template['ownership'] == 'custom' and template['status'] == 'active'
    )
    return [
        {
            'label': 'System Templates',
            'value': str(system_templates),
            'caption': 'Protected canonical report contracts',
            'icon': 'shield-check',
            'tone': 'info',
        },
        {
            'label': 'Custom Templates',
            'value': str(custom_templates),
            'caption': 'Reusable operator-owned definitions',
            'icon': 'copy-plus',
            'tone': 'maintenance',
        },
        {
            'label': 'Active Custom',
            'value': str(active_custom_templates),
            'caption': 'Available for repeated generation',
            'icon': 'check-circle-2',
            'tone': 'normal',
        },
        {
            'label': 'Total Templates',
            'value': str(len(templates)),
            'caption': 'System and custom definitions',
            'icon': 'layout-template',
            'tone': 'info',
        },
    ]


def get_template_posture(templates: list[dict[str, Any]]) -> dict[str, Any]:
    analytics_count = sum(1 for item in templates if item.get('family') == REPORT_FAMILY_ANALYTICS)
    inventory_count = sum(1 for item in templates if item.get('family') == REPORT_FAMILY_INVENTORY)
    system_count = sum(1 for item in templates if item.get('ownership') == 'system')
    custom_count = sum(1 for item in templates if item.get('ownership') == 'custom')
    active_custom_count = sum(
        1 for item in templates if item.get('ownership') == 'custom' and item.get('status') == 'active'
    )
    draft_count = sum(1 for item in templates if item.get('ownership') == 'custom' and item.get('status') == 'draft')
    catalog_count = len(REPORT_TYPE_SPECS)
    catalog_analytics_count = sum(1 for spec in REPORT_TYPE_SPECS if spec.family == REPORT_FAMILY_ANALYTICS)
    catalog_inventory_count = sum(1 for spec in REPORT_TYPE_SPECS if spec.family == REPORT_FAMILY_INVENTORY)
    supported_formats = sorted({fmt.upper() for spec in REPORT_TYPE_SPECS for fmt in spec.allowed_formats})
    protected_coverage_percent = round((system_count / catalog_count) * 100) if catalog_count else 0

    return {
        'analytics_count': analytics_count,
        'inventory_count': inventory_count,
        'catalog_analytics_count': catalog_analytics_count,
        'catalog_inventory_count': catalog_inventory_count,
        'system_count': system_count,
        'custom_count': custom_count,
        'active_custom_count': active_custom_count,
        'draft_count': draft_count,
        'catalog_count': catalog_count,
        'format_count': len(supported_formats),
        'supported_formats_label': ' · '.join(supported_formats),
        'protected_coverage_percent': protected_coverage_percent,
        'customization_label': 'No Custom Overrides' if custom_count == 0 else f'{custom_count} Custom Templates',
        'customization_tone': 'normal' if draft_count == 0 else 'warning',
        'status_label': 'Canonical Catalog Ready',
        'status_tone': 'normal',
    }


def get_filter_options() -> dict[str, list[dict[str, str]]]:
    report_type_options = [{'value': '', 'label': 'All Report Types'}]
    for option in REPORT_TYPE_OPTIONS:
        report_type_options.append(
            {'value': str(option['value']), 'label': str(option['label']).replace(' Report', '')}
        )

    published_domains = sorted(
        {str(item.get('report_domain') or DEFAULT_REPORT_DOMAIN) for item in SYSTEM_TEMPLATE_ITEMS},
        key=lambda value: REPORT_DOMAIN_LABELS.get(value, value),
    )

    return {
        'domains': [
            {'value': '', 'label': 'All Domains'},
            *[
                {'value': value, 'label': REPORT_DOMAIN_LABELS.get(value, value.replace('_', ' ').title())}
                for value in published_domains
            ],
        ],
        'families': [
            {'value': '', 'label': 'All Families'},
            {'value': REPORT_FAMILY_ANALYTICS, 'label': 'Analytics'},
            {'value': REPORT_FAMILY_INVENTORY, 'label': 'Inventory'},
        ],
        'report_types': report_type_options,
        'ownership': [
            {'value': '', 'label': 'All Ownership'},
            {'value': 'system', 'label': 'System Templates'},
            {'value': 'custom', 'label': 'Custom Templates'},
        ],
        'statuses': [
            {'value': '', 'label': 'All Status'},
            {'value': 'system', 'label': 'System'},
            {'value': 'active', 'label': 'Active'},
            {'value': 'draft', 'label': 'Draft'},
        ],
        'formats': [
            {'value': '', 'label': 'All Formats'},
            *[{'value': str(item['value']), 'label': str(item['label'])} for item in OUTPUT_FORMAT_OPTIONS],
        ],
    }


def get_selected_filters(args: MultiDict[str, str] | None) -> dict[str, str]:
    defaults = {
        'domain': '',
        'family': '',
        'report_type': '',
        'ownership': '',
        'status': '',
        'output_format': '',
        'search': '',
    }
    if args is None:
        return defaults

    filters = {
        'domain': args.get('domain', '').strip(),
        'family': args.get('family', '').strip(),
        'report_type': args.get('report_type', '').strip(),
        'ownership': args.get('ownership', '').strip(),
        'status': args.get('status', '').strip(),
        'output_format': args.get('output_format', '').strip().lower(),
        'search': args.get('search', '').strip(),
    }
    allowed_domains = {str(item.get('report_domain') or DEFAULT_REPORT_DOMAIN) for item in SYSTEM_TEMPLATE_ITEMS}
    if filters['domain'] not in allowed_domains:
        filters['domain'] = ''
    if filters['family'] not in {REPORT_FAMILY_ANALYTICS, REPORT_FAMILY_INVENTORY}:
        filters['family'] = ''
    if filters['report_type'] not in get_allowed_report_types():
        filters['report_type'] = ''
    if filters['ownership'] not in {'system', 'custom'}:
        filters['ownership'] = ''
    if filters['status'] not in {'system', 'active', 'draft'}:
        filters['status'] = ''
    allowed_formats = {str(item['value']) for item in OUTPUT_FORMAT_OPTIONS}
    if filters['output_format'] not in allowed_formats:
        filters['output_format'] = ''
    return filters


def build_template_registry_url(
    selected_filters: dict[str, str],
    pagination: dict[str, Any],
    *,
    edit_template_id: int | None = None,
) -> str:
    query: dict[str, Any] = {key: value for key, value in selected_filters.items() if value}
    query.update({'page': pagination['page'], 'per_page': pagination['per_page']})
    if edit_template_id is not None:
        query['edit_template_id'] = edit_template_id
    return url_for('reports.report_templates', **query)


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
        'label': (f'Showing {pagination.start_item}–{pagination.end_item} of {pagination.total_items} Templates'),
    }


def count_active_filters(selected_filters: dict[str, str]) -> int:
    return sum(1 for value in selected_filters.values() if value)


def get_report_architecture_context() -> dict[str, Any]:
    return {
        'current_domain_label': 'KAORI Published Reports',
        'current_source_label': 'Kubernetes + Object Storage',
        'server_label': REPORT_DOMAIN_LABELS.get('server', 'KAORI Server Reports'),
        'hci_label': REPORT_DOMAIN_LABELS.get('hci', 'KAORI HCI Reports'),
        'server_description': REPORT_DOMAIN_DESCRIPTIONS.get('server', ''),
        'hci_description': REPORT_DOMAIN_DESCRIPTIONS.get('hci', ''),
        'status': 'Kubernetes and Object Storage report contracts ready · Server and HCI coverage remains planned',
    }


def get_template_context() -> list[str]:
    return [
        'System templates provide protected defaults for repeatable infrastructure reports and cannot be modified directly.',  # noqa: E501
        'Custom templates store a report type, selected sections, owner snapshot, status, and source template reference.',  # noqa: E501
        'Templates pre-fill Generate Report so users can create consistent PDF, Excel, or CSV artifacts without rebuilding the section checklist every time.',  # noqa: E501
        'Template sections are validated against each report type so the configured renderer receives a supported output contract.',  # noqa: E501
    ]


def get_renderer_readiness() -> list[dict[str, str]]:
    return [
        {
            'label': 'System template catalog',
            'description': 'Default templates are available for published Kubernetes and Object Storage report contracts.',
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
            'label': 'Output renderer mapping',
            'description': 'Templates are mapped to the canonical Analytics PDF/XLSX/CSV or Inventory Excel/CSV renderer and shared payload builders.',  # noqa: E501
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
    default_sections = get_default_sections(report_type)
    if get_report_type_spec(report_type).family == REPORT_FAMILY_INVENTORY:
        return default_sections
    allowed_sections = set(default_sections)
    return [section for section in sections if section in allowed_sections]


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


def get_report_family(report_type: str) -> str:
    try:
        return get_report_type_spec(report_type).family
    except ReportContractError:
        return REPORT_FAMILY_ANALYTICS


def get_report_family_label(family: str) -> str:
    return 'Inventory' if family == REPORT_FAMILY_INVENTORY else 'Analytics'


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


def build_generate_href(
    report_type: str,
    sections: list[str],
    name: str | None = None,
    output_format: str | None = None,
) -> str:
    params: list[tuple[str, str]] = [
        ('report_type', report_type),
        ('output_format', output_format or get_default_output_format(report_type)),
    ]
    if name:
        params.append(('name', name))
    params.extend(('sections', section) for section in sections)
    return f'{url_for("reports.generate_report")}?{urlencode(params)}'


def build_copy_name(name: str) -> str:
    return f'{name} Copy'[:255]


def format_status_label(status: str) -> str:
    labels = {
        'system': 'System Template',
        'active': 'Active',
        'draft': 'Draft',
    }
    return labels.get(status, status.title())


def get_status_tone(status: str) -> str:
    tones = {
        'system': 'info',
        'active': 'normal',
        'draft': 'unknown',
    }
    return tones.get(status, 'gray')

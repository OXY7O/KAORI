from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.definitions.loader import DefinitionError, load_definition_document
from app.definitions.validation import (
    require_bool,
    require_list,
    require_mapping,
    require_str,
    string_tuple,
    unique_by,
)

REPORT_FAMILY_ANALYTICS = 'analytics'
REPORT_FAMILY_INVENTORY = 'inventory'

FORMAT_PDF = 'pdf'
FORMAT_XLSX = 'xlsx'
FORMAT_CSV = 'csv'


@dataclass(frozen=True, slots=True)
class OutputFormatSpec:
    value: str
    label: str
    extension: str
    mimetype: str


@dataclass(frozen=True, slots=True)
class ReportCoverageItemSpec:
    name: str
    description: str
    icon: str


@dataclass(frozen=True, slots=True)
class ReportCoverageDomainSpec:
    key: str
    label: str
    description: str
    icon: str
    status: str
    tone: str
    items: tuple[ReportCoverageItemSpec, ...]


@dataclass(frozen=True, slots=True)
class ReportTypeSpec:
    value: str
    label: str
    description: str
    icon: str
    family: str
    default_format: str
    allowed_formats: tuple[str, ...]
    default_sections: tuple[str, ...]
    period_mode: str
    requires_cluster: bool = True


def _load_report_catalog() -> tuple[dict[str, OutputFormatSpec], tuple[ReportTypeSpec, ...]]:
    document = load_definition_document('reports/catalog.yaml', expected_kind='report_catalog')
    raw_formats = [
        require_mapping(item, f'output_formats[{index}]')
        for index, item in enumerate(require_list(document.get('output_formats'), 'output_formats'))
    ]
    unique_by(raw_formats, 'value', 'output_formats')
    formats: dict[str, OutputFormatSpec] = {}
    for index, raw in enumerate(raw_formats):
        path = f'output_formats[{index}]'
        spec = OutputFormatSpec(
            value=require_str(raw, 'value', path),
            label=require_str(raw, 'label', path),
            extension=require_str(raw, 'extension', path),
            mimetype=require_str(raw, 'mimetype', path),
        )
        formats[spec.value] = spec

    raw_reports = [
        require_mapping(item, f'report_types[{index}]')
        for index, item in enumerate(require_list(document.get('report_types'), 'report_types'))
    ]
    unique_by(raw_reports, 'value', 'report_types')
    reports: list[ReportTypeSpec] = []
    for index, raw in enumerate(raw_reports):
        path = f'report_types[{index}]'
        family = require_str(raw, 'family', path)
        if family not in {REPORT_FAMILY_ANALYTICS, REPORT_FAMILY_INVENTORY}:
            raise DefinitionError(f'{path}.family is unsupported: {family!r}.')
        default_format = require_str(raw, 'default_format', path)
        allowed_formats = string_tuple(raw.get('allowed_formats'), f'{path}.allowed_formats')
        if default_format not in formats or any(item not in formats for item in allowed_formats):
            raise DefinitionError(f'{path} references unknown output format.')
        if default_format not in allowed_formats:
            raise DefinitionError(f'{path}.default_format must be included in allowed_formats.')
        reports.append(ReportTypeSpec(
            value=require_str(raw, 'value', path),
            label=require_str(raw, 'label', path),
            description=require_str(raw, 'description', path),
            icon=require_str(raw, 'icon', path),
            family=family,
            default_format=default_format,
            allowed_formats=allowed_formats,
            default_sections=string_tuple(raw.get('default_sections'), f'{path}.default_sections'),
            period_mode=require_str(raw, 'period_mode', path),
            requires_cluster=require_bool(raw, 'requires_cluster', path, default=True),
        ))
    return formats, tuple(reports)


def _load_report_coverage_catalog() -> tuple[ReportCoverageDomainSpec, ...]:
    document = load_definition_document('reports/coverage.yaml', expected_kind='report_coverage_catalog')
    raw_domains = [
        require_mapping(item, f'domains[{index}]')
        for index, item in enumerate(require_list(document.get('domains'), 'domains'))
    ]
    unique_by(raw_domains, 'key', 'domains')
    domains: list[ReportCoverageDomainSpec] = []
    for index, raw_domain in enumerate(raw_domains):
        path = f'domains[{index}]'
        raw_items = [
            require_mapping(item, f'{path}.items[{item_index}]')
            for item_index, item in enumerate(require_list(raw_domain.get('items'), f'{path}.items'))
        ]
        unique_by(raw_items, 'name', f'{path}.items')
        items = tuple(
            ReportCoverageItemSpec(
                name=require_str(item, 'name', f'{path}.items[{item_index}]'),
                description=require_str(item, 'description', f'{path}.items[{item_index}]'),
                icon=require_str(item, 'icon', f'{path}.items[{item_index}]'),
            )
            for item_index, item in enumerate(raw_items)
        )
        status = require_str(raw_domain, 'status', path)
        tone = require_str(raw_domain, 'tone', path)
        if status not in {'Planned', 'Reserved'}:
            raise DefinitionError(f'{path}.status is unsupported: {status!r}.')
        if tone not in {'info', 'unknown'}:
            raise DefinitionError(f'{path}.tone is unsupported: {tone!r}.')
        domains.append(
            ReportCoverageDomainSpec(
                key=require_str(raw_domain, 'key', path),
                label=require_str(raw_domain, 'label', path),
                description=require_str(raw_domain, 'description', path),
                icon=require_str(raw_domain, 'icon', path),
                status=status,
                tone=tone,
                items=items,
            )
        )
    return tuple(domains)


OUTPUT_FORMAT_SPECS, REPORT_TYPE_SPECS = _load_report_catalog()
PLANNED_REPORT_COVERAGE_DOMAINS = _load_report_coverage_catalog()

_REPORT_TYPE_BY_VALUE = {item.value: item for item in REPORT_TYPE_SPECS}

OUTPUT_FORMAT_OPTIONS: list[dict[str, str]] = [
    {'value': spec.value, 'label': spec.label} for spec in OUTPUT_FORMAT_SPECS.values()
]

REPORT_TYPE_OPTIONS: list[dict[str, Any]] = [
    {
        'value': spec.value,
        'label': spec.label,
        'description': spec.description,
        'icon': spec.icon,
        'family': spec.family,
        'primary_format': spec.default_format,
        'allowed_formats': list(spec.allowed_formats),
        'default_sections': list(spec.default_sections),
        'period_mode': spec.period_mode,
        'requires_cluster': spec.requires_cluster,
    }
    for spec in REPORT_TYPE_SPECS
]

REQUIRES_SELECTED_CLUSTER_REPORT_TYPES = frozenset(spec.value for spec in REPORT_TYPE_SPECS if spec.requires_cluster)

ANALYTICS_REPORT_TYPES = frozenset(spec.value for spec in REPORT_TYPE_SPECS if spec.family == REPORT_FAMILY_ANALYTICS)
INVENTORY_REPORT_TYPES = frozenset(spec.value for spec in REPORT_TYPE_SPECS if spec.family == REPORT_FAMILY_INVENTORY)


class ReportContractError(ValueError):
    """Raised when a report violates the canonical KAORI reporting contract."""


def get_report_type_spec(report_type: str) -> ReportTypeSpec:
    try:
        return _REPORT_TYPE_BY_VALUE[report_type]
    except KeyError as exc:
        raise ReportContractError(f'Unsupported report type: {report_type!r}.') from exc


def get_report_type_label(report_type: str) -> str:
    return get_report_type_spec(report_type).label


def normalize_report_type(value: str | None) -> str:
    normalized = str(value or REPORT_TYPE_SPECS[0].value).strip()
    return normalized if normalized in _REPORT_TYPE_BY_VALUE else REPORT_TYPE_SPECS[0].value


def get_allowed_output_formats(report_type: str) -> tuple[str, ...]:
    return get_report_type_spec(report_type).allowed_formats


def get_default_output_format(report_type: str) -> str:
    return get_report_type_spec(report_type).default_format


def validate_report_contract(
    *,
    report_type: str,
    output_format: str,
    cluster_id: str | None,
) -> None:
    spec = get_report_type_spec(report_type)
    normalized_format = str(output_format or '').strip().lower()

    if spec.requires_cluster and not str(cluster_id or '').strip():
        raise ReportContractError(
            'A selected Kubernetes cluster is required. Cross-cluster report generation is disabled.'
        )
    if normalized_format not in spec.allowed_formats:
        allowed = ', '.join(value.upper() for value in spec.allowed_formats)
        raise ReportContractError(f'{spec.label} supports only {allowed} output.')


def require_selected_cluster(report: Any) -> str:
    cluster_id = str(getattr(report, 'cluster_id', '') or '').strip()
    if not cluster_id:
        raise ReportContractError(
            'A selected Kubernetes cluster is required. Cross-cluster report generation is disabled.'
        )
    return cluster_id


def validate_report_instance(report: Any) -> None:
    validate_report_contract(
        report_type=str(getattr(report, 'report_type', '') or ''),
        output_format=str(getattr(report, 'output_format', '') or ''),
        cluster_id=getattr(report, 'cluster_id', None),
    )

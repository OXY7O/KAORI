"""Canonical report coverage declarations shared by Reports and capability overviews.

This is metadata only: an unimplemented report candidate is never an executable
report type or proof that report generation has been admitted.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.definitions.loader import DefinitionError, load_definition_document
from app.definitions.validation import require_list, require_mapping, require_str, unique_by


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
        if status not in {'Published', 'Evidence Ready', 'Planned', 'Reserved'}:
            raise DefinitionError(f'{path}.status is unsupported: {status!r}.')
        if tone not in {'normal', 'info', 'unknown'}:
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


REPORT_COVERAGE_DOMAINS = _load_report_coverage_catalog()

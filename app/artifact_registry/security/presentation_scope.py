from __future__ import annotations

from typing import Any

from app.models.integration import IntegrationInstance


def _security_scope_labels(
    *,
    provider_value: str,
    source_id: int | None,
    scoped_sources: list[IntegrationInstance],
) -> tuple[str, str]:
    provider_label = provider_value.replace('_', ' ').title() if provider_value else ''
    if source_id is not None:
        selected_source = scoped_sources[0] if len(scoped_sources) == 1 else None
        if selected_source is not None:
            return (
                selected_source.name,
                f'{selected_source.provider_key.replace("_", " ").title()} · {selected_source.name}',
            )
        return 'Selected Registry Source', 'No Matching Registry Source'
    if provider_label:
        source_count_label = 'Source' if len(scoped_sources) == 1 else 'Sources'
        return provider_label, f'{provider_label} · {len(scoped_sources)} {source_count_label}'
    source_count_label = 'Source' if len(scoped_sources) == 1 else 'Sources'
    return 'All Registry Sources', f'{len(scoped_sources)} Registered Registry {source_count_label}'


def _security_snapshot_context(
    evidence: dict[str, Any],
    *,
    active_scope_label: str,
    source_label: str,
    view: str,
) -> dict[str, Any]:
    artifact_total = evidence['artifact_total']
    coverage_count = evidence['coverage_count']
    coverage_percent = round((coverage_count / artifact_total) * 100) if artifact_total else 0
    coverage_supporting = (
        f'{coverage_percent}% usable scan coverage.'
        if view == 'vulnerabilities'
        else f'{coverage_percent}% security evidence coverage.'
    )
    return {
        **evidence['snapshot'],
        'source_label': source_label,
        'scope_label': active_scope_label,
        'coverage_label': f'{coverage_count} of {artifact_total} artifacts',
        'coverage_supporting': coverage_supporting,
        'coverage_tone': 'normal' if artifact_total and coverage_count == artifact_total else 'warning',
    }

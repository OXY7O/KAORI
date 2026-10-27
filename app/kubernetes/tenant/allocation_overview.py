"""Read-only Tenant logical allocation presentation from canonical committed evidence.

There is no provider read and no reimplementation of #654 admission arithmetic.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import joinedload

from app.common.pagination import paginate_sequence
from app.common.presentation import present_user_datetime

from app.kubernetes.tenant.capacity import CapacityVector
from app.kubernetes.tenant.capacity_allocation_state import (
    _TERMINAL_NAMESPACE_ALLOCATION_STATUSES,
    _TERMINAL_TENANT_ALLOCATION_LIFECYCLES,
    _active_namespace_allocation_query,
    _aggregate_committed_allocation,
    _canonical_shared_allocation_quota,
)
from app.kubernetes.tenant.capacity_governance_support import _vector_display
from app.models.tenant import (
    Tenant,
    TenantEnvironment,
    TenantNamespace,
)

_ZERO = Decimal('0')
_HUNDRED = Decimal('100')

_DIMENSIONS = (
    ('cpu', 'CPU Requests', 'cpu', 'Compute request commitment'),
    ('memory_bytes', 'Memory Requests', 'memory', 'Compute request commitment'),
    ('pods', 'Pod Slots', 'pods', 'Logical Pod quota commitment'),
    ('storage_bytes', 'Logical Storage', 'storage', 'Explicit Tenant requests.storage budget; not backend free space'),
)


def _share(value: Decimal, total: Decimal) -> str:
    """A display percentage only; never used to make admission decisions."""
    return format(min(max(value * _HUNDRED / total, _ZERO), _HUNDRED).quantize(Decimal('0.1')), 'f')


def build_tenant_allocation_bars(summary: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Render canonical #654 budget/commitment/headroom; never substitute zero for unknown."""
    budget = summary.get('budget')
    available = budget.get('available') if isinstance(budget, Mapping) else None
    committed = summary.get('committed')
    displays = summary.get('display')
    budget_display = displays.get('budget') if isinstance(displays, Mapping) else None
    committed_display = displays.get('committed') if isinstance(displays, Mapping) else None
    headroom_display = displays.get('headroom') if isinstance(displays, Mapping) else None
    result: list[dict[str, Any]] = []
    for key, label, display_key, explanation in _DIMENSIONS:
        ceiling = available.get(key) if isinstance(available, Mapping) else None
        used = committed.get(key) if isinstance(committed, Mapping) else None
        record: dict[str, object] = {
            'key': key,
            'label': label,
            'explanation': explanation,
            'budget': budget_display.get(display_key, 'N/A') if isinstance(budget_display, Mapping) else 'N/A',
            'committed': committed_display.get(display_key, 'N/A') if isinstance(committed_display, Mapping) else 'N/A',
            'headroom': headroom_display.get(display_key, 'N/A') if isinstance(headroom_display, Mapping) else 'N/A',
            'known': False,
            'percent': '0',
            'free_percent': '0',
            'shortfall': None,
            'state': 'Unknown' if key != 'storage_bytes' else 'Not Governed',
        }
        if ceiling is not None and used is not None:
            total = Decimal(str(ceiling))
            consumed = Decimal(str(used))
            if total > _ZERO and consumed >= _ZERO:
                bounded = min(consumed, total)
                record.update(
                    known=True,
                    percent=_share(bounded, total),
                    free_percent=_share(total - bounded, total),
                    state='Overcommitted' if consumed > total else 'Governed',
                )
            elif total == _ZERO:
                record.update(state='Exhausted' if consumed == _ZERO else 'Overcommitted')
            if consumed > total:
                shortfall = consumed - total
                # Canonical commitment units and display formatting remain #654-owned.
                values: dict[str, Decimal | None] = {dim[0]: None for dim in _DIMENSIONS}
                values[key] = shortfall
                record['shortfall'] = _vector_display(
                    CapacityVector(
                        cpu=values['cpu'],
                        memory_bytes=values['memory_bytes'],
                        pods=values['pods'],
                        storage_bytes=values['storage_bytes'],
                    )
                )[display_key]
        result.append(record)
    return result


def describe_tightest_headroom(bars: list[dict[str, Any]], state: str) -> str | None:
    """Explain the tightest committed headroom without reclassifying admission."""
    if state not in {'Near Capacity', 'Critical', 'Exhausted'}:
        return None
    if state == 'Exhausted':
        zero_budget = next((bar for bar in bars if bar['state'] == 'Exhausted'), None)
        if zero_budget:
            return f'Exhausted: {zero_budget["label"]} (zero governed budget)'
    governed = [bar for bar in bars if bar['known'] and bar['state'] == 'Governed']
    if not governed:
        return None
    tightest = min(governed, key=lambda bar: Decimal(str(bar['free_percent'])))
    return f'Lowest headroom: {tightest["label"]} ({tightest["free_percent"]}%)'


def filter_tenant_contribution_rows(rows: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    """Filter committed Tenant evidence without modifying its canonical allocation."""
    needle = query.strip().casefold()
    if not needle:
        return rows
    return [
        row
        for row in rows
        if needle in str(row['tenant'].name).casefold()
        or needle in str(row['tenant'].id).casefold()
        or needle in str(row['source']).casefold()
        or any(
            needle in str(namespace['name']).casefold() or needle in str(namespace['environment']).casefold()
            for namespace in row['namespaces']
        )
    ]


def summarize_tenant_contributions(rows: list[dict[str, Any]]) -> dict[str, int]:
    """Summarize the unfiltered committed contribution ledger for read-only presentation."""
    return {
        'tenants': len(rows),
        'namespaces': sum(int(row['namespace_count']) for row in rows),
        'shared': sum(row['source'] == 'Shared Tenant Quota' for row in rows),
        'attention': sum(bool(row['unknown']) for row in rows),
    }


def build_tenant_contribution_rows(cluster_id: str) -> list[dict[str, object]]:
    """Partition the same canonical ledger as #654, including shared-quota rules."""
    tenants = (
        Tenant.query.filter(
            Tenant.cluster_id == cluster_id,
            Tenant.lifecycle_status.notin_(_TERMINAL_TENANT_ALLOCATION_LIFECYCLES),
        )
        .order_by(Tenant.name.asc(), Tenant.id.asc())
        .all()
    )
    namespaces = (
        _active_namespace_allocation_query()
        .options(joinedload(TenantNamespace.environment).joinedload(TenantEnvironment.tenant))
        .filter(TenantNamespace.cluster_id == cluster_id)
        .order_by(TenantNamespace.namespace.asc())
        .all()
    )
    shared, ambiguous = _canonical_shared_allocation_quota(cluster_id)
    return _partition_tenant_contributions(tenants, namespaces, shared, ambiguous)


def _partition_tenant_contributions(
    tenants: list[Tenant],
    namespaces: list[TenantNamespace],
    shared: Mapping[str, Mapping[str, object]],
    ambiguous: list[str],
) -> list[dict[str, Any]]:
    """Pure read-model partition; match #654's shared and ambiguous accounting."""
    by_tenant: dict[str, list[TenantNamespace]] = defaultdict(list)
    for row in namespaces:
        if getattr(row, 'provisioning_status', None) in _TERMINAL_NAMESPACE_ALLOCATION_STATUSES:
            continue
        by_tenant[str(row.environment.tenant_id)].append(row)

    results = []
    for tenant in tenants:
        if getattr(tenant, 'lifecycle_status', None) in _TERMINAL_TENANT_ALLOCATION_LIFECYCLES:
            continue
        rows = by_tenant.get(str(tenant.id), [])
        if not rows and str(tenant.id) not in shared and str(tenant.id) not in ambiguous:
            continue
        quota = {str(tenant.id): shared[str(tenant.id)]} if str(tenant.id) in shared else {}
        vector, unbounded = _aggregate_committed_allocation(
            rows,
            shared_quota_by_tenant=quota,
            ambiguous_shared_tenants=[str(tenant.id)] if str(tenant.id) in ambiguous else [],
        )
        results.append(
            {
                'tenant': tenant,
                'namespace_count': len(rows),
                'allocation': _vector_display(vector),
                'unknown': bool(unbounded)
                or any(value is None for value in (vector.cpu, vector.memory_bytes, vector.pods, vector.storage_bytes)),
                'source': 'Shared Tenant Quota'
                if quota
                else 'Ambiguous Shared Quota'
                if str(tenant.id) in ambiguous
                else 'Namespace Quotas',
                'namespaces': [
                    {
                        'name': row.namespace,
                        'environment': row.environment.environment,
                        'state': row.provisioning_status,
                    }
                    for row in rows
                ],
            }
        )
    return results


def build_resource_profile_capacity_workspace(
    context: dict[str, Any], *, active_view: str, args: Any
) -> None:
    """Project committed Capacity/Allocation evidence into Resource Profile workspace."""
    capacity_search = str(args.get('capacity_search') or '').strip()
    allocation_view = str(args.get('allocation_view') or 'overview').strip().lower()
    if allocation_view not in {'overview', 'budget'}:
        allocation_view = 'overview'
    context['active_allocation_view'] = allocation_view
    capacity_environment = str(args.get('capacity_environment') or '').strip().lower()
    capacity_state = str(args.get('capacity_state') or '').strip()
    capacity_evidence = str(args.get('capacity_evidence') or '').strip().lower()
    capacity_resource = str(args.get('capacity_resource') or '').strip()
    if capacity_resource not in {'', 'cpu', 'memory_bytes', 'pods', 'storage_bytes'}:
        capacity_resource = ''
    capacity_rows = list(context.get('capacity_governance') or [])
    context['capacity_environment_options'] = sorted(
        {str(item['cluster'].environment).strip() for item in capacity_rows if item['cluster'].environment}
    )
    context['capacity_state_options'] = sorted({str(item['state']) for item in capacity_rows if item.get('state')})
    context['capacity_evidence_options'] = sorted(
        {str(item.get('snapshot_state') or 'unknown') for item in capacity_rows}
    )
    context['capacity_resource'] = capacity_resource
    _project_capacity_allocation_overview(
        context, capacity_rows=capacity_rows, active_view=active_view, allocation_view=allocation_view, args=args
    )
    _filter_capacity_governance_rows(
        context,
        capacity_rows=capacity_rows,
        args=args,
        filters={
            'search': capacity_search,
            'environment': capacity_environment,
            'state': capacity_state,
            'evidence': capacity_evidence,
            'resource': capacity_resource,
        },
    )


def _project_capacity_allocation_overview(
    context: dict[str, Any], *, capacity_rows: list[Any], active_view: str, allocation_view: str, args: Any
) -> None:
    # Read-only cluster visual projection uses the same committed #654 summaries
    # already resolved for this page. Only one cluster's Tenant contributions are
    # queried on the Capacity tab (no provider calls or speculative admission).
    selection = str(args.get('allocation_cluster_id') or '').strip()
    selected = next(
        (row for row in capacity_rows if str(row['cluster'].id) == selection),
        capacity_rows[0] if capacity_rows else None,
    )
    context['allocation_cluster_options'] = capacity_rows
    context['allocation_cluster_id'] = str(selected['cluster'].id) if selected else ''
    context['allocation_overview'] = None
    context['allocation_tenant_rows'] = []
    context['allocation_tenant_matches'] = 0
    context['allocation_tenant_total'] = 0
    context['allocation_tenant_summary'] = {'tenants': 0, 'namespaces': 0, 'shared': 0, 'attention': 0}
    allocation_search = str(args.get('allocation_search') or '').strip()
    context['allocation_search'] = allocation_search
    if active_view == 'capacity' and allocation_view == 'overview' and selected is not None:
        bars = build_tenant_allocation_bars(selected)
        context['allocation_overview'] = {
            'cluster': selected['cluster'],
            'summary': selected,
            'bars': bars,
            'tightest_headroom': describe_tightest_headroom(bars, selected['state']),
            'cutoff': present_user_datetime(selected.get('data_cutoff')),
        }
        tenant_rows = build_tenant_contribution_rows(str(selected['cluster'].id))
        context['allocation_tenant_total'] = len(tenant_rows)
        context['allocation_tenant_summary'] = summarize_tenant_contributions(tenant_rows)
        tenant_rows = filter_tenant_contribution_rows(tenant_rows, allocation_search)
        context['allocation_tenant_rows'] = tenant_rows
        context['allocation_tenant_matches'] = len(tenant_rows)


def _filter_capacity_governance_rows(
    context: dict[str, Any], *, capacity_rows: list[Any], args: Any, filters: dict[str, str]
) -> None:
    capacity_search = filters['search']
    capacity_environment = filters['environment']
    capacity_state = filters['state']
    capacity_evidence = filters['evidence']
    if capacity_search:
        needle = capacity_search.casefold()
        capacity_rows = [
            item
            for item in capacity_rows
            if needle in str(item['cluster'].name).casefold() or needle in str(item['cluster'].environment).casefold()
        ]
    if capacity_environment:
        capacity_rows = [
            item for item in capacity_rows if str(item['cluster'].environment).lower() == capacity_environment
        ]
    if capacity_state:
        capacity_rows = [item for item in capacity_rows if item['state'] == capacity_state]
    if capacity_evidence:
        capacity_rows = [
            item for item in capacity_rows if str(item.get('snapshot_state') or 'unknown').lower() == capacity_evidence
        ]
    capacity_items, capacity_pagination = paginate_sequence(
        capacity_rows,
        page=args.get('capacity_page', 1, type=int) or 1,
        per_page=args.get('capacity_per_page', 5, type=int) or 5,
    )
    context['capacity_governance'] = capacity_items
    # Reuse the read-only #1034 presentation percentages for each visible
    # committed #654 Allocation Budget row; no new evidence or admission path.
    context['capacity_budget_bars'] = {
        str(item['cluster'].id): build_tenant_allocation_bars(item) for item in capacity_items
    }
    context['capacity_pagination'] = capacity_pagination
    context['capacity_filters'] = filters

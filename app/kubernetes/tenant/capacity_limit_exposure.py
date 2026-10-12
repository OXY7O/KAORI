"""Committed CPU/Memory limit exposure, separate from request-based admission.

Provider ResourceQuota hard limits are maximum declared ceilings, not actual
node utilization or guaranteed scheduling. Missing limits are Unknown, not 0.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.kubernetes.tenant.capacity import CapacityVector

_ZERO = Decimal('0')
_HUNDRED = Decimal('100')


def _display_limit_cpu(value: Decimal | None) -> str:
    return 'N/A' if value is None else f'{value.quantize(Decimal("0.01"))} cores'


def _display_limit_memory(value: Decimal | None) -> str:
    return 'N/A' if value is None else f'{(value / Decimal(1024**3)).quantize(Decimal("0.01"))} GiB'


def limit_exposure_threshold(budget: CapacityVector, *, cpu_ratio: Decimal, memory_ratio: Decimal) -> CapacityVector:
    return CapacityVector(
        cpu=budget.cpu * cpu_ratio if budget.cpu is not None else None,
        memory_bytes=budget.memory_bytes * memory_ratio if budget.memory_bytes is not None else None,
    )


def assess_limit_exposure(
    *,
    committed: CapacityVector,
    budget: CapacityVector | None,
    mode: str,
    cpu_ratio: Decimal,
    memory_ratio: Decimal,
    evidence_ready: bool,
    unknown_sources: list[str] | None = None,
) -> dict[str, Any]:
    """Return honest planning evidence. This function cannot authorize a write."""
    ceiling = (
        limit_exposure_threshold(budget, cpu_ratio=cpu_ratio, memory_ratio=memory_ratio)
        if budget is not None else CapacityVector(cpu=None, memory_bytes=None)
    )
    missing = (
        not evidence_ready or budget is None
        or any(value is None for value in (
            committed.cpu, committed.memory_bytes, ceiling.cpu, ceiling.memory_bytes,
        ))
        or bool(unknown_sources)
    )
    if missing:
        state = 'Unknown'
        reason = 'Committed limits or fresh governed capacity evidence are incomplete.'
    else:
        assert committed.cpu is not None and committed.memory_bytes is not None
        assert ceiling.cpu is not None and ceiling.memory_bytes is not None
        return _assess_known_limits(
            committed=committed, ceiling=ceiling, mode=mode,
            cpu_ratio=cpu_ratio, memory_ratio=memory_ratio,
        )
    return {
        'mode': mode,
        'state': state,
        'reason': reason,
        'scope': 'committed_resourcequota_limits',
        'cpu_ratio': format(cpu_ratio, 'f'),
        'memory_ratio': format(memory_ratio, 'f'),
        'committed': {
            'cpu': None if committed.cpu is None else format(committed.cpu, 'f'),
            'memory_bytes': None if committed.memory_bytes is None else format(committed.memory_bytes, 'f'),
        },
        'threshold': {
            'cpu': None if ceiling.cpu is None else format(ceiling.cpu, 'f'),
            'memory_bytes': None if ceiling.memory_bytes is None else format(ceiling.memory_bytes, 'f'),
        },
        'display': {
            'cpu_committed': _display_limit_cpu(committed.cpu),
            'cpu_threshold': _display_limit_cpu(ceiling.cpu),
            'memory_committed': _display_limit_memory(committed.memory_bytes),
            'memory_threshold': _display_limit_memory(ceiling.memory_bytes),
        },
        'unknown_sources': list(unknown_sources or []),
        'planning_only': True,
        'capacity_approval': False,
    }


def _assess_known_limits(
    *, committed: CapacityVector, ceiling: CapacityVector,
    mode: str, cpu_ratio: Decimal, memory_ratio: Decimal,
) -> dict[str, Any]:
    assert committed.cpu is not None and committed.memory_bytes is not None
    assert ceiling.cpu is not None and ceiling.memory_bytes is not None
    if committed.cpu > ceiling.cpu or committed.memory_bytes > ceiling.memory_bytes:
        state = 'Overcommitted'
        reason = 'Committed CPU/Memory Limit Exposure exceeds operator policy thresholds.'
    else:
        cpu_percent = committed.cpu * _HUNDRED / ceiling.cpu if ceiling.cpu else None
        mem_percent = committed.memory_bytes * _HUNDRED / ceiling.memory_bytes if ceiling.memory_bytes else None
        state = (
            'Near Capacity' if any(value is not None and value >= Decimal('90') for value in (cpu_percent, mem_percent))
            else 'Healthy'
        )
        reason = 'Limit exposure is within the configured planning thresholds.'
    return {
        'mode': mode,
        'state': state,
        'reason': reason,
        'scope': 'committed_resourcequota_limits',
        'cpu_ratio': format(cpu_ratio, 'f'),
        'memory_ratio': format(memory_ratio, 'f'),
        'committed': {
            'cpu': None if committed.cpu is None else format(committed.cpu, 'f'),
            'memory_bytes': None if committed.memory_bytes is None else format(committed.memory_bytes, 'f'),
        },
        'threshold': {
            'cpu': None if ceiling.cpu is None else format(ceiling.cpu, 'f'),
            'memory_bytes': None if ceiling.memory_bytes is None else format(ceiling.memory_bytes, 'f'),
        },
        'display': {
            'cpu_committed': _display_limit_cpu(committed.cpu),
            'cpu_threshold': _display_limit_cpu(ceiling.cpu),
            'memory_committed': _display_limit_memory(committed.memory_bytes),
            'memory_threshold': _display_limit_memory(ceiling.memory_bytes),
        },
        'unknown_sources': [],
        'planning_only': True,
        'capacity_approval': False,
    }

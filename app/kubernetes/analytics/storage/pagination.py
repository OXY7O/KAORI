from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def _positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _per_page(value: Any, allowed: Sequence[int], default: int) -> int:
    parsed = _positive_int(value, default)
    return parsed if parsed in allowed else default


def resolve_storage_pagination(
    query_args: Mapping[str, Any],
    *,
    allowed_per_page: Sequence[int] = (5, 10, 25, 50),
    default_per_page: int = 5,
) -> dict[str, dict[str, int]]:
    """Resolve independent filesystem, PVC, and PV pagination state."""
    return {
        'filesystem': {
            'page': _positive_int(query_args.get('filesystem_page'), 1),
            'per_page': _per_page(
                query_args.get('filesystem_per_page'),
                allowed_per_page,
                default_per_page,
            ),
        },
        'pvc': {
            'page': _positive_int(query_args.get('pvc_page'), 1),
            'per_page': _per_page(
                query_args.get('pvc_per_page'),
                allowed_per_page,
                default_per_page,
            ),
        },
        'pv': {
            'page': _positive_int(query_args.get('pv_page'), 1),
            'per_page': _per_page(
                query_args.get('pv_per_page'),
                allowed_per_page,
                default_per_page,
            ),
        },
    }

from __future__ import annotations

from collections.abc import Callable


def validate_then_apply[_ResultT](
    *,
    validate: Callable[[], object],
    apply: Callable[[], _ResultT],
    prepare_apply: Callable[[], object] | None = None,
) -> _ResultT:
    """Run validation before a Kubernetes mutation and abort apply on failure."""
    validate()
    if prepare_apply is not None:
        prepare_apply()
    return apply()

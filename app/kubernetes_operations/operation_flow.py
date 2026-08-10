from __future__ import annotations

from collections.abc import Callable


def validate_then_apply[ResultT](
    *,
    validate: Callable[[], object],
    apply: Callable[[], ResultT],
    prepare_apply: Callable[[], object] | None = None,
) -> ResultT:
    """Run validation before a Kubernetes mutation and abort apply on failure."""
    validate()
    if prepare_apply is not None:
        prepare_apply()
    return apply()

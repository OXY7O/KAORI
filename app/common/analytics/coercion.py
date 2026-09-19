from __future__ import annotations

from typing import Any

__all__ = ['as_dict', 'as_list', 'safe_float', 'safe_int']


def as_dict(value: Any) -> dict[str, Any]:
    """Return a mapping payload or an empty canonical dictionary."""
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    """Return a list payload or an empty canonical list."""
    return value if isinstance(value, list) else []


def safe_float(value: Any) -> float:
    """Coerce supported scalar values to float without leaking parse errors."""
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, int | float | str):
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
    return 0.0


def safe_int(value: Any) -> int:
    """Round the canonical float coercion to an integer."""
    return int(round(safe_float(value)))

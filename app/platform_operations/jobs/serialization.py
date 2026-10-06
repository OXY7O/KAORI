from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import UUID


def to_json_compatible(value: Any) -> Any:
    """Return a recursively JSON-compatible representation for job telemetry.

    Job payloads, result summaries, and automatic Activity Audit metadata are
    persisted in PostgreSQL JSON columns. Operational results can legitimately
    contain datetime-like and other scalar value objects, so normalize those at
    the job boundary instead of allowing terminal lifecycle commits to fail.
    """

    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return to_json_compatible(value.value)
    if isinstance(value, (UUID, Path)):
        return str(value)
    if is_dataclass(value) and not isinstance(value, type):
        return to_json_compatible(asdict(value))
    if isinstance(value, dict):
        return {str(key): to_json_compatible(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_json_compatible(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return [to_json_compatible(item) for item in sorted(value, key=str)]

    raise TypeError(f'Unsupported job JSON value: {type(value).__name__}')

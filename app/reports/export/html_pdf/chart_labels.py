from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(slots=True)
class _LabelPosition:
    key: str
    y: float


def resolve_vertical_labels(
    labels: Sequence[tuple[str, float]],
    *,
    min_y: float,
    max_y: float,
    min_gap: float,
) -> dict[str, float]:
    """Return collision-safe vertical label positions.

    Data-point coordinates remain unchanged. Only the annotation positions are
    adjusted inside a dedicated label gutter, preserving analytical accuracy
    while guaranteeing a minimum readable separation.
    """

    if not labels:
        return {}

    ordered = sorted(((key, max(min_y, min(max_y, y))) for key, y in labels), key=lambda item: item[1])
    resolved = [_LabelPosition(key=key, y=y) for key, y in ordered]

    for index in range(1, len(resolved)):
        previous_y = resolved[index - 1].y
        current_y = resolved[index].y
        if current_y - previous_y < min_gap:
            resolved[index].y = previous_y + min_gap

    overflow = resolved[-1].y - max_y
    if overflow > 0:
        for item in resolved:
            item.y -= overflow

    for index in range(len(resolved) - 2, -1, -1):
        next_y = resolved[index + 1].y
        current_y = resolved[index].y
        if next_y - current_y < min_gap:
            resolved[index].y = next_y - min_gap

    underflow = min_y - resolved[0].y
    if underflow > 0:
        for item in resolved:
            item.y += underflow

    return {item.key: item.y for item in resolved}

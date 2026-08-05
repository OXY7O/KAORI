from __future__ import annotations

from collections.abc import Sequence


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
    resolved: list[list[object]] = [[key, y] for key, y in ordered]

    for index in range(1, len(resolved)):
        previous_y = float(resolved[index - 1][1])
        current_y = float(resolved[index][1])
        if current_y - previous_y < min_gap:
            resolved[index][1] = previous_y + min_gap

    overflow = float(resolved[-1][1]) - max_y
    if overflow > 0:
        for item in resolved:
            item[1] = float(item[1]) - overflow

    for index in range(len(resolved) - 2, -1, -1):
        next_y = float(resolved[index + 1][1])
        current_y = float(resolved[index][1])
        if next_y - current_y < min_gap:
            resolved[index][1] = next_y - min_gap

    underflow = min_y - float(resolved[0][1])
    if underflow > 0:
        for item in resolved:
            item[1] = float(item[1]) + underflow

    return {str(key): float(y) for key, y in resolved}

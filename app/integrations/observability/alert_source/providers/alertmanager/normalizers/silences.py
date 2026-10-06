from __future__ import annotations

from typing import Any


def normalize_silences(
    silences: list[dict[str, Any]],
    *,
    source_instance_id: int | None,
    source_instance_name: str,
) -> list[dict[str, Any]]:
    return [
        normalize_silence(
            item,
            source_instance_id=source_instance_id,
            source_instance_name=source_instance_name,
        )
        for item in silences
    ]


def normalize_silence(
    silence: dict[str, Any],
    *,
    source_instance_id: int | None,
    source_instance_name: str,
) -> dict[str, Any]:
    normalized = dict(silence)
    normalized['source_instance_id'] = source_instance_id
    normalized['source_instance_name'] = source_instance_name
    normalized['source'] = 'alertmanager'
    return normalized

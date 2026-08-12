from __future__ import annotations

from collections.abc import Iterable


def compact_readiness_reason(value: object) -> str:
    """Normalize persisted Kubernetes readiness copy for compact UI surfaces."""
    text = ' '.join(str(value or '').split()).strip()
    if not text:
        return ''

    lowered = text.lower()
    if 'legacy lifecycle band' in lowered and lowered.startswith('kubernetes '):
        subject = text.split(' is ', 1)[0].strip()
        if subject:
            return f'{subject} is in a legacy lifecycle band. Plan an upgrade.'

    return text


def compact_readiness_reasons(values: Iterable[object]) -> list[str]:
    return [reason for item in values if (reason := compact_readiness_reason(item))]

from __future__ import annotations

from collections.abc import Iterable


def compact_readiness_reason(value: object) -> str:
    """Normalize persisted Kubernetes readiness copy for compact UI surfaces."""
    text = ' '.join(str(value or '').split()).strip()
    if not text:
        return ''

    lowered = text.lower()
    if 'kaori extended lifecycle support' in lowered and lowered.startswith('kubernetes '):
        subject = text.split(' is ', 1)[0].strip()
        if subject:
            return f'{subject} uses KAORI Extended support. Upgrade recommended.'

    if 'optional capability access is unavailable for:' in lowered:
        return 'Optional gaps do not affect core readiness.'

    if 'legacy lifecycle band' in lowered and lowered.startswith('kubernetes '):
        subject = text.split(' is ', 1)[0].strip()
        if subject:
            return f'{subject} is in a legacy lifecycle band. Plan an upgrade.'

    return text


def compact_readiness_reasons(values: Iterable[object]) -> list[str]:
    reasons = [reason for item in values if (reason := compact_readiness_reason(item))]
    optional_reason = 'Optional gaps do not affect core readiness.'
    extended_suffix = ' uses KAORI Extended support. Upgrade recommended.'
    extended_index = next(
        (index for index, reason in enumerate(reasons) if extended_suffix in reason),
        None,
    )
    if extended_index is None or optional_reason not in reasons:
        return reasons

    optional_index = reasons.index(optional_reason)
    merged_index = min(extended_index, optional_index)
    extended_reason = reasons[extended_index]
    merged_reason = (
        extended_reason.removesuffix(' Upgrade recommended.')
        + ' Upgrade recommended; optional gaps do not affect core readiness.'
    )

    compacted: list[str] = []
    for index, reason in enumerate(reasons):
        if index == merged_index:
            compacted.append(merged_reason)
        if index in {extended_index, optional_index}:
            continue
        compacted.append(reason)
    return compacted

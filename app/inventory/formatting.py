from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

def _parse_kubernetes_size_bytes(
    value: str | int | float | None,
) -> Decimal | None:
    if value is None:
        return None

    raw = str(value).strip()
    if not raw or raw == '-':
        return None

    units = {
        'Ki': Decimal(1024),
        'Mi': Decimal(1024) ** 2,
        'Gi': Decimal(1024) ** 3,
        'Ti': Decimal(1024) ** 4,
        'Pi': Decimal(1024) ** 5,
        'Ei': Decimal(1024) ** 6,
        'K': Decimal(1000),
        'M': Decimal(1000) ** 2,
        'G': Decimal(1000) ** 3,
        'T': Decimal(1000) ** 4,
        'P': Decimal(1000) ** 5,
        'E': Decimal(1000) ** 6,
    }

    try:
        for suffix in sorted(units, key=len, reverse=True):
            if raw.endswith(suffix):
                number = Decimal(raw.removesuffix(suffix))
                return number * units[suffix]

        return Decimal(raw)
    except (InvalidOperation, ValueError, TypeError):
        return None


def _format_decimal(value: Decimal, decimals: int = 1) -> str:
    quantized = round(value, decimals)
    if quantized == quantized.to_integral():
        return str(int(quantized))
    return f'{quantized:.{decimals}f}'.rstrip('0').rstrip('.')


def format_kubernetes_size(
    value: str | int | float | None,
) -> str:
    size_bytes = _parse_kubernetes_size_bytes(value)

    if size_bytes is None or size_bytes < 0:
        return '-'

    units = [
        ('PiB', Decimal(1024) ** 5),
        ('TiB', Decimal(1024) ** 4),
        ('GiB', Decimal(1024) ** 3),
        ('MiB', Decimal(1024) ** 2),
        ('KiB', Decimal(1024)),
    ]

    for label, divisor in units:
        if size_bytes >= divisor:
            return f'{_format_decimal(size_bytes / divisor)} {label}'

    return f'{int(size_bytes)} B'


def format_byte_count(
    value: int | None,
) -> str:
    return format_kubernetes_size(value)


def convert_ki_to_gib(
    value: str | None,
) -> float:
    size_bytes = _parse_kubernetes_size_bytes(value)
    if size_bytes is None:
        return 0
    return round(float(size_bytes / (Decimal(1024) ** 3)), 1)


def convert_storage_to_gib(
    value: str | None,
) -> float:
    return convert_ki_to_gib(value)


def format_gib(
    value: float,
) -> str:
    if value <= 0:
        return '-'
    return f'{value:g} GiB'


def format_quota_value(
    resource_name: str,
    value: str | None,
) -> str:
    if not value:
        return '-'

    size_markers = (
        'memory',
        'storage',
        'ephemeral-storage',
    )

    if any(marker in resource_name.lower() for marker in size_markers):
        return format_kubernetes_size(value)

    return value



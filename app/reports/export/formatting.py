from __future__ import annotations


def slugify(
    value: str,
) -> str:
    normalized = ''.join(character.lower() if character.isalnum() else '-' for character in value)
    parts = [part for part in normalized.split('-') if part]
    return '-'.join(parts)[:80] or 'report'


def format_period(
    value: str,
) -> str:
    labels = {
        'snapshot': 'Current Inventory Snapshot',
        '24h': 'Last 24 Hours',
        '7d': 'Last 7 Days',
        '30d': 'Last 30 Days',
        '90d': 'Last 90 Days',
        'month': 'This Month',
    }
    return labels.get(value, value)

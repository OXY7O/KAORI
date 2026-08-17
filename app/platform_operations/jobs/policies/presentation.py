from __future__ import annotations


def present_interval(minutes: int | None, *, empty: str = 'Not Scheduled') -> str:
    if minutes is None:
        return empty
    value = max(int(minutes), 0)
    if value < 60:
        return f'{value} Minute' if value == 1 else f'{value} Minutes'
    hours, remainder = divmod(value, 60)
    hours_label = f'{hours} Hour' if hours == 1 else f'{hours} Hours'
    if remainder == 0:
        return hours_label
    return f'{hours_label} {remainder} Minutes'

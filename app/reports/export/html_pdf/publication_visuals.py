from __future__ import annotations

from html import escape


def _donut_label_lines(label: str) -> tuple[str, ...]:
    words = [word for word in label.split() if word]
    if len(words) <= 1:
        return (label,)
    if len(words) == 2:
        return words[0], words[1]
    midpoint = max(1, len(words) // 2)
    return ' '.join(words[:midpoint]), ' '.join(words[midpoint:])


def count_donut_svg(count: int, label: str) -> str:
    safe_count = max(0, count)
    lines = _donut_label_lines(label)
    label_markup = ''.join(
        f'<tspan x="90" dy="{0 if index == 0 else 8.5}">{escape(line)}</tspan>' for index, line in enumerate(lines)
    )
    return (
        '<svg viewBox="0 0 180 180" role="img" aria-label="'
        + escape(f'{safe_count} {label}')
        + '"><circle cx="90" cy="90" r="55" fill="none" stroke="#E2E8F0" stroke-width="24"/>'
        '<circle cx="90" cy="90" r="55" fill="none" stroke="#7C3AED" stroke-width="24" '
        'stroke-dasharray="345.6 345.6" transform="rotate(-90 90 90)"/>'
        f'<text x="90" y="82" text-anchor="middle" font-size="30" font-weight="700" fill="#172033">{safe_count}</text>'
        f'<text x="90" y="103" text-anchor="middle" font-size="7" fill="#64748B">{label_markup}</text></svg>'
    )

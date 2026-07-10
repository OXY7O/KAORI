from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import KeepTogether, Paragraph, Spacer, Table, TableStyle

from app.reports.export.constants import SECTION_DESCRIPTIONS, SECTION_LABELS
from app.reports.export.styles import (
    build_pdf_styles,
    default_grid_table_style,
    default_metadata_table_style,
)


def build_status_banner(
    label: str,
    description: str,
) -> Table:
    table = Table(
        [
            [
                label,
                Paragraph(
                    safe_text(
                        description,
                    ),
                    build_pdf_styles()['small'],
                ),
            ]
        ],
        colWidths=[
            4.2 * cm,
            12.0 * cm,
        ],
    )

    table.setStyle(
        TableStyle(
            [
                (
                    'BACKGROUND',
                    (
                        0,
                        0,
                    ),
                    (
                        -1,
                        -1,
                    ),
                    colors.HexColor(
                        '#eff6ff',
                    ),
                ),
                (
                    'TEXTCOLOR',
                    (
                        0,
                        0,
                    ),
                    (
                        0,
                        0,
                    ),
                    colors.HexColor(
                        '#1d4ed8',
                    ),
                ),
                (
                    'FONTNAME',
                    (
                        0,
                        0,
                    ),
                    (
                        0,
                        0,
                    ),
                    'Helvetica-Bold',
                ),
                (
                    'FONTSIZE',
                    (
                        0,
                        0,
                    ),
                    (
                        -1,
                        -1,
                    ),
                    8.5,
                ),
                (
                    'BOX',
                    (
                        0,
                        0,
                    ),
                    (
                        -1,
                        -1,
                    ),
                    0.5,
                    colors.HexColor(
                        '#bfdbfe',
                    ),
                ),
                (
                    'LEFTPADDING',
                    (
                        0,
                        0,
                    ),
                    (
                        -1,
                        -1,
                    ),
                    8,
                ),
                (
                    'RIGHTPADDING',
                    (
                        0,
                        0,
                    ),
                    (
                        -1,
                        -1,
                    ),
                    8,
                ),
                (
                    'TOPPADDING',
                    (
                        0,
                        0,
                    ),
                    (
                        -1,
                        -1,
                    ),
                    7,
                ),
                (
                    'BOTTOMPADDING',
                    (
                        0,
                        0,
                    ),
                    (
                        -1,
                        -1,
                    ),
                    7,
                ),
                (
                    'VALIGN',
                    (
                        0,
                        0,
                    ),
                    (
                        -1,
                        -1,
                    ),
                    'TOP',
                ),
            ]
        )
    )

    return table


def build_single_section_content(
    section: str,
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    section_label = SECTION_LABELS.get(
        section,
        section.replace(
            '_',
            ' ',
        ).title(),
    )

    section_description = SECTION_DESCRIPTIONS.get(
        section,
        'Prepared report section for future data integration.',
    )

    rows = [
        [
            'Content Status',
            'Prepared',
        ],
        [
            'Data Source',
            'Pending analytics payload integration',
        ],
        [
            'Current Output',
            section_description,
        ],
    ]

    table = Table(
        rows,
        colWidths=[
            4.0 * cm,
            12.2 * cm,
        ],
    )

    table.setStyle(
        default_metadata_table_style(),
    )

    return [
        KeepTogether(
            [
                Paragraph(
                    safe_text(
                        section_label,
                    ),
                    styles['small_section_title'],
                ),
                table,
                Spacer(
                    1,
                    0.25 * cm,
                ),
            ]
        )
    ]


def build_key_value_table(
    rows: list[list[Any]],
    styles: dict[str, ParagraphStyle],
) -> Table:
    table_rows = [
        [
            _pdf_paragraph(
                row[0],
                styles,
            ),
            _pdf_paragraph(
                row[1],
                styles,
            ),
        ]
        for row in rows
    ]

    table = Table(
        table_rows,
        colWidths=[
            4.4 * cm,
            11.8 * cm,
        ],
    )

    table.setStyle(
        default_metadata_table_style(),
    )

    return table


def build_pdf_table(
    rows: list[list[Any]],
    styles: dict[str, ParagraphStyle],
    col_widths: list[float],
) -> Table:
    table_rows: list[list[Any]] = []

    for row in rows:
        table_rows.append(
            [
                _pdf_paragraph(
                    cell,
                    styles,
                )
                for cell in row
            ]
        )

    table = Table(
        table_rows,
        colWidths=col_widths,
        repeatRows=1,
    )

    table.setStyle(
        default_grid_table_style(),
    )

    return table


def _pdf_paragraph(
    value: Any,
    styles: dict[str, ParagraphStyle],
) -> Paragraph:
    return Paragraph(
        safe_text(
            _pdf_value(
                value,
            )
        ),
        styles['small'],
    )


def _as_pdf_list(
    value: Any,
) -> list[Any]:
    if isinstance(
        value,
        list,
    ):
        return value

    return []


def _pdf_nested_label(
    row: dict[str, Any],
    key: str,
) -> str:
    value = row.get(
        key,
        {},
    )

    if isinstance(
        value,
        dict,
    ):
        return _pdf_value(
            value.get(
                'label',
                '-',
            )
        )

    return _pdf_value(
        value,
    )


def format_forecast_eta(
    eta: Any,
) -> str:
    if not isinstance(
        eta,
        dict,
    ):
        return '-'

    label = _pdf_value(
        eta.get(
            'label',
            '-',
        )
    )

    date = eta.get(
        'date',
    )

    resource = eta.get(
        'resource',
    )

    parts = [
        label,
    ]

    if date:
        parts.append(
            str(
                date,
            )
        )

    if resource:
        parts.append(
            str(
                resource,
            )
        )

    return ' · '.join(
        parts,
    )


def _safe_pdf_float(
    value: Any,
) -> float:
    if isinstance(
        value,
        bool,
    ):
        return float(
            value,
        )

    if isinstance(
        value,
        int | float | str,
    ):
        try:
            return float(
                value,
            )
        except (
            TypeError,
            ValueError,
        ):
            return 0.0

    return 0.0


def _pdf_value(
    value: Any,
) -> str:
    if value is None:
        return '-'

    if isinstance(
        value,
        bool,
    ):
        return 'Yes' if value else 'No'

    return str(
        value,
    )


def _format_resource_number(
    value: Any,
) -> str:
    if value is None:
        return '0'

    try:
        number = float(
            value,
        )
    except (
        TypeError,
        ValueError,
    ):
        return str(
            value,
        )

    if number.is_integer():
        return str(
            int(
                number,
            )
        )

    return f'{number:.2f}'


def slugify(
    value: str,
) -> str:
    normalized = ''.join(character.lower() if character.isalnum() else '-' for character in value)

    parts = [
        part
        for part in normalized.split(
            '-',
        )
        if part
    ]

    return (
        '-'.join(
            parts,
        )[:80]
        or 'report'
    )


def format_period(
    value: str,
) -> str:
    labels = {
        '24h': 'Last 24 hours',
        '7d': 'Last 7 days',
        '30d': 'Last 30 days',
        '90d': 'Last 90 days',
        'month': 'This month',
    }

    return labels.get(
        value,
        value,
    )


def format_datetime(
    value: datetime | None,
) -> str:
    if value is None:
        return '-'

    return value.strftime(
        '%d %b %Y %H:%M UTC',
    )


def safe_text(
    value: Any,
) -> str:
    return escape(
        str(
            value,
        )
    )

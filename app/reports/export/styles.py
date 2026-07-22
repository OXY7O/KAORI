from __future__ import annotations

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import SimpleDocTemplate, TableStyle


def build_pdf_styles() -> dict[str, ParagraphStyle]:
    base_styles = getSampleStyleSheet()

    return {
        'title': ParagraphStyle(
            'KAORIReportTitle',
            parent=base_styles['Title'],
            fontName='Helvetica-Bold',
            fontSize=24,
            leading=30,
            textColor=colors.HexColor(
                '#0f172a',
            ),
            alignment=TA_CENTER,
            spaceAfter=10,
        ),
        'subtitle': ParagraphStyle(
            'KAORIReportSubtitle',
            parent=base_styles['Normal'],
            fontName='Helvetica',
            fontSize=9,
            leading=13,
            textColor=colors.HexColor(
                '#475569',
            ),
            alignment=TA_CENTER,
            spaceAfter=12,
        ),
        'section_title': ParagraphStyle(
            'KAORIReportSectionTitle',
            parent=base_styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=13,
            leading=17,
            textColor=colors.HexColor(
                '#1d4ed8',
            ),
            spaceBefore=8,
            spaceAfter=8,
        ),
        'small_section_title': ParagraphStyle(
            'KAORIReportSmallSectionTitle',
            parent=base_styles['Heading3'],
            fontName='Helvetica-Bold',
            fontSize=10,
            leading=14,
            textColor=colors.HexColor(
                '#0f172a',
            ),
            spaceBefore=6,
            spaceAfter=5,
        ),
        'normal': ParagraphStyle(
            'KAORIReportNormal',
            parent=base_styles['Normal'],
            fontName='Helvetica',
            fontSize=9,
            leading=13,
            textColor=colors.HexColor(
                '#334155',
            ),
            alignment=TA_LEFT,
        ),
        'small': ParagraphStyle(
            'KAORIReportSmall',
            parent=base_styles['Normal'],
            fontName='Helvetica',
            fontSize=8,
            leading=11,
            textColor=colors.HexColor(
                '#64748b',
            ),
        ),
        'muted': ParagraphStyle(
            'KAORIReportMuted',
            parent=base_styles['Normal'],
            fontName='Helvetica',
            fontSize=8,
            leading=11,
            textColor=colors.HexColor(
                '#94a3b8',
            ),
        ),
    }


def default_metadata_table_style() -> TableStyle:
    return TableStyle(
        [
            (
                'BACKGROUND',
                (
                    0,
                    0,
                ),
                (
                    0,
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
                    -1,
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
                    -1,
                ),
                'Helvetica-Bold',
            ),
            (
                'FONTNAME',
                (
                    1,
                    0,
                ),
                (
                    1,
                    -1,
                ),
                'Helvetica',
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
                'GRID',
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
                    '#cbd5e1',
                ),
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
        ]
    )


def default_grid_table_style() -> TableStyle:
    return TableStyle(
        [
            (
                'BACKGROUND',
                (
                    0,
                    0,
                ),
                (
                    -1,
                    0,
                ),
                colors.HexColor(
                    '#1d4ed8',
                ),
            ),
            (
                'TEXTCOLOR',
                (
                    0,
                    0,
                ),
                (
                    -1,
                    0,
                ),
                colors.white,
            ),
            (
                'FONTNAME',
                (
                    0,
                    0,
                ),
                (
                    -1,
                    0,
                ),
                'Helvetica-Bold',
            ),
            (
                'FONTNAME',
                (
                    0,
                    1,
                ),
                (
                    -1,
                    -1,
                ),
                'Helvetica',
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
                'GRID',
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
                    '#cbd5e1',
                ),
            ),
            (
                'ROWBACKGROUNDS',
                (
                    0,
                    1,
                ),
                (
                    -1,
                    -1,
                ),
                [
                    colors.white,
                    colors.HexColor(
                        '#f8fafc',
                    ),
                ],
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
        ]
    )


def draw_page_footer(
    canvas: Canvas,
    doc: SimpleDocTemplate,
) -> None:
    canvas.saveState()

    page_width, _page_height = A4

    footer_y = 1.0 * cm

    canvas.setStrokeColor(
        colors.HexColor(
            '#cbd5e1',
        )
    )
    canvas.setLineWidth(
        0.5,
    )
    canvas.line(
        1.5 * cm,
        footer_y + 0.35 * cm,
        page_width - 1.5 * cm,
        footer_y + 0.35 * cm,
    )

    canvas.setFont(
        'Helvetica',
        7,
    )
    canvas.setFillColor(
        colors.HexColor(
            '#64748b',
        )
    )

    canvas.drawString(
        1.5 * cm,
        footer_y,
        'KAORI • Generated operational report',
    )

    canvas.drawRightString(
        page_width - 1.5 * cm,
        footer_y,
        f'Page {doc.page}',
    )

    canvas.restoreState()

from __future__ import annotations

from typing import Any, Final

from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.worksheet import Worksheet

KAORI_PRIMARY: Final = '7C3AED'
KAORI_PRIMARY_DARK: Final = '5B21B6'
KAORI_PRIMARY_SOFT: Final = 'EDE9FE'
KAORI_INK: Final = '111827'
KAORI_MUTED: Final = '64748B'
KAORI_LINE: Final = 'CBD5E1'
KAORI_LINE_LIGHT: Final = 'E2E8F0'
KAORI_PANEL: Final = 'F8FAFC'
KAORI_GREEN_FILL: Final = 'DCFCE7'
KAORI_GREEN_TEXT: Final = '166534'
KAORI_AMBER_FILL: Final = 'FEF3C7'
KAORI_AMBER_TEXT: Final = '92400E'
KAORI_RED_FILL: Final = 'FEE2E2'
KAORI_RED_TEXT: Final = '991B1B'
KAORI_BLUE_FILL: Final = 'DBEAFE'
KAORI_BLUE_TEXT: Final = '1E40AF'
KAORI_SLATE_FILL: Final = 'F1F5F9'
KAORI_SLATE_TEXT: Final = '475569'
KAORI_WHITE: Final = 'FFFFFF'

BODY_FONT: Final = 'Aptos'
TITLE_FONT: Final = 'Aptos Display'

THIN_LINE: Final = Side(style='thin', color=KAORI_LINE_LIGHT)
HEADER_BORDER: Final = Border(
    left=Side(style='thin', color=KAORI_PRIMARY_DARK),
    right=Side(style='thin', color=KAORI_PRIMARY_DARK),
    top=Side(style='thin', color=KAORI_PRIMARY_DARK),
    bottom=Side(style='thin', color=KAORI_PRIMARY_DARK),
)
BODY_BORDER: Final = Border(bottom=THIN_LINE)


def style_title(cell: Any) -> None:
    cell.font = Font(name=TITLE_FONT, size=16, bold=True, color=KAORI_WHITE)
    cell.fill = PatternFill('solid', fgColor=KAORI_PRIMARY_DARK)
    cell.alignment = Alignment(horizontal='left', vertical='center')


def style_subtitle(cell: Any) -> None:
    cell.font = Font(name=BODY_FONT, size=10, color=KAORI_INK)
    cell.fill = PatternFill('solid', fgColor=KAORI_PRIMARY_SOFT)
    cell.alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)


def style_context(cell: Any) -> None:
    cell.font = Font(name=BODY_FONT, size=9, color=KAORI_MUTED)
    cell.fill = PatternFill('solid', fgColor=KAORI_PANEL)
    cell.border = Border(bottom=THIN_LINE)
    cell.alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)


def style_header(cell: Any) -> None:
    cell.font = Font(name=BODY_FONT, size=10, bold=True, color=KAORI_WHITE)
    cell.fill = PatternFill('solid', fgColor=KAORI_PRIMARY)
    cell.border = HEADER_BORDER
    cell.alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)


def style_body(cell: Any, *, alternate: bool = False) -> None:
    cell.font = Font(name=BODY_FONT, size=9, color=KAORI_INK)
    cell.border = BODY_BORDER
    cell.alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)
    if alternate:
        cell.fill = PatternFill('solid', fgColor=KAORI_PANEL)


def style_empty(cell: Any, *, primary: bool) -> None:
    cell.font = Font(
        name=BODY_FONT,
        size=9,
        italic=primary,
        color=KAORI_MUTED,
    )
    cell.fill = PatternFill('solid', fgColor=KAORI_PANEL)
    cell.border = BODY_BORDER
    cell.alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)


def configure_sheet_page(
    sheet: Worksheet,
    *,
    print_area: str,
    print_title_rows: str,
    orientation: str = 'landscape',
    fit_to_width: int = 1,
) -> None:
    sheet.sheet_view.showGridLines = False
    sheet.print_area = print_area
    sheet.print_title_rows = print_title_rows
    sheet.page_setup.orientation = orientation
    sheet.page_setup.paperSize = sheet.PAPERSIZE_A4
    sheet.page_setup.fitToWidth = max(1, fit_to_width)
    sheet.page_setup.fitToHeight = 0
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
    sheet.page_margins.left = 0.25
    sheet.page_margins.right = 0.25
    sheet.page_margins.top = 0.45
    sheet.page_margins.bottom = 0.45
    sheet.page_margins.header = 0.2
    sheet.page_margins.footer = 0.2


def set_footer(sheet: Worksheet, document_reference: str) -> None:
    sheet.oddFooter.left.text = document_reference
    sheet.oddFooter.left.size = 8
    sheet.oddFooter.left.color = KAORI_MUTED
    sheet.oddFooter.right.text = 'Page &P of &N'
    sheet.oddFooter.right.size = 8
    sheet.oddFooter.right.color = KAORI_MUTED

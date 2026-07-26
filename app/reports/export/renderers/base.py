from __future__ import annotations

from pathlib import Path
from typing import Protocol

from app.models.report import Report


class ReportPdfRenderer(Protocol):
    def __call__(self, report: Report, output_path: Path) -> None: ...

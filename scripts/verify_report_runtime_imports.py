#!/usr/bin/env python3
"""Smoke-test the canonical report renderer import graph.

This check intentionally imports the runtime artifact registry instead of only
parsing source files. It protects package ``__init__`` boundaries from eager
renderer imports that can create partially initialized modules.
"""

from __future__ import annotations

import sys
from importlib import import_module
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

catalog = import_module('app.reports.catalog')
artifacts = import_module('app.reports.export.artifacts')

FORMAT_CSV = catalog.FORMAT_CSV
FORMAT_PDF = catalog.FORMAT_PDF
FORMAT_XLSX = catalog.FORMAT_XLSX
get_report_artifact_format = artifacts.get_report_artifact_format


def main() -> int:
    errors: list[str] = []

    for output_format in (FORMAT_PDF, FORMAT_XLSX, FORMAT_CSV):
        try:
            artifact_format = get_report_artifact_format(output_format)
        except Exception as exc:  # pragma: no cover - failure path is the gate output
            errors.append(f'{output_format}: registry resolution failed: {exc!r}')
            continue

        if artifact_format.value != output_format:
            errors.append(f'{output_format}: registry returned mismatched value {artifact_format.value!r}.')
        if not callable(artifact_format.renderer):
            errors.append(f'{output_format}: renderer is not callable.')

    if errors:
        print('ERROR: canonical report runtime imports failed:', file=sys.stderr)
        for error in errors:
            print(f'  - {error}', file=sys.stderr)
        return 1

    print(
        'KAORI report runtime import audit passed: PDF, XLSX, and CSV renderers load '
        'through the canonical artifact registry without circular imports.'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def require(source: str, token: str, label: str, errors: list[str]) -> None:
    if token not in source:
        errors.append(f'{label}: missing {token!r}')


def forbid(source: str, token: str, label: str, errors: list[str]) -> None:
    if token in source:
        errors.append(f'{label}: forbidden legacy token {token!r}')


def main() -> int:
    errors: list[str] = []
    component = read('app/templates/components/snapshot_context_bar.html')
    inventory_partial = read('app/templates/inventory/components/_data_freshness.html')
    inventory_service = read('app/inventory/overview.py')
    tls_partial = read('app/templates/governance/tls_certificates/partials/_snapshot_context.html')
    contract = read('docs/design/components/SNAPSHOT_CONTEXT_BAR.md')
    pattern = read('docs/design/patterns/KUBERNETES_INVENTORY_OVERVIEW.md')
    quality_gate = read('scripts/quality_gate.sh')

    for token in (
        'border-t border-outline-subtle',
        'xl:divide-x',
        'xl:divide-outline-subtle',
        "coverage_tone='normal'",
        "exceptions_tone='normal'",
        "metric('database-backup', 'Committed Coverage'",
        "metric('scan-search', 'Snapshot Exceptions'",
        'supporting',
    ):
        require(component, token, 'snapshot component', errors)

    for token in (
        'bg-surface-hover',
        "~ '/' ~",
    ):
        forbid(component + inventory_partial, token, 'snapshot component', errors)

    for token in (
        'coverage_label=inventory_freshness.coverage_label',
        'coverage_supporting=inventory_freshness.coverage_supporting',
        'coverage_tone=inventory_freshness.coverage_tone',
        'exceptions_tone=inventory_freshness.exceptions_tone',
    ):
        require(inventory_partial, token, 'inventory snapshot partial', errors)

    for token in (
        "'source_label': 'Committed Inventory Snapshot'",
        "'coverage_label': coverage_label",
        "'coverage_supporting': coverage_supporting",
        "'scope_supporting':",
        "'latest_supporting':",
        "'exceptions_supporting': 'Review required' if has_exceptions else 'No issues detected'",
        "'The selected cluster snapshot is current and fully committed.'",
    ):
        require(inventory_service, token, 'inventory freshness service', errors)

    for token in (
        "coverage_tone=payload.snapshot.coverage_tone",
        "exceptions_tone=payload.snapshot.exceptions_tone",
        "title='TLS Collection Snapshot'",
    ):
        require(tls_partial, token, 'TLS snapshot partial', errors)

    for token in (
        'single neutral summary surface',
        'no metric background tiles',
        'Semantic color appears only',
        'Snapshot Context Bar Standard v1.1',
    ):
        require(contract, token, 'snapshot standard documentation', errors)

    require(pattern, 'subtle dividers instead of nested Violet metric cards', 'inventory pattern', errors)
    require(
        quality_gate,
        'python scripts/verify_snapshot_context_bar_standard.py',
        'quality gate',
        errors,
    )

    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1

    print(
        'KAORI Snapshot Context Bar audit passed: one neutral surface, transparent '
        'metrics, subtle dividers, and controlled semantic indicators match the '
        'Inventory Data Snapshot contract.'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

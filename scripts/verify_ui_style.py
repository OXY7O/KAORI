#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

_METRICS = (
    'arbitrary_text_sizes',
    'arbitrary_tracking',
    'font_extrabold_utilities',
    'arbitrary_radii',
    'raw_hex_colors',
    'raw_palette_utilities',
    'semantic_border_utilities',
    'page_local_compact_status_labels',
    'page_local_compact_pill_labels',
    'custom_hero_titles',
    'custom_previous_next_pagination',
    'copied_standard_surface_shells',
    'copied_right_context_grids',
    'page_local_workspace_tablists',
)

_ARBITRARY_TEXT = re.compile(r'\btext-\[[^\]]+\]')
_ARBITRARY_TRACKING = re.compile(r'\btracking-\[[^\]]+\]')
_FONT_EXTRABOLD = re.compile(r'\bfont-extrabold\b')
_ARBITRARY_RADIUS = re.compile(r'\b(?:rounded-3xl|rounded-\[[^\]]+\])')
_RAW_HEX = re.compile(r'(?<![\w-])#[0-9a-fA-F]{3,8}\b')
_RAW_PALETTE = re.compile(
    r'\b(?:bg|text|border|ring|shadow|fill|stroke)-'
    r'(?:red|green|blue|amber|yellow|gray|slate|zinc|neutral|stone|indigo|'
    r'purple|violet|pink|rose|cyan|teal|emerald|lime|orange|sky)-'
    r'\d{2,3}(?:/\d{1,3})?\b'
)
_SEMANTIC_BORDER = re.compile(
    r'\bborder-status-'
    r'(?:normal|warning|critical|info|unknown|disabled|pending|maintenance)-'
    r'border\b'
)
_TAG_WITH_CLASS = re.compile(r'<[^>]+\bclass="(?P<class>[^"]+)"[^>]*>', re.IGNORECASE)
_H1_TAG = re.compile(r'<h1\b[^>]*>', re.IGNORECASE | re.DOTALL)
_PREVIOUS = re.compile(r'>\s*Previous\s*<', re.IGNORECASE)
_NEXT = re.compile(r'>\s*Next\s*<', re.IGNORECASE)
_TABLIST = re.compile(r'role=[\"\']tablist[\"\']', re.IGNORECASE)
_APPROVED_SEMANTIC_BORDER_COMPONENTS = {
    'app/templates/components/action_button.html',
    'app/templates/components/operational_callout.html',
    'app/templates/components/kubernetes_operation_ui.html',
}
_APPROVED_STANDARD_SURFACE_COMPONENTS = {
    'app/templates/components/table.html',
    'app/templates/components/operational_section_card.html',
    'app/templates/components/snapshot_context_bar.html',
    'app/templates/components/visualization_workspace.html',
    'app/templates/components/details/_detail_content.html',
    'app/templates/components/operation_evidence_boundary.html',
    'app/templates/components/protected_value_panel.html',
    'app/templates/components/activity_status_card.html',
    'app/templates/components/kubernetes_operation_ui.html',
}

_APPROVED_ARBITRARY_TEXT_COMPONENTS = {
    'app/templates/components/forecast_projection_chart.html',
    'app/templates/components/page_hero.html',
    'app/templates/components/table.html',
    'app/templates/components/table_label.html',
}
_APPROVED_CUSTOM_HERO_COMPONENTS = {
    'app/templates/components/page_hero.html',
    'app/templates/reports/pdf/components/analytics_publication.html',
}


def _count_page_local_compact_status_labels(relative: str, source: str) -> int:
    if relative in {
        'app/templates/components/table_label.html',
        'app/templates/components/page_hero.html',
    }:
        return 0
    count = 0
    for match in _TAG_WITH_CLASS.finditer(source):
        classes = match.group('class')
        if 'bg-status-' not in classes or '-soft' not in classes:
            continue
        if 'text-[10px]' in classes or 'text-[11px]' in classes:
            count += 1
    return count


def _count_page_local_compact_pill_labels(relative: str, source: str) -> int:
    if relative in {
        'app/templates/components/table_label.html',
        'app/templates/components/page_hero.html',
        'app/templates/kubernetes/analytics/components/_record_filter_bar.html',
    }:
        return 0
    count = 0
    for match in _TAG_WITH_CLASS.finditer(source):
        classes = match.group('class')
        has_compact_padding = re.search(
            r'\bpx-(?:1|1\.5|2|2\.5|3)\b',
            classes,
        )
        if 'rounded-full' not in classes or not has_compact_padding:
            continue
        if not re.search(r'\b(?:text-xs|text-\[(?:9|10|11)px\])\b', classes):
            continue
        count += 1
    return count


def _count_custom_hero_titles(relative: str, source: str) -> int:
    if relative in _APPROVED_CUSTOM_HERO_COMPONENTS:
        return 0
    return sum(1 for match in _H1_TAG.finditer(source) if 'page_hero.title_classes()' not in match.group(0))


def _count_copied_standard_surface_shells(relative: str, source: str) -> int:
    if relative in _APPROVED_STANDARD_SURFACE_COMPONENTS:
        return 0
    count = 0
    for match in _TAG_WITH_CLASS.finditer(source):
        classes = match.group('class')
        required = (
            'overflow-hidden',
            'rounded-xl',
            'border-outline-default',
            'bg-surface-card',
            'shadow-sm',
        )
        if all(token in classes for token in required):
            count += 1
    return count


def _metrics(relative: str, source: str) -> dict[str, int]:
    custom_pagination = int(
        'components/pagination.html' not in source
        and _PREVIOUS.search(source) is not None
        and _NEXT.search(source) is not None
        and ('pagination' in relative.lower() or 'pagination' in source.lower())
    )
    return {
        'arbitrary_text_sizes': (
            0 if relative in _APPROVED_ARBITRARY_TEXT_COMPONENTS else len(_ARBITRARY_TEXT.findall(source))
        ),
        'arbitrary_tracking': len(_ARBITRARY_TRACKING.findall(source)),
        'font_extrabold_utilities': len(_FONT_EXTRABOLD.findall(source)),
        'arbitrary_radii': len(_ARBITRARY_RADIUS.findall(source)),
        'raw_hex_colors': len(_RAW_HEX.findall(source)),
        'raw_palette_utilities': len(_RAW_PALETTE.findall(source)),
        'semantic_border_utilities': (
            0 if relative in _APPROVED_SEMANTIC_BORDER_COMPONENTS else len(_SEMANTIC_BORDER.findall(source))
        ),
        'page_local_compact_status_labels': _count_page_local_compact_status_labels(relative, source),
        'page_local_compact_pill_labels': _count_page_local_compact_pill_labels(relative, source),
        'custom_hero_titles': _count_custom_hero_titles(relative, source),
        'custom_previous_next_pagination': custom_pagination,
        'copied_standard_surface_shells': _count_copied_standard_surface_shells(relative, source),
        'copied_right_context_grids': (
            0
            if relative == 'app/templates/components/context_rail.html'
            else source.count('xl:grid-cols-[minmax(0,1fr)_20rem]')
        ),
        'page_local_workspace_tablists': (
            0
            if relative.startswith('app/templates/components/') or 'components/workspace_tabs.html' in source
            else len(_TABLIST.findall(source))
        ),
    }


def scan(root: Path) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for path in sorted((root / 'app' / 'templates').rglob('*.html')):
        source = path.read_text(encoding='utf-8')
        relative = path.relative_to(root).as_posix()
        metrics = {metric: value for metric, value in _metrics(relative, source).items() if value}
        if metrics:
            result[relative] = metrics
    return result


def write_baseline(root: Path, baseline_path: Path) -> None:
    payload = {
        'version': 3,
        'description': (
            'Per-template ceiling for style-drift review candidates. Counts are not all defects; '
            'they must not increase and should fall during page-by-page standardization.'
        ),
        'files': scan(root),
    }
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    baseline_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + '\n',
        encoding='utf-8',
    )


def validate(root: Path, baseline_path: Path) -> list[str]:
    payload = json.loads(baseline_path.read_text(encoding='utf-8'))
    baseline = payload.get('files', {})
    current = scan(root)
    errors: list[str] = []

    for path in sorted(set(current) | set(baseline)):
        current_metrics = current.get(path, {metric: 0 for metric in _METRICS})
        baseline_metrics = baseline.get(path, {metric: 0 for metric in _METRICS})
        for metric in _METRICS:
            value = int(current_metrics.get(metric, 0))
            allowed = int(baseline_metrics.get(metric, 0))
            if value > allowed:
                errors.append(f'{path}: {metric} {value} exceeds style ceiling {allowed}')
            elif value < allowed:
                errors.append(
                    f'{path}: {metric} fell from {allowed} to {value}; update the style baseline in the same change'
                )
    return errors


def _totals(files: dict[str, dict[str, int]]) -> dict[str, int]:
    return {metric: sum(int(values.get(metric, 0)) for values in files.values()) for metric in _METRICS}


def main() -> int:
    parser = argparse.ArgumentParser(description='Prevent KAORI page-local styling drift from increasing.')
    parser.add_argument('--root', type=Path, default=Path('.'))
    parser.add_argument(
        '--baseline',
        type=Path,
        default=Path('docs/architecture/ui-style-debt-baseline.json'),
    )
    parser.add_argument('--write-baseline', action='store_true')
    args = parser.parse_args()

    root = args.root.resolve()
    baseline = args.baseline if args.baseline.is_absolute() else root / args.baseline

    try:
        if args.write_baseline:
            write_baseline(root, baseline)
            print(f'Wrote KAORI UI style baseline to {baseline.relative_to(root)}.')
            return 0
        errors = validate(root, baseline)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f'ERROR: {exc}')
        return 1

    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1

    files = scan(root)
    totals = _totals(files)
    summary = ', '.join(f'{metric}={totals[metric]}' for metric in _METRICS)
    print(f'KAORI UI style drift is bounded across {len(files)} templates: {summary}.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

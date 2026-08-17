#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANALYTICS_TEMPLATES = ROOT / 'app' / 'templates' / 'analytics'

_MANUAL_COMPACT_LABEL = re.compile(
    r'<[^>]+class="[^"]*\binline-flex\b[^"]*\bmin-h-6\b[^"]*\brounded-md\b[^"]*"[^>]*>',
    re.IGNORECASE,
)
_ARBITRARY_COMPACT_TEXT = re.compile(r'\btext-\[(?:10|11)px\]\b')
_COUNT_LITERAL_HINT = re.compile(
    r'\b(?:Actionable|Records?|Checks?|Groups?|Owners?|Contacts?|Runbooks?|Signals?|Candidates?|Series|Domains?|Resources?|Items?|Findings?|Recommendations?|Boundaries|Quota Objects|Complete Evidence|Hard Keys|Pods|Available)\b',
    re.IGNORECASE,
)
_COUNT_EXPRESSION_HINT = re.compile(
    r'(?:\|length\b|(?:^|[._])count\b|_count\b|total_items\b|actionable_total\b|finding_count_display\b|recommendation_count_display\b)',
    re.IGNORECASE,
)
_QUOTED_LITERAL = re.compile(r"(['\"])(?P<value>.*?)(?<!\\)\1")


def _extract_calls(source: str, function_name: str) -> list[tuple[int, str]]:
    marker = function_name + '('
    calls: list[tuple[int, str]] = []
    start = 0
    while True:
        idx = source.find(marker, start)
        if idx < 0:
            return calls
        arg_start = idx + len(marker)
        depth = 1
        quote: str | None = None
        escaped = False
        pos = arg_start
        while pos < len(source) and depth:
            char = source[pos]
            if quote:
                if escaped:
                    escaped = False
                elif char == '\\':
                    escaped = True
                elif char == quote:
                    quote = None
            else:
                if char in ("'", '"'):
                    quote = char
                elif char == '(':
                    depth += 1
                elif char == ')':
                    depth -= 1
            pos += 1
        if depth:
            raise ValueError(f'Unclosed call for {function_name}')
        line = source.count('\n', 0, idx) + 1
        calls.append((line, source[arg_start : pos - 1]))
        start = pos


def _split_top_level_args(arguments: str) -> list[str]:
    args: list[str] = []
    depth = 0
    quote: str | None = None
    escaped = False
    start = 0
    for idx, char in enumerate(arguments):
        if quote:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in ("'", '"'):
            quote = char
            continue
        if char in '([{':
            depth += 1
            continue
        if char in ')]}':
            depth -= 1
            continue
        if char == ',' and depth == 0:
            args.append(arguments[start:idx].strip())
            start = idx + 1
    tail = arguments[start:].strip()
    if tail:
        args.append(tail)
    return args


def _positional_args(args: list[str]) -> list[str]:
    return [arg for arg in args if '=' not in arg.split('|', 1)[0]]


def _has_named_icon(args: list[str]) -> bool:
    for arg in args:
        if not arg.lstrip().startswith('icon='):
            continue
        value = arg.split('=', 1)[1].strip().lower()
        if value not in {'none', "''", '""'}:
            return True
    return False


def _validate_status_labels(relative: str, source: str, errors: list[str]) -> None:
    for line, arguments in _extract_calls(source, 'table_label.status_label'):
        args = _split_top_level_args(arguments)
        positional = _positional_args(args)
        if len(positional) >= 3 and positional[2].strip().lower() not in {'none', "''", '""'}:
            errors.append(
                f'{relative}:{line}: Analytics status_label must not pass a Lucide icon; '
                'use text-first status_label or status_indicator_label for repeated states.'
            )
        if _has_named_icon(args):
            errors.append(
                f'{relative}:{line}: Analytics status_label must not use icon=; '
                'ordinary operational status is iconless.'
            )


def _validate_metadata_counts(relative: str, source: str, errors: list[str]) -> None:
    for line, arguments in _extract_calls(source, 'table_label.metadata_label'):
        args = _split_top_level_args(arguments)
        if not args:
            continue
        first_arg = args[0]
        literal_count = any(
            _COUNT_LITERAL_HINT.search(match.group('value')) for match in _QUOTED_LITERAL.finditer(first_arg)
        )
        expression_count = _COUNT_EXPRESSION_HINT.search(first_arg) is not None
        if not literal_count and not expression_count:
            continue
        positional = _positional_args(args)
        icon_value = positional[1].strip() if len(positional) >= 2 else ''
        has_icon = icon_value.lower() not in {'', 'none', "''", '""'} or _has_named_icon(args)
        if has_icon:
            errors.append(
                f'{relative}:{line}: count/category metadata must stay iconless unless the icon '
                'adds independent source/scope meaning.'
            )


def _require_dense_status_dots(errors: list[str]) -> None:
    checks = {
        'app/templates/kubernetes/analytics/alerts/partials/_alerts_table_row.html': (
            'status_indicator_label(alert.status|title',
        ),
        'app/templates/kubernetes/analytics/workload/partials/_workload_mapping_section.html': (
            'status_indicator_label(row.configuration_status.label',
            'status_indicator_label(row.metrics_coverage.label',
        ),
        'app/templates/kubernetes/analytics/workload/partials/_tenant_quota_section.html': (
            'status_indicator_label(row.quota_status.label',
        ),
        'app/templates/kubernetes/analytics/storage/partials/_persistent_volume_claims_panel.html': (
            'status_indicator_label(row.status',
        ),
        'app/templates/kubernetes/analytics/storage/partials/_persistent_volumes_panel.html': (
            'status_indicator_label(row.status',
        ),
    }
    for relative, required_tokens in checks.items():
        source = (ROOT / relative).read_text(encoding='utf-8')
        for token in required_tokens:
            if token not in source:
                errors.append(
                    f'{relative}: repeated operational state must use semantic-dot '
                    f'status_indicator_label; missing {token!r}.'
                )


def main() -> int:
    errors: list[str] = []

    for path in sorted(ANALYTICS_TEMPLATES.rglob('*.html')):
        source = path.read_text(encoding='utf-8')
        relative = path.relative_to(ROOT).as_posix()

        _validate_status_labels(relative, source, errors)
        _validate_metadata_counts(relative, source, errors)

        for match in _MANUAL_COMPACT_LABEL.finditer(source):
            line = source.count('\n', 0, match.start()) + 1
            errors.append(
                f'{relative}:{line}: page-local compact label markup is forbidden; use components/table_label.html.'
            )

        for match in _ARBITRARY_COMPACT_TEXT.finditer(source):
            line = source.count('\n', 0, match.start()) + 1
            errors.append(f'{relative}:{line}: arbitrary compact label text size is forbidden in Analytics templates.')

    _require_dense_status_dots(errors)

    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1

    print(
        'KAORI Kubernetes Analytics compact-label audit passed: operational status labels are '
        'iconless, dense repeated states use semantic dots, count metadata is iconless, and '
        'page-local compact label markup is absent.'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

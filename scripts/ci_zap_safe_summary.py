"""Safe aggregate of the existing ZAP traditional JSON baseline.

Only fixed labels, validated numeric counts and the trusted source SHA leave
this process. Never publish ZAP's URLs, headers, bodies, payloads or messages.
This is an Actions evidence formatter, not a SARIF generator or security gate.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

MAX_REPORT_BYTES = 32 * 1024 * 1024
RISK_NAMES = (
    (3, 'High'),
    (2, 'Medium'),
    (1, 'Low'),
    (0, 'Informational'),
)
MAX_ALERT_FAMILIES = 100_000
MAX_SITE_ENTRIES = 100_000


def _unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise UnverifiedZapReport('Ambiguous JSON object')
        result[key] = value
    return result


def _reject_constant(_value: str) -> None:
    raise UnverifiedZapReport('Non-finite JSON number')


def _finite_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise UnverifiedZapReport('Non-finite JSON number')
    return parsed


SHA_PATTERN = re.compile(r'[0-9a-fA-F]{40}\Z')


class UnverifiedZapReport(ValueError):
    """The report schema cannot safely support the aggregate claim."""


def _risk_code(value: object) -> int:
    if type(value) is int and 0 <= value <= 3:
        return value
    if type(value) is str and value in ('0', '1', '2', '3'):
        return int(value)
    raise UnverifiedZapReport('Invalid risk category')


def _count_risks(payload: Any) -> tuple[int, Counter[int]]:
    if not isinstance(payload, dict):
        raise UnverifiedZapReport('Invalid report structure')
    sites = payload.get('site')
    if not isinstance(sites, list) or not sites:
        raise UnverifiedZapReport('Missing scanned sites')
    if len(sites) > MAX_SITE_ENTRIES:
        raise UnverifiedZapReport('Excessive scanned sites')

    totals: Counter[int] = Counter()
    families = 0
    for site in sites:
        if not isinstance(site, dict):
            raise UnverifiedZapReport('Invalid site structure')
        alerts = site.get('alerts')
        if not isinstance(alerts, list):
            raise UnverifiedZapReport('Missing alert list')
        # Reject oversized batches before walking individual alert objects.
        # The limit is cumulative across sites, not per-site.
        if len(alerts) > MAX_ALERT_FAMILIES - families:
            raise UnverifiedZapReport('Excessive alert records')
        for alert in alerts:
            if not isinstance(alert, dict):
                raise UnverifiedZapReport('Invalid alert structure')
            families += 1
            if families > MAX_ALERT_FAMILIES:
                raise UnverifiedZapReport('Excessive alert records')
            totals[_risk_code(alert.get('riskcode'))] += 1

    return len(sites), totals


def render_summary(payload: Any, source_sha: str) -> str:
    """Render ONLY allowlisted, non-sensitive numerical evidence."""
    if not SHA_PATTERN.fullmatch(source_sha):
        raise UnverifiedZapReport('Invalid source identity')
    site_count, totals = _count_risks(payload)

    lines = [
        '### OWASP ZAP — sanitized Runtime & DAST evidence',
        '',
        f'Committed source SHA: `{source_sha.lower()}`',
        '',
        'These counts describe grouped alert records in a traditional ZAP JSON report.',
        'They are **not** ZAP CLI FAIL/WARN/PASS counts, a Code scanning',
        'SARIF analysis, or proof of complete application security.',
        '',
        '| Risk class | Grouped alert records |',
        '| --- | ---: |',
    ]
    for code, label in RISK_NAMES:
        lines.append(f'| {label} | {totals[code]} |')
    lines.extend(
        [
            f'| **Total** | **{sum(totals.values())}** |',
            '',
            f'Scanned site entries: **{site_count}**.',
            'Actual gate result and ZAP CLI warning/failure classifications remain',
            'authoritative in this same Full Admission run. ZAP warnings may be',
            'non-blocking under the existing `-I` policy.',
            'Raw HTTP targets, paths, queries, headers, cookies, bodies, payloads',
            'and instance details are intentionally excluded.',
            '',
        ]
    )
    return '\n'.join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Render only allowlisted ZAP aggregates')
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--source-sha', required=True)
    args = parser.parse_args(argv)

    try:
        # Refuse aliasing the raw report: unlinking output would destroy input.
        # A symlink output could otherwise redirect publication to another file.
        if (
            args.output.is_symlink()
            or (args.output.exists() and args.input.exists() and args.output.samefile(args.input))
            or args.output.resolve() == args.input.resolve()
        ):
            raise UnverifiedZapReport('Unsafe evidence output location')
        # A reused workspace must never retain a prior run's verified-looking output.
        # Failure to clear it is a publication failure, not a valid new summary.
        args.output.unlink(missing_ok=True)
        with args.input.open('rb') as stream:
            raw = stream.read(MAX_REPORT_BYTES + 1)
        if len(raw) > MAX_REPORT_BYTES:
            raise UnverifiedZapReport('Report exceeds bounded input size')
        payload = json.loads(
            raw.decode('utf-8'),
            object_pairs_hook=_unique_keys,
            parse_constant=_reject_constant,
            parse_float=_finite_float,
        )
        summary = render_summary(payload, args.source_sha)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        try:
            args.output.write_text(summary, encoding='utf-8')
        except OSError:
            # A failed write may have created a truncated, apparently valid artifact.
            # Best-effort removal ensures a failed publication cannot be reused.
            args.output.unlink(missing_ok=True)
            raise
    except (OSError, ValueError, UnicodeError, RecursionError):
        # Don't echo source exceptions: paths and parser context may be sensitive.
        print('ZAP sanitized summary NOT VERIFIED; no raw fields emitted.', file=sys.stderr)
        return 2

    print('ZAP sanitized summary available; raw fields omitted.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

"""Safe aggregate of the existing ZAP traditional JSON baseline.

Only fixed labels, validated numeric counts and the trusted source SHA leave
this process. Never publish ZAP's URLs, headers, bodies, payloads or messages.
This is an Actions evidence formatter, not a SARIF generator or security gate.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import stat
import sys
import tempfile
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
MAX_OBJECT_MEMBERS = 10_000
MAX_JSON_OBJECTS = 100_000
MAX_ALERT_INSTANCES = 1_000_000


def _unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    # A bounded raw report can still contain a huge object with tiny keys.
    # Cap members before building the dictionary to avoid memory amplification.
    if len(pairs) > MAX_OBJECT_MEMBERS:
        raise UnverifiedZapReport('Excessive JSON object members')
    for key, value in pairs:
        if key in result:
            raise UnverifiedZapReport('Ambiguous JSON object')
        result[key] = value
    return result


def _reject_constant(_value: str) -> None:
    raise UnverifiedZapReport('Non-finite JSON number')


def _bounded_int(value: str) -> int:
    # A JSON number outside this bound cannot represent an approved aggregate.
    # Reject it before allocating a very large Python integer.
    if len(value.lstrip('-')) > 20:
        raise UnverifiedZapReport('Excessive JSON integer')
    return int(value)


def _finite_float(value: str) -> float:
    # Even ignored JSON fields must not force unbounded numeric conversion.
    # Ordinary ZAP counts are integers; keep a generous finite-float limit.
    if len(value) > 128:
        raise UnverifiedZapReport('Excessive JSON floating-point literal')
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


def _count_risks(payload: Any) -> tuple[int, Counter[int], int | None]:
    if not isinstance(payload, dict):
        raise UnverifiedZapReport('Invalid report structure')
    sites = payload.get('site')
    if not isinstance(sites, list) or not sites:
        raise UnverifiedZapReport('Missing scanned sites')
    if len(sites) > MAX_SITE_ENTRIES:
        raise UnverifiedZapReport('Excessive scanned sites')

    totals: Counter[int] = Counter()
    families = 0
    instances = 0
    complete_instance_counts = True
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
            # Instance details remain private, but bound their cumulative count.
            # ZAP may omit instances for an alert family.
            if 'instances' not in alert:
                complete_instance_counts = False
            alert_instances = alert.get('instances', [])
            if not isinstance(alert_instances, list):
                raise UnverifiedZapReport('Invalid alert instances')
            if len(alert_instances) > MAX_ALERT_INSTANCES - instances:
                raise UnverifiedZapReport('Excessive alert instances')
            # A non-object instance is not a compatible traditional ZAP record.
            # Inspect only types; never serialize private instance fields.
            if any(not isinstance(instance, dict) for instance in alert_instances):
                raise UnverifiedZapReport('Invalid alert instance structure')
            instances += len(alert_instances)
            totals[_risk_code(alert.get('riskcode'))] += 1

    return len(sites), totals, instances if complete_instance_counts else None


def render_summary(payload: Any, source_sha: str) -> str:
    """Render ONLY allowlisted, non-sensitive numerical evidence."""
    if not SHA_PATTERN.fullmatch(source_sha):
        raise UnverifiedZapReport('Invalid source identity')
    site_count, totals, instance_count = _count_risks(payload)

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
            (
                f'Alert instance entries: **{instance_count}**.'
                if instance_count is not None
                else 'Alert instance entries: **NOT VERIFIED** (missing instance arrays).'
            ),
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
        # Refuse publication through a symlinked parent directory. Otherwise
        # an attacker-controlled workspace alias can redirect sanitized evidence
        # outside the intended output tree even when the filename is regular.
        if args.output.parent.resolve() != args.output.parent.absolute():
            raise UnverifiedZapReport('Unsafe evidence output directory')
        # Bind publication to the same existing directory inode observed before
        # reading the untrusted report. A same-path directory replacement can
        # otherwise redirect evidence without introducing a symlink.
        original_output_parent = (
            args.output.parent.stat() if args.output.parent.is_dir() else None
        )
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
        # Reject untrusted source identity before opening or parsing raw DAST data.
        # The stale output has already been cleared to avoid false prior evidence.
        if not SHA_PATTERN.fullmatch(args.source_sha):
            raise UnverifiedZapReport('Invalid source identity')
        # Open without following symlinks or blocking on a FIFO swapped in
        # after the initial path check. Validate the opened descriptor, not
        # only the pathname (which may change between stat and open).
        # Do not silently follow a swapped symlink on platforms without
        # descriptor-level no-follow support. A pathname precheck alone races.
        nofollow = getattr(os, 'O_NOFOLLOW', None)
        if nofollow is None:
            raise UnverifiedZapReport('No safe no-follow input open available')
        # Nonblocking open is mandatory: a swapped FIFO must never hang CI.
        nonblock = getattr(os, 'O_NONBLOCK', None)
        if nonblock is None:
            raise UnverifiedZapReport('No safe nonblocking input open available')
        flags = os.O_RDONLY | nonblock | nofollow
        descriptor = os.open(args.input, flags)
        try:
            stream = os.fdopen(descriptor, 'rb')
        except BaseException:
            # fdopen may fail before taking ownership of the raw descriptor.
            os.close(descriptor)
            raise
        with stream:
            opened_stat = os.fstat(stream.fileno())
            if not stat.S_ISREG(opened_stat.st_mode):
                raise UnverifiedZapReport('Non-regular ZAP report input')
            # Reject known oversized regular files without reading their contents.
            # The bounded read below remains authoritative if the file grows
            # after fstat or a filesystem reports a stale size.
            if opened_stat.st_size > MAX_REPORT_BYTES:
                raise UnverifiedZapReport('Report exceeds bounded input size')
            raw = stream.read(MAX_REPORT_BYTES + 1)
            # A concurrent writer must not turn a partial/mixed scan into
            # apparently verified evidence. Compare metadata on this descriptor.
            final_stat = os.fstat(stream.fileno())
            if (
                opened_stat.st_dev != final_stat.st_dev
                or opened_stat.st_ino != final_stat.st_ino
                or opened_stat.st_mode != final_stat.st_mode
                or opened_stat.st_size != final_stat.st_size
                or opened_stat.st_mtime_ns != final_stat.st_mtime_ns
                or opened_stat.st_ctime_ns != final_stat.st_ctime_ns
            ):
                raise UnverifiedZapReport('ZAP report changed during read')
        if len(raw) > MAX_REPORT_BYTES:
            raise UnverifiedZapReport('Report exceeds bounded input size')
        # A short read with unchanged descriptor metadata is not a complete
        # scan report. Do not publish a valid-looking JSON prefix as evidence.
        if len(raw) != opened_stat.st_size:
            raise UnverifiedZapReport('Incomplete ZAP report read')
        # Keep the object budget invocation-local: concurrent summary renders
        # must not share or reset one another's parser counters.
        objects_seen = 0

        def bounded_unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            nonlocal objects_seen
            objects_seen += 1
            if objects_seen > MAX_JSON_OBJECTS:
                raise UnverifiedZapReport('Excessive JSON object count')
            return _unique_keys(pairs)

        payload = json.loads(
            raw.decode('utf-8'),
            object_pairs_hook=bounded_unique_keys,
            parse_constant=_reject_constant,
            parse_float=_finite_float,
            parse_int=_bounded_int,
        )
        summary = render_summary(payload, args.source_sha)
        # The descriptor can remain stable even when its pathname is replaced
        # after open. Reject a different on-disk report before publication.
        current_input = args.input.stat(follow_symlinks=False)
        if (
            not stat.S_ISREG(current_input.st_mode)
            or any(
                getattr(current_input, field) != getattr(final_stat, field)
                for field in ('st_dev', 'st_ino', 'st_mode', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
            )
        ):
            raise UnverifiedZapReport('ZAP report path changed during parse')
        args.output.parent.mkdir(parents=True, exist_ok=True)
        # Revalidate the output directory after reading untrusted input. A
        # workspace actor may have replaced an initially safe directory with
        # a symlink while parsing; do not publish through that changed alias.
        if args.output.parent.resolve() != args.output.parent.absolute():
            raise UnverifiedZapReport('Unsafe evidence output directory')
        current_output_parent = args.output.parent.stat()
        if original_output_parent is not None:
            if (
                current_output_parent.st_dev != original_output_parent.st_dev
                or current_output_parent.st_ino != original_output_parent.st_ino
            ):
                raise UnverifiedZapReport('Evidence output directory changed during parse')
        # Publish atomically: a symlink introduced after the initial alias check
        # must never redirect writes to the raw report or another sensitive file.
        # A failed write also must not expose a partial, verified-looking summary.
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode='w',
                encoding='utf-8',
                dir=args.output.parent,
                prefix='.zap-summary-',
                suffix='.tmp',
                delete=False,
            ) as stream:
                temporary = Path(stream.name)
                stream.write(summary)
            # A workspace actor can replace the input or output directory while
            # the temporary summary is being written. Recheck both identities
            # immediately before the atomic publication boundary.
            publish_input = args.input.stat(follow_symlinks=False)
            if not stat.S_ISREG(publish_input.st_mode) or any(
                getattr(publish_input, field) != getattr(final_stat, field)
                for field in ('st_dev', 'st_ino', 'st_mode', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
            ):
                raise UnverifiedZapReport('ZAP report changed before publication')
            publish_parent = args.output.parent.stat()
            if (
                args.output.parent.resolve() != args.output.parent.absolute()
                or publish_parent.st_dev != current_output_parent.st_dev
                or publish_parent.st_ino != current_output_parent.st_ino
            ):
                raise UnverifiedZapReport('Evidence output directory changed before publication')
            os.replace(temporary, args.output)
            temporary = None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    except (OSError, ValueError, UnicodeError, RecursionError):
        # Don't echo source exceptions: paths and parser context may be sensitive.
        print('ZAP sanitized summary NOT VERIFIED; no raw fields emitted.', file=sys.stderr)
        return 2

    print('ZAP sanitized summary available; raw fields omitted.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

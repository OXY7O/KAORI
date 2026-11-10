#!/usr/bin/env python3
"""Strict metadata-only ZAP baseline summary (#4400).

Never emit untrusted report strings; scan pass/fail remains with the DAST gate.
"""

import argparse
import json
from pathlib import Path

RISK_CODES = ("0", "1", "2", "3", "4")
MAX_REPORT_BYTES = 32 * 1024 * 1024


def summarize(report):
    """Return allowlisted counts, or None for incompatible evidence."""
    if not isinstance(report, dict) or not isinstance(report.get("site"), list):
        return None
    sites = report["site"]
    if not sites:
        return None
    families = {code: 0 for code in RISK_CODES}
    instances = {code: 0 for code in RISK_CODES}
    for site in sites:
        if not isinstance(site, dict) or not isinstance(site.get("alerts"), list):
            return None
        for alert in site["alerts"]:
            if not isinstance(alert, dict):
                return None
            code = alert.get("riskcode")
            if type(code) is int:
                code = str(code)
            if code not in RISK_CODES:
                return None
            entries = alert.get("instances")
            if not isinstance(entries, list) or any(not isinstance(entry, dict) for entry in entries):
                return None
            families[code] += 1
            instances[code] += len(entries)
    return {"sites": len(sites), "families": families, "instances": instances}


def render(summary, source_sha):
    """Interpolate only fixed labels, validated SHA and integer counters."""
    valid_sha = (
        isinstance(source_sha, str)
        and len(source_sha) == 40
        and all(c in "0123456789abcdef" for c in source_sha)
    )
    if summary is None or not valid_sha:
        return "### ZAP baseline — NOT VERIFIED\n\nSanitized evidence unavailable or incompatible.\n"
    lines = [
        "### ZAP baseline — numeric findings only",
        "",
        f"Source SHA: `{source_sha}`",
        "Evidence: Full Admission Runtime & DAST (counts only; scan outcome governed separately)",
        f'Sites scanned: {summary["sites"]}',
        "",
        "| Risk code | Alert families | Instances |",
        "| --- | ---: | ---: |",
    ]
    for code in RISK_CODES:
        lines.append(f'| {code} | {summary["families"][code]} | {summary["instances"][code]} |')
    return "\n".join(lines) + "\n"


def _reject_duplicate_keys(pairs):
    """Reject ambiguous JSON keys rather than silently trusting the last value."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Ambiguous ZAP JSON object")
        result[key] = value
    return result


def _reject_nonfinite_number(_value):
    """NaN and Infinity are not valid JSON evidence."""
    raise ValueError("Non-finite ZAP JSON number")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--source-sha", required=True)
    args = parser.parse_args()
    try:
        # Bound untrusted scan artifacts before parsing; do not echo file contents.
        if args.report.stat().st_size > MAX_REPORT_BYTES:
            raise ValueError("ZAP report exceeds bounded input size")
        summary = summarize(json.loads(\n            args.report.read_text(encoding="utf-8"),\n            object_pairs_hook=_reject_duplicate_keys,\n            parse_constant=_reject_nonfinite_number,\n        ))
    except (OSError, UnicodeError, ValueError):
        summary = None
    print(render(summary, args.source_sha), end="")


if __name__ == "__main__":
    main()

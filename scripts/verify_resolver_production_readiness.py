#!/usr/bin/env python3
"""Validate a JSON evidence file against KAORI Domain 20 readiness gates."""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TextIO

from app.resolver.production_readiness import ProductionReadinessError, assess_readiness


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='Validate KAORI resolver production-readiness evidence.',
    )
    parser.add_argument('evidence', type=Path, help='Path to a JSON object containing readiness checks.')
    parser.add_argument(
        '--rollout-stage',
        default='disabled',
        choices=('disabled', 'shadow', 'non_production', 'canary', 'production'),
        help='Rollout stage included in the assessment output.',
    )
    return parser


def load_evidence(path: Path) -> Mapping[str, object]:
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError as exc:
        raise ValueError(f'Evidence file does not exist: {path}.') from exc
    except OSError as exc:
        raise ValueError(f'Evidence file cannot be read: {path}: {exc}.') from exc
    except json.JSONDecodeError as exc:
        raise ValueError(
            f'Evidence file contains invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}.'
        ) from exc
    if not isinstance(payload, dict):
        raise ValueError('Evidence JSON root must be an object keyed by readiness check name.')
    return payload


def run(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> int:
    args = build_parser().parse_args(argv)
    try:
        results = load_evidence(args.evidence)
        assessment = assess_readiness(results=results, rollout_stage=args.rollout_stage)
    except (ValueError, ProductionReadinessError) as exc:
        print(json.dumps({'error': str(exc)}, indent=2), file=stderr)
        return 2

    print(
        json.dumps(
            {
                'ready': assessment.ready,
                'rollout_stage': assessment.rollout_stage,
                'failed_checks': list(assessment.failed_checks),
                'evidence_hash': assessment.evidence_hash,
            },
            indent=2,
            sort_keys=True,
        ),
        file=stdout,
    )
    return 0 if assessment.ready else 1


def main() -> int:
    return run()


if __name__ == '__main__':
    raise SystemExit(main())

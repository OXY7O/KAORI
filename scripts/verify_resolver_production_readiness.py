#!/usr/bin/env python3
"""Validate a JSON evidence file against KAORI Domain 20 readiness gates."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.resolver.production_readiness import assess_readiness


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('evidence', type=Path)
    args = parser.parse_args()
    results = json.loads(args.evidence.read_text(encoding='utf-8'))
    assessment = assess_readiness(results=results)
    print(json.dumps({
        'ready': assessment.ready,
        'failed_checks': assessment.failed_checks,
        'evidence_hash': assessment.evidence_hash,
    }, indent=2))
    return 0 if assessment.ready else 1


if __name__ == '__main__':
    raise SystemExit(main())

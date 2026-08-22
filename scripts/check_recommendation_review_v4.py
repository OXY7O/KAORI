from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / 'app/templates/intelligence/partials/_recommendation_detail_content.html'


def _run(*args: str) -> None:
    print(f"+ {' '.join(args)}", flush=True)
    subprocess.run(args, cwd=ROOT, check=True)


def _static_contract() -> None:
    source = TEMPLATE.read_text(encoding='utf-8')
    required = (
        'data-kaori-recommendation-review-layout="decision-evidence-workflow"',
        'Recommendation Review',
        'Committed Snapshot',
        'WHY KAORI RAISED THIS',
        'RECOMMENDED OUTCOME',
        'EVIDENCE & AFFECTED ASSETS',
        'REMEDIATION WORKFLOW',
        'TRACEABILITY',
        'Verification Gate',
        'Validate Live State',
        'Rule Key',
        '2xl:grid-cols-12',
        'block break-words [overflow-wrap:anywhere]',
    )
    missing = [token for token in required if token not in source]
    if missing:
        raise SystemExit(f"FAIL — Recommendation Review v4 missing: {', '.join(missing)}")
    forbidden = ('block truncate', 'line-clamp-', 'text-[10px]', 'text-[11px]')
    present = [token for token in forbidden if token in source]
    if present:
        raise SystemExit(f"FAIL — Recommendation Review v4 forbidden UI token(s): {', '.join(present)}")
    print('PASS — Recommendation Review v4 static contract')


def main() -> int:
    parser = argparse.ArgumentParser(description='Verify the KAORI Recommendation Review v4 redesign.')
    parser.add_argument(
        '--skip-formatters',
        action='store_true',
        help='Skip Ruff/djLint checks when those tools are unavailable in the current environment.',
    )
    args = parser.parse_args()

    _static_contract()

    if not args.skip_formatters:
        _run(sys.executable, '-m', 'ruff', 'format', '--check', '.')
        _run(sys.executable, '-m', 'ruff', 'check', '.')
        _run(
            sys.executable,
            '-m',
            'djlint',
            'app/templates/intelligence/partials/_recommendation_detail_content.html',
            '--check',
        )

    _run(sys.executable, '-m', 'pytest', '-q', 'tests/contracts/intelligence')
    _run(sys.executable, 'scripts/verify_intelligence_baseline_lock.py')
    _run(sys.executable, 'scripts/verify_core_workspace_ui_lock.py')
    _run(sys.executable, 'scripts/verify_ui_style.py')
    _run(sys.executable, 'scripts/verify_template_dependencies.py')
    _run(sys.executable, 'scripts/verify_code_health_baseline_integrity.py')
    _run(sys.executable, 'scripts/verify_code_health.py')

    print('PASS — KAORI Recommendation Review v4 verification complete')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

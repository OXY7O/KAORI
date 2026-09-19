#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

ARTIFACT_DIR="$ROOT/tmp/ci-artifacts/security"
mkdir -p "$ARTIFACT_DIR"

printf '[KAORI CI] workflow lint\n'
actionlint .github/workflows/*.yml

printf '[KAORI CI] workflow security lint\n'
zizmor --persona=regular --min-severity=medium .github/workflows

printf '[KAORI CI] shell lint\n'
shellcheck .github/ci/*.sh scripts/*.sh

printf '[KAORI CI] Dockerfile lint\n'
hadolint --failure-threshold error Dockerfile .github/ci/Dockerfile

printf '[KAORI CI] secret scan\n'
gitleaks git \
  --no-banner \
  --redact \
  --report-format json \
  --report-path "$ARTIFACT_DIR/gitleaks.json" \
  .

printf '[KAORI CI] Python SAST\n'
set +e
bandit -r app scripts -q -ll -f json -o "$ARTIFACT_DIR/bandit.json"
bandit_status=$?
set -e

python - "$ARTIFACT_DIR/bandit.json" "$bandit_status" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

report_path = Path(sys.argv[1])
status = int(sys.argv[2])

if not report_path.exists():
    print("FAIL — KAORI Python SAST")
    print()
    print("Bandit Report")
    print()
    print("  FAIL — Bandit did not produce its JSON diagnostic artifact.")
    print()
    print("Summary")
    print()
    print(f"  Bandit exited with status {status}")
    raise SystemExit(status or 1)

payload = json.loads(report_path.read_text(encoding="utf-8"))
findings = payload.get("results", [])

if status == 0:
    print("PASS — KAORI Python SAST")
    print()
    print("Bandit")
    print()
    print("  PASS — No medium-or-higher Python SAST findings detected.")
    print()
    print("Summary")
    print()
    print("  1 check passed · 0 failed")
    raise SystemExit(0)

print("FAIL — KAORI Python SAST")
print()
print("Findings")
print()
for finding in findings:
    filename = finding.get("filename", "<unknown>")
    line = finding.get("line_number", "?")
    test_id = finding.get("test_id", "B???")
    severity = finding.get("issue_severity", "UNKNOWN")
    confidence = finding.get("issue_confidence", "UNKNOWN")
    issue = " ".join(str(finding.get("issue_text", "Bandit finding")).split())
    print(f"  FAIL — {test_id} · {severity}/{confidence} · {filename}:{line}")
    print(f"         {issue}")

print()
print("Summary")
print()
print(f"  {len(findings)} findings · Bandit exit status {status}")
raise SystemExit(status)
PY

printf '[KAORI CI] Semgrep community SAST\n'
semgrep scan \
  --config .github/ci/semgrep.yml \
  --error \
  --metrics=off \
  --exclude node_modules \
  --exclude app/static/vendor \
  --json \
  --json-output "$ARTIFACT_DIR/semgrep.json" \
  app scripts frontend

printf '[KAORI CI] Python dependency audit\n'
pip-audit -r requirements/base.txt --format=json --output="$ARTIFACT_DIR/pip-audit-base.json"
pip-audit -r requirements/dev.txt --format=json --output="$ARTIFACT_DIR/pip-audit-dev.json"

printf '[KAORI CI] Node dependency audit\n'
npm audit --audit-level=high --json > "$ARTIFACT_DIR/npm-audit.json"

printf 'PASS — KAORI Free-Plan Static Security\n'

#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Retained as the stable developer/CI entrypoint used by older operational
# instructions. The implementation is canonical in quality_gate.sh.
exec bash scripts/quality_gate.sh --static

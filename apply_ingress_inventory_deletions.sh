#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-.}"
rm -f "$ROOT/app/templates/inventory/ingresses/partials/_inventory_scope.html"
echo "KAORI Ingress obsolete wrapper removed."

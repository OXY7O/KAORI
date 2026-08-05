#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="${1:-.}"
while IFS= read -r path; do
  [[ -n "$path" ]] || continue
  rm -f -- "$ROOT_DIR/$path"
done < "$(dirname "$0")/KAORI_CORE_WORKSPACE_DELETED_FILES.txt"

#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
KAORI_STATE_DIR="${KAORI_STATE_DIR:-/var/lib/kaori/deploy-state}"
previous_image_file="$KAORI_STATE_DIR/previous-image"
previous_source_file="$KAORI_STATE_DIR/previous-source-sha"

fail() {
  printf 'KAORI VPS rollback failed: %s\n' "$*" >&2
  exit 1
}

[[ -r "$previous_image_file" ]] || fail "previous image record is missing: $previous_image_file"
[[ -r "$previous_source_file" ]] || fail "previous source record is missing: $previous_source_file"

previous_image="$(tr -d '\r\n' < "$previous_image_file")"
previous_source_sha="$(tr -d '\r\n' < "$previous_source_file")"
[[ "$previous_image" =~ @sha256:[0-9a-f]{64}$ ]] || fail 'recorded previous image is not an immutable @sha256: reference'
[[ "$previous_source_sha" =~ ^[0-9a-f]{40}$ ]] || fail 'recorded previous source SHA is invalid'

printf '%s\n' 'WARNING: image rollback does not reverse database schema changes.' >&2
printf '%s\n' 'If the failed rollout introduced an incompatible migration, restore the reviewed pre-migration backup separately.' >&2

exec bash "$SCRIPT_DIR/deploy.sh" "$previous_image" "$previous_source_sha"

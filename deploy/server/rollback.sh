#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
KAORI_STATE_DIR="${KAORI_STATE_DIR:-/var/lib/kaori/deploy-state}"
previous_image_file="$KAORI_STATE_DIR/previous-image"
previous_source_file="$KAORI_STATE_DIR/previous-source-sha"
previous_version_file="$KAORI_STATE_DIR/previous-version"
previous_backup_file="$KAORI_STATE_DIR/previous-backup"

fail() {
  printf 'KAORI server rollback failed: %s\n' "$*" >&2
  exit 1
}

[[ $# -eq 1 && "$1" == '--restore-backup' ]] || \
  fail 'refusing image-only rollback; usage: rollback.sh --restore-backup'
[[ -r "$previous_image_file" ]] || fail "previous image record is missing: $previous_image_file"
[[ -r "$previous_source_file" ]] || fail "previous source record is missing: $previous_source_file"
[[ -r "$previous_version_file" ]] || fail "previous version record is missing: $previous_version_file"
[[ -r "$previous_backup_file" ]] || fail "previous backup record is missing: $previous_backup_file"

previous_image_ref="$(tr -d '\r\n' < "$previous_image_file")"
previous_source_sha="$(tr -d '\r\n' < "$previous_source_file")"
previous_version="$(tr -d '\r\n' < "$previous_version_file")"
backup_file="$(tr -d '\r\n' < "$previous_backup_file")"
[[ "$previous_image_ref" =~ @sha256:[0-9a-f]{64}$ ]] || fail 'recorded previous image is not immutable'
[[ "$previous_source_sha" =~ ^[0-9a-f]{40}$ ]] || fail 'recorded previous source SHA is invalid'
[[ "$previous_version" =~ ^v[0-9]+\.[0-9]+\.[0-9]+(-rc\.[0-9]+)?$ ]] || fail 'recorded previous release version is invalid'
[[ -n "$backup_file" && -f "$backup_file" ]] || fail 'recorded rollback backup does not exist'

printf '%s\n' 'Restoring reviewed pre-migration database backup before image rollback.' >&2
bash "$SCRIPT_DIR/restore.sh" "$backup_file"

printf '%s\n' 'Database restore completed; redeploying previous immutable release.' >&2
exec bash "$SCRIPT_DIR/deploy.sh" "$previous_image_ref" "$previous_source_sha" "$previous_version"

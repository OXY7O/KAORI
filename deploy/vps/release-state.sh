#!/usr/bin/env bash

# Shared by VPS operator commands that need to parse the production Compose
# graph outside an active deploy.sh transaction. Ordinary deployment exports
# these values directly; standalone backup/restore/verify recovers the exact
# last successful release identity from deployment state instead of relying on
# mutable values in /etc/kaori/.env.production.

KAORI_STATE_DIR="${KAORI_STATE_DIR:-/var/lib/kaori/deploy-state}"

load_current_release_identity() {
  if [[ -n "${KAORI_IMAGE:-}" && -n "${APP_VERSION:-}" && -n "${APP_BUILD_SHA:-}" && -n "${APP_BUILD_DATE:-}" ]]; then
    export KAORI_IMAGE APP_VERSION APP_BUILD_SHA APP_BUILD_DATE
    return 0
  fi

  local image_file="$KAORI_STATE_DIR/current-image"
  local version_file="$KAORI_STATE_DIR/current-version"
  local source_file="$KAORI_STATE_DIR/source-sha"
  local build_date_file="$KAORI_STATE_DIR/current-build-date"

  [[ -r "$image_file" ]] || return 1
  [[ -r "$version_file" ]] || return 1
  [[ -r "$source_file" ]] || return 1
  [[ -r "$build_date_file" ]] || return 1

  KAORI_IMAGE="$(tr -d '\r\n' < "$image_file")"
  APP_VERSION="$(tr -d '\r\n' < "$version_file")"
  APP_BUILD_SHA="$(tr -d '\r\n' < "$source_file")"
  APP_BUILD_DATE="$(tr -d '\r\n' < "$build_date_file")"

  [[ "$KAORI_IMAGE" =~ @sha256:[0-9a-f]{64}$ ]] || return 1
  [[ "$APP_VERSION" =~ ^v[0-9]+\.[0-9]+\.[0-9]+(-rc\.[0-9]+)?$ ]] || return 1
  [[ "$APP_BUILD_SHA" =~ ^[0-9a-f]{40}$ ]] || return 1
  [[ -n "$APP_BUILD_DATE" ]] || return 1

  export KAORI_IMAGE APP_VERSION APP_BUILD_SHA APP_BUILD_DATE
}

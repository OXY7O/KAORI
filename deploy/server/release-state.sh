#!/usr/bin/env bash

KAORI_STATE_DIR="${KAORI_STATE_DIR:-/var/lib/kaori/deploy-state}"
KAORI_ACTIVE_RELEASE_ENV_FILE="${KAORI_ACTIVE_RELEASE_ENV_FILE:-/var/lib/kaori/deploy-state/release.env}"

validate_release_identity() {
  [[ "${KAORI_IMAGE:-}" =~ @sha256:[0-9a-f]{64}$ ]] || return 1
  [[ "${APP_VERSION:-}" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-rc\.[0-9]+)?$ ]] || return 1
  [[ "${APP_BUILD_SHA:-}" =~ ^[0-9a-f]{40}$ ]] || return 1
  [[ -n "${APP_BUILD_DATE:-}" ]] || return 1
}

load_release_env_file() {
  local release_file="$1"
  local key value
  [[ -r "$release_file" && -f "$release_file" && ! -L "$release_file" ]] || return 1

  KAORI_IMAGE=''
  APP_VERSION=''
  APP_BUILD_SHA=''
  APP_BUILD_DATE=''
  while IFS='=' read -r key value; do
    case "$key" in
      KAORI_IMAGE) KAORI_IMAGE="$value" ;;
      APP_VERSION) APP_VERSION="$value" ;;
      APP_BUILD_SHA) APP_BUILD_SHA="$value" ;;
      APP_BUILD_DATE) APP_BUILD_DATE="$value" ;;
    esac
  done < "$release_file"

  validate_release_identity || return 1
  export KAORI_IMAGE APP_VERSION APP_BUILD_SHA APP_BUILD_DATE
}

load_current_release_identity() {
  if validate_release_identity; then
    export KAORI_IMAGE APP_VERSION APP_BUILD_SHA APP_BUILD_DATE
    return 0
  fi

  if load_release_env_file "$KAORI_ACTIVE_RELEASE_ENV_FILE"; then
    return 0
  fi

  local image_file="$KAORI_STATE_DIR/current-image"
  local version_file="$KAORI_STATE_DIR/current-version"
  local source_file="$KAORI_STATE_DIR/source-sha"
  local build_date_file="$KAORI_STATE_DIR/current-build-date"
  local release_version

  [[ -r "$image_file" && -r "$version_file" && -r "$source_file" && -r "$build_date_file" ]] || return 1
  KAORI_IMAGE="$(tr -d '\r\n' < "$image_file")"
  release_version="$(tr -d '\r\n' < "$version_file")"
  APP_VERSION="${release_version#v}"
  APP_BUILD_SHA="$(tr -d '\r\n' < "$source_file")"
  APP_BUILD_DATE="$(tr -d '\r\n' < "$build_date_file")"

  [[ "$release_version" =~ ^v[0-9]+\.[0-9]+\.[0-9]+(-rc\.[0-9]+)?$ ]] || return 1
  validate_release_identity || return 1
  export KAORI_IMAGE APP_VERSION APP_BUILD_SHA APP_BUILD_DATE
}

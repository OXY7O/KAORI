#!/usr/bin/env bash

KAORI_STATE_DIR="${KAORI_STATE_DIR:-/var/lib/kaori/deploy-state}"
KAORI_ACTIVE_RELEASE_ENV_FILE="${KAORI_ACTIVE_RELEASE_ENV_FILE:-/var/lib/kaori/deploy-state/release.env}"

# Runtime target identity comes from operator-selected Environment configuration.
# No slot-count mode. A custom project must own all persistent data and receipts.
kaori_validate_target_config() {
  KAORI_COMPOSE_PROJECT="${KAORI_COMPOSE_PROJECT:-kaori-production}"
  KAORI_NETWORK_NAME="${KAORI_NETWORK_NAME:-kaori-production}"
  KAORI_INSTANCE_VOLUME="${KAORI_INSTANCE_VOLUME:-kaori-production-instance}"
  KAORI_POSTGRES_VOLUME="${KAORI_POSTGRES_VOLUME:-kaori-vps-postgres-data}"
  KAORI_REDIS_VOLUME="${KAORI_REDIS_VOLUME:-kaori-vps-redis-data}"
  KAORI_STATE_DIR="${KAORI_STATE_DIR:-/var/lib/kaori/deploy-state}"
  KAORI_BACKUP_DIR="${KAORI_BACKUP_DIR:-/var/lib/kaori/backups}"
  KAORI_ACTIVE_RELEASE_ENV_FILE="${KAORI_ACTIVE_RELEASE_ENV_FILE:-/var/lib/kaori/deploy-state/release.env}"
  KAORI_TRUST_DIR="${KAORI_TRUST_DIR:-/etc/kaori/trust}"
  KAORI_DEPLOY_ROOT="${KAORI_DEPLOY_ROOT:-/opt/kaori}"

  if [[ "$KAORI_COMPOSE_PROJECT" == "kaori-production" ]]; then
    [[ "$KAORI_NETWORK_NAME" == "kaori-production" &&
       "$KAORI_INSTANCE_VOLUME" == "kaori-production-instance" &&
       "$KAORI_POSTGRES_VOLUME" == "kaori-vps-postgres-data" &&
       "$KAORI_REDIS_VOLUME" == "kaori-vps-redis-data" &&
       "$KAORI_STATE_DIR" == "/var/lib/kaori/deploy-state" &&
       "$KAORI_BACKUP_DIR" == "/var/lib/kaori/backups" &&
       "$KAORI_ACTIVE_RELEASE_ENV_FILE" == "/var/lib/kaori/deploy-state/release.env" &&
       "$KAORI_TRUST_DIR" == "/etc/kaori/trust" ]] || {
      printf 'Invalid canonical project/resource/receipt target binding\n' >&2
      return 1
    }
  else
    [[ "$KAORI_COMPOSE_PROJECT" =~ ^kaori-app-[a-z0-9]+(-[a-z0-9]+)*$ ]] || {
      printf 'Unsupported Application Compose project namespace\n' >&2
      return 1
    }
    local project="$KAORI_COMPOSE_PROJECT"
    local state_root="/var/lib/kaori/targets/$project"
    local config_root="/etc/kaori/targets/$project"
    [[ "$KAORI_NETWORK_NAME" == "$project" &&
       "$KAORI_INSTANCE_VOLUME" == "$project-instance" &&
       "$KAORI_POSTGRES_VOLUME" == "$project-postgres-data" &&
       "$KAORI_REDIS_VOLUME" == "$project-redis-data" &&
       "$KAORI_STATE_DIR" == "$state_root/deploy-state" &&
       "$KAORI_BACKUP_DIR" == "$state_root/backups" &&
       "$KAORI_ACTIVE_RELEASE_ENV_FILE" == "$state_root/deploy-state/release.env" &&
       "${KAORI_DEPLOY_ENV_FILE:-}" == "$config_root/deploy.env" &&
       "${KAORI_APP_ENV_FILE:-}" == "$config_root/app.env" &&
       "${KAORI_SECRETS_ENV_FILE:-}" == "$config_root/secrets.env" &&
       "${KAORI_POSTGRES_ADMIN_ENV_FILE:-}" == "$config_root/postgres-admin.env" &&
       "${KAORI_POSTGRES_MIGRATION_ENV_FILE:-}" == "$config_root/postgres-migrate.env" &&
       "$KAORI_TRUST_DIR" == "$config_root/trust" &&
       "$KAORI_DEPLOY_ROOT" == "/opt/kaori/targets/$project" ]] || {
      printf 'Invalid distinct Application target: project, config, volumes or rollback state overlap\n' >&2
      return 1
    }
  fi

  [[ -z "${COMPOSE_PROJECT_NAME:-}" || "$COMPOSE_PROJECT_NAME" == "$KAORI_COMPOSE_PROJECT" ]] || {
    printf 'COMPOSE_PROJECT_NAME conflicts with configured runtime project\n' >&2
    return 1
  }
  COMPOSE_PROJECT_NAME="$KAORI_COMPOSE_PROJECT"
  export KAORI_COMPOSE_PROJECT KAORI_NETWORK_NAME KAORI_INSTANCE_VOLUME
  export KAORI_POSTGRES_VOLUME KAORI_REDIS_VOLUME KAORI_STATE_DIR KAORI_BACKUP_DIR
  export KAORI_ACTIVE_RELEASE_ENV_FILE KAORI_TRUST_DIR KAORI_DEPLOY_ROOT
  export COMPOSE_PROJECT_NAME
}

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

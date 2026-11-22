#!/usr/bin/env bash
set -Eeuo pipefail
set +x

set -Eeuo pipefail
fail() { echo "BLOCK: $*" >&2; exit 1; }

if [[ "$GITHUB_EVENT_NAME" == push ]]; then
  [[ "$GITHUB_REF" == refs/heads/kaori/staging ]] || fail 'staging push only'
else
  case "$TARGET_ENV" in
    staging) [[ "$GITHUB_REF" == refs/heads/kaori/staging ]] || fail 'staging branch required' ;;
    production) [[ "$GITHUB_REF" == refs/heads/main ]] || fail 'protected main branch required' ;;
    *) fail 'unknown Environment' ;;
  esac
fi

case "$(printenv TARGET_INVENTORY || printf false)" in
  true) [[ "$GITHUB_EVENT_NAME" == workflow_dispatch ]] ||
    fail 'runtime inventory requires explicit manual dispatch' ;;
  false) ;;
  *) fail 'invalid runtime inventory mode' ;;
esac

# Issue #5116: release-bound target observation is never a generic credential probe.
# Only the already manual protected-main stable publisher can activate this mode.
case "${RELEASE_GATE:-false}" in
  true)
    [[ "$TARGET_ENV" == production &&
       "$GITHUB_EVENT_NAME" == workflow_dispatch &&
       "$GITHUB_REF" == refs/heads/main &&
       "${TARGET_INVENTORY:-false}" == true ]] ||
      fail 'stable runtime gate requires explicit protected-main production inventory'
    [[ "${EXPECTED_RC_SOURCE_SHA:-}" =~ ^[0-9a-f]{40}$ &&
       "${EXPECTED_RC_IMAGE_DIGEST:-}" =~ ^sha256:[0-9a-f]{64}$ &&
       "${EXPECTED_RELEASE_VERSION:-}" =~ ^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$ &&
       "${EXPECTED_RC_TAG:-}" =~ ^v[0-9]+\.[0-9]+\.[0-9]+-rc\.[1-9][0-9]*$ &&
       "${EXPECTED_RC_TAG}" == "v${EXPECTED_RELEASE_VERSION}-rc."* ]] ||
      fail 'stable runtime gate requires an exact accepted RC source, tag, digest and version'
    [[ -z "${EXPECTED_RUNTIME_VERSION:-}" ||
       "${EXPECTED_RUNTIME_VERSION}" == "${EXPECTED_RELEASE_VERSION}" ||
       "${EXPECTED_RUNTIME_VERSION}" == "${EXPECTED_RC_TAG#v}" ]] ||
      fail 'release-bound runtime observation must match exact stable or accepted RC version'
    ;;
  false) ;;
  *) fail 'unknown stable runtime gate mode' ;;
esac

for name in REGISTRY_HOST REGISTRY_IMAGE REGISTRY_USER REGISTRY_PASSWORD DEPLOY_HOST DEPLOY_PORT DEPLOY_USER DEPLOY_ROOT DEPLOY_SSH_KEY DEPLOY_SSH_PASSPHRASE DEPLOY_KNOWN_HOSTS; do
  [[ -n "$(printenv "$name")" ]] || fail "missing required Environment credential/config: $name"
done

[[ "$REGISTRY_HOST" =~ ^[a-zA-Z0-9.-]+(:[0-9]{1,5})?$ ]] || fail 'invalid registry hostname'
[[ "$REGISTRY_IMAGE" == "$REGISTRY_HOST/"* ]] || fail 'registry image outside configured registry'
[[ "$DEPLOY_HOST" =~ ^[a-zA-Z0-9._-]+$ ]] || fail 'invalid SSH host'
[[ "$DEPLOY_USER" =~ ^[a-zA-Z0-9._-]+$ ]] || fail 'invalid SSH user'
[[ "$DEPLOY_PORT" =~ ^[0-9]{1,5}$ ]] || fail 'SSH port must be a number'
(( 10#$DEPLOY_PORT > 0 && 10#$DEPLOY_PORT < 65536 )) || fail 'SSH port out of range'
if [[ "$DEPLOY_ROOT" != /opt/kaori ]]; then
  [[ "$DEPLOY_ROOT" =~ ^/opt/kaori/targets/kaori-app-[a-z0-9]+(-[a-z0-9]+)*$ ]] || fail 'invalid App target root'
  project="$DEPLOY_ROOT"
  project="${project##*/}"
  RECEIPT_PATH="/var/lib/kaori/targets/$project/deploy-state/release.env"
  HOST_ENV_PATH="/etc/kaori/targets/$project/deploy.env"
fi
[[ "$RECEIPT_PATH" == /* && "$RECEIPT_PATH" != *'..'* ]] || fail 'unsafe receipt path'
printf '%s\n' "RECEIPT_PATH=$RECEIPT_PATH" "HOST_ENV_PATH=$HOST_ENV_PATH" >> "$GITHUB_ENV"
echo 'PASS: approved branch, Environment and target syntax'

set -Eeuo pipefail
umask 077
tmp="$(mktemp -d)"
trap 'rm -rf -- "$tmp"' EXIT
mkdir -m 700 "$tmp/docker"
if ! printf '%s' "$REGISTRY_PASSWORD" |
  docker --config "$tmp/docker" login "$REGISTRY_HOST" \
    --username "$REGISTRY_USER" --password-stdin >/dev/null 2>&1
then
  echo 'BLOCK: configured Environment registry credentials were rejected' >&2
  exit 1
fi
echo 'PASS: Environment registry credential authentication (no image push/pull)'
rm -rf -- "$tmp"
trap - EXIT

set -Eeuo pipefail
umask 077
fail() { echo "BLOCK: $*" >&2; exit 1; }
tmp="$(mktemp -d)"
agent_started=false
cleanup() {
  if [[ "$agent_started" == true ]]; then ssh-agent -k >/dev/null 2>&1 || true; fi
  rm -rf -- "$tmp"
}
trap cleanup EXIT INT TERM HUP
printf '%s\n' "$DEPLOY_SSH_KEY" > "$tmp/id"
printf '%s\n' "$DEPLOY_KNOWN_HOSTS" > "$tmp/known_hosts"
chmod 600 "$tmp/id" "$tmp/known_hosts"
host_id="$DEPLOY_HOST"
[[ "$DEPLOY_PORT" == 22 ]] || host_id="[$DEPLOY_HOST]:$DEPLOY_PORT"
ssh-keygen -F "$host_id" -f "$tmp/known_hosts" >/dev/null ||
  fail 'pinned SSH host identity missing (no TOFU permitted)'
cat > "$tmp/askpass" <<'ASKPASS'
#!/usr/bin/env bash
printf '%s\n' "$DEPLOY_SSH_PASSPHRASE"
ASKPASS
chmod 700 "$tmp/askpass"
eval "$(ssh-agent -s)" >/dev/null
agent_started=true
export SSH_ASKPASS="$tmp/askpass" SSH_ASKPASS_REQUIRE=force DISPLAY=:0
setsid -w ssh-add "$tmp/id" </dev/null >/dev/null 2>&1 ||
  fail 'Environment SSH key/passphrase cannot be loaded'

{
  printf 'root=%q\n' "$DEPLOY_ROOT"
  printf 'receipt=%q\n' "$RECEIPT_PATH"
  printf 'deploy_env=%q\n' "$HOST_ENV_PATH"
  printf 'inventory_requested=%q\n' "$(printenv TARGET_INVENTORY || printf false)"
  printf 'registry_image=%q\n' "$REGISTRY_IMAGE"
  printf 'release_gate_requested=%q\n' "${RELEASE_GATE:-false}"
  printf 'expected_rc_source_sha=%q\n' "${EXPECTED_RC_SOURCE_SHA:-}"
  printf 'expected_rc_image_digest=%q\n' "${EXPECTED_RC_IMAGE_DIGEST:-}"
  printf 'expected_release_version=%q\n' "${EXPECTED_RELEASE_VERSION:-}"
  printf 'expected_rc_tag=%q\n' "${EXPECTED_RC_TAG:-}"
  printf 'expected_runtime_version=%q\n' "${EXPECTED_RUNTIME_VERSION:-${EXPECTED_RELEASE_VERSION:-}}"
  cat <<'REMOTE_READ_ONLY'
set -Eeuo pipefail
[[ -d "$root" && ! -L "$root" ]] || {
  echo 'BLOCK: configured deployment root missing/unsafe' >&2
  exit 1
}
[[ -f "$receipt" && ! -L "$receipt" ]] || {
  echo 'BLOCK: committed release receipt missing/unsafe' >&2
  exit 1
}
if [[ -n "$deploy_env" ]]; then
  [[ -f "$deploy_env" && ! -L "$deploy_env" ]] || {
    echo 'BLOCK: VM-local deployment config missing/unsafe' >&2
    exit 1
  }
fi
command -v docker >/dev/null 2>&1 || {
  echo 'BLOCK: target Docker CLI unavailable' >&2
  exit 1
}
docker info >/dev/null 2>&1 || {
  echo 'BLOCK: target deploy user lacks Docker daemon access' >&2
  exit 1
}
echo 'PASS: pinned SSH, prepared VM target, receipt and Docker access; read-only'

# Explicit inventory is observational. Normal push/credential preflight stops above.
# Never print host credentials, env files, Docker config, inspect JSON or private URLs.
if [[ "$inventory_requested" == true ]]; then
  [[ -r "$receipt" && -s "$receipt" ]] ||
    { echo 'BLOCK: committed release receipt is unreadable' >&2; exit 1; }
  [[ "$(stat -c %s -- "$receipt")" -le 4096 ]] ||
    { echo 'BLOCK: release receipt exceeds permitted size' >&2; exit 1; }

  # Read only four release identity keys; do not source arbitrary host files.
  for key in KAORI_IMAGE APP_VERSION APP_BUILD_SHA APP_BUILD_DATE; do
    [[ "$(grep -c "^$key=" "$receipt" || true)" == 1 ]] ||
      { echo 'BLOCK: release receipt identity is missing or duplicated' >&2; exit 1; }
  done
  [[ "$(wc -l < "$receipt")" -eq 4 ]] ||
    { echo 'BLOCK: unexpected release receipt fields' >&2; exit 1; }
  receipt_image="$(sed -n 's/^KAORI_IMAGE=//p' "$receipt")"
  receipt_version="$(sed -n 's/^APP_VERSION=//p' "$receipt")"
  receipt_sha="$(sed -n 's/^APP_BUILD_SHA=//p' "$receipt")"
  receipt_build="$(sed -n 's/^APP_BUILD_DATE=//p' "$receipt")"
  [[ "$receipt_image" =~ ^[^[:space:]]+@sha256:[0-9a-f]{64}$ &&
     "$receipt_image" == "$registry_image@sha256:"* &&
     "$receipt_version" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-rc\.[0-9]+)?$ &&
     "$receipt_sha" =~ ^[0-9a-f]{40}$ &&
     "$receipt_build" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[^[:space:]]+$ ]] ||
    { echo 'BLOCK: malformed or foreign immutable release receipt identity' >&2; exit 1; }
  [[ -d "$root/releases/$receipt_sha" && ! -L "$root/releases/$receipt_sha" ]] ||
    { echo 'BLOCK: committed source release directory unavailable' >&2; exit 1; }

  project='kaori-production'
  network='kaori-production'
  instance_volume='kaori-production-instance'
  postgres_volume='kaori-vps-postgres-data'
  redis_volume='kaori-vps-redis-data'
  if [[ "$root" != /opt/kaori ]]; then
    project="$(basename -- "$root")"
    [[ "$project" =~ ^kaori-app-[a-z0-9]+(-[a-z0-9]+)*$ ]] ||
      { echo 'BLOCK: unknown configured Application runtime namespace' >&2; exit 1; }
    network="$project"
    instance_volume="$project-instance"
    postgres_volume="$project-postgres-data"
    redis_volume="$project-redis-data"
  fi

  # All lookups are scoped by observed Compose project/service labels.
  # Only docker ps/inspect are permitted: no exec/pull/up/restart/write.
  checked_cid=''
  find_running_service() {
    local service="$1"
    checked_cid="$(docker ps --filter "label=com.docker.compose.project=$project" \
      --filter "label=com.docker.compose.service=$service" --format '{{.ID}}')"
    [[ "$checked_cid" =~ ^[0-9a-f]{12,64}$ ]] ||
      { echo "BLOCK: expected exactly one running $service in selected project" >&2; return 1; }
    [[ "$(docker inspect --format '{{.State.Status}}' "$checked_cid")" == running ]] ||
      { echo "BLOCK: selected $service is not running" >&2; return 1; }
  }

  web_cid=''
  app_count=0
  for service in web worker registry-security-worker maintenance-worker runtime-worker \
    validation-worker analytics-worker reports-worker forecasting-worker \
    resolver-execution-worker resolver-maintenance-worker beat
  do
    find_running_service "$service" || exit 1
    [[ "$(docker inspect --format '{{.Config.Image}}' "$checked_cid")" == "$receipt_image" ]] ||
      { echo "BLOCK: $service container image differs from committed digest" >&2; exit 1; }
    [[ "$(docker inspect --format '{{index .Config.Labels "org.opencontainers.image.revision"}}' "$checked_cid")" == "$receipt_sha" ]] ||
      { echo "BLOCK: $service OCI revision differs from committed source" >&2; exit 1; }
    health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}missing{{end}}' "$checked_cid")"
    [[ "$health" == healthy || "$health" == missing ]] ||
      { echo "BLOCK: $service container health is not ready" >&2; exit 1; }
    if [[ "$release_gate_requested" == true && "$service" == web &&
          "$health" != healthy ]]; then
      echo 'BLOCK: release target web health check missing or not healthy' >&2
      exit 1
    fi
    [[ "$service" != web ]] || web_cid="$checked_cid"
    (( app_count += 1 ))
  done
  [[ "$app_count" -eq 12 && -n "$web_cid" ]] ||
    { echo 'BLOCK: Application container inventory incomplete' >&2; exit 1; }

  web_networks="$(docker inspect --format '{{range $name, $_ := .NetworkSettings.Networks}}{{println $name}}{{end}}' "$web_cid")"
  grep -Fxq -- "$network" <<< "$web_networks" ||
    { echo 'BLOCK: web container is not attached to configured network' >&2; exit 1; }
  web_volumes="$(docker inspect --format '{{range .Mounts}}{{if eq .Type "volume"}}{{println .Name}}{{end}}{{end}}' "$web_cid")"
  grep -Fxq -- "$instance_volume" <<< "$web_volumes" ||
    { echo 'BLOCK: web instance volume differs from selected project' >&2; exit 1; }

  for service in postgres redis; do
    find_running_service "$service" || exit 1
    [[ "$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}missing{{end}}' "$checked_cid")" == healthy ]] ||
      { echo "BLOCK: selected $service is not healthy" >&2; exit 1; }
    published_ports="$(docker inspect --format '{{json .NetworkSettings.Ports}}' "$checked_cid")"
    [[ "$published_ports" != *HostPort* ]] ||
      { echo "BLOCK: selected $service exposes a host port" >&2; exit 1; }
    expected_volume="$postgres_volume"
    [[ "$service" != redis ]] || expected_volume="$redis_volume"
    actual_volumes="$(docker inspect --format '{{range .Mounts}}{{if eq .Type "volume"}}{{println .Name}}{{end}}{{end}}' "$checked_cid")"
    grep -Fxq -- "$expected_volume" <<< "$actual_volumes" ||
      { echo "BLOCK: $service volume differs from selected project" >&2; exit 1; }
  done

  # Do not authorize stable tag/registry publication from a credential-only snapshot.
  # This is the read-only stage; actual mutation/convergence belongs to #5117.
  if [[ "$release_gate_requested" == true ]]; then
    # #5117: an explicitly selected RC-version observation may qualify a future
    # same-digest stable-version reconciliation, never stable publication.
    # Default stays the original strict stable-version READY_NOOP gate.
    [[ "$expected_runtime_version" == "$expected_release_version" ||
       "$expected_runtime_version" == "${expected_rc_tag#v}" ]] ||
      { echo 'BLOCK: release-bound runtime observation version is not accepted' >&2; exit 1; }
    if [[ "$receipt_sha" != "$expected_rc_source_sha" ||
          "$receipt_image" != "$registry_image@$expected_rc_image_digest" ||
          "$receipt_version" != "$expected_runtime_version" ]]; then
      echo 'NEEDS_RECONCILIATION: selected target does not yet match accepted RC digest/source and stable runtime version; stable publication held' >&2
      exit 1
    fi

    # The server's existing deploy.sh owns these committed results and rollback
    # pointers. Inspect their existence only; do not evaluate host-owned shell.
    state_dir="${receipt%/*}"
    [[ -d "$state_dir" && ! -L "$state_dir" ]] ||
      { echo 'BLOCK: selected target release state directory unsafe' >&2; exit 1; }
    for result_key in verification-result migration-result; do
      result_file="$state_dir/$result_key"
      [[ -f "$result_file" && ! -L "$result_file" && -r "$result_file" ]] ||
        { echo 'BLOCK: committed migration/verification evidence missing' >&2; exit 1; }
      [[ "$(cat -- "$result_file")" == pass ]] ||
        { echo 'BLOCK: committed migration/verification evidence not PASS' >&2; exit 1; }
    done
    [[ -f "$state_dir/previous-release.env" &&
       ! -L "$state_dir/previous-release.env" &&
       -r "$state_dir/previous-release.env" &&
       -s "$state_dir/previous-release.env" ]] ||
      { echo 'BLOCK: previous immutable release receipt unavailable for rollback' >&2; exit 1; }
    previous_receipt="$state_dir/previous-release.env"
    [[ "$(wc -l < "$previous_receipt")" -eq 4 ]] ||
      { echo 'BLOCK: previous release receipt structure invalid' >&2; exit 1; }
    for key in KAORI_IMAGE APP_VERSION APP_BUILD_SHA APP_BUILD_DATE; do
      [[ "$(grep -c "^$key=" "$previous_receipt" || true)" == 1 ]] ||
        { echo 'BLOCK: previous release receipt identity missing or duplicated' >&2; exit 1; }
    done
    previous_image="$(sed -n 's/^KAORI_IMAGE=//p' "$previous_receipt")"
    previous_version="$(sed -n 's/^APP_VERSION=//p' "$previous_receipt")"
    previous_sha="$(sed -n 's/^APP_BUILD_SHA=//p' "$previous_receipt")"
    previous_date="$(sed -n 's/^APP_BUILD_DATE=//p' "$previous_receipt")"
    [[ "$previous_image" =~ ^[^[:space:]]+@sha256:[0-9a-f]{64}$ &&
       "$previous_image" == "$registry_image@sha256:"* &&
       "$previous_version" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-rc\.[0-9]+)?$ &&
       "$previous_sha" =~ ^[0-9a-f]{40}$ &&
       "$previous_date" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[^[:space:]]+$ &&
       -d "$root/releases/$previous_sha" && ! -L "$root/releases/$previous_sha" ]] ||
      { echo 'BLOCK: previous release receipt is not a recoverable immutable artifact' >&2; exit 1; }
    [[ -f "$state_dir/previous-backup" &&
       ! -L "$state_dir/previous-backup" &&
       -r "$state_dir/previous-backup" ]] ||
      { echo 'BLOCK: committed previous backup pointer unavailable' >&2; exit 1; }
    IFS= read -r rollback_backup < "$state_dir/previous-backup" ||
      { echo 'BLOCK: previous backup pointer unreadable' >&2; exit 1; }
    backup_root="${state_dir%/*}/backups"
    [[ -d "$backup_root" && ! -L "$backup_root" &&
       "$rollback_backup" == "$backup_root/"* &&
       "$rollback_backup" != *'..'* && "$rollback_backup" != *$'\n'* &&
       -f "$rollback_backup" && ! -L "$rollback_backup" &&
       -s "$rollback_backup" && -f "$rollback_backup.sha256" &&
       ! -L "$rollback_backup.sha256" ]] ||
      { echo 'BLOCK: committed rollback backup evidence is unsafe or missing' >&2; exit 1; }
    [[ "$(wc -l < "$rollback_backup.sha256")" -eq 1 &&
       "$(cat -- "$rollback_backup.sha256")" == "$(sha256sum -- "$rollback_backup")" ]] ||
      { echo 'BLOCK: rollback checksum does not identify the selected backup' >&2; exit 1; }
    sha256sum --check --status "$rollback_backup.sha256" ||
      { echo 'BLOCK: rollback backup digest verification failed' >&2; exit 1; }
    if [[ "$expected_runtime_version" == "$expected_release_version" ]]; then
      echo 'READY_NOOP: accepted immutable digest/source, stable runtime identity and committed rollback evidence verified on configured target'
    else
      echo 'READY_FOR_STABLE_CONVERGENCE: accepted RC digest/source, exact RC runtime version and rollback evidence verified; stable runtime version is not yet committed'
    fi
    echo 'LIMIT: provider-edge acceptance and actual recovery drill require separately governed #5117 UAT; read-only observation is not release authorization'
  fi

  receipt_digest="$(printf '%s' "$receipt_image" | sed 's/^.*@//')"
  echo "PASS: configured runtime inventory · project=$project source=$receipt_sha version=$receipt_version digest=$receipt_digest; 12 app containers match receipt; network/volumes and private healthy PostgreSQL/Redis checked"
  echo 'LIMIT: observational snapshot only; no database transactions, rollback drill, browser UAT, supply-chain verification or provider-edge acceptance'
fi
REMOTE_READ_ONLY
} | ssh \
  -o BatchMode=yes -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes \
  -o UserKnownHostsFile="$tmp/known_hosts" -o ConnectTimeout=15 \
  -o ConnectionAttempts=1 -p "$DEPLOY_PORT" -i "$tmp/id" \
  "$DEPLOY_USER@$DEPLOY_HOST" 'bash -s'

{
  echo '### Environment credential preflight — PASS'
  echo 'Registry login, pinned SSH identity and remote target/receipt/Docker access verified.'
  echo 'Read-only: no image publication, Docker container change, database command, host file write, DNS, release or deployment.'
  echo 'This check does NOT replace signed digest verification, real UAT, Human Acceptance or production deployment approval.'
  if [[ "$(printenv TARGET_INVENTORY || printf false)" == true ]]; then
    echo 'Opt-in runtime inventory compared receipt, application containers and private volumes; see sanitized PASS/BLOCK job lines.'
    if [[ "${RELEASE_GATE:-false}" == true ]]; then
      if [[ "${EXPECTED_RUNTIME_VERSION:-${EXPECTED_RELEASE_VERSION:-}}" == "${EXPECTED_RELEASE_VERSION:-}" ]]; then
        echo 'Release-bound read-only gate classified selected target as READY_NOOP; recovery and edge acceptance remain separately governed.'
      else
        echo 'Read-only RC observation is READY_FOR_STABLE_CONVERGENCE only; stable publication remains blocked until runtime convergence and full verification.'
      fi
    fi
    echo 'This is not recovery/rollback testing, DB migration acceptance, public-edge acceptance or an authorized stable release.'
  fi
} >> "$GITHUB_STEP_SUMMARY"

#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "$SCRIPT_DIR/../.." 2>/dev/null && pwd || true)"

deploy_user='kaori-deploy'
deploy_root='/opt/kaori'
ssh_public_key_file=''
ssh_port='22'
app_env_template="${ROOT_DIR:+$ROOT_DIR/deploy/env/app.env.example}"
secrets_env_template="${ROOT_DIR:+$ROOT_DIR/deploy/env/secrets.env.example}"
deploy_env_template="${ROOT_DIR:+$ROOT_DIR/deploy/env/deploy.env.example}"
app_env_file='/etc/kaori/app.env'
secrets_env_file='/etc/kaori/secrets.env'
deploy_env_file='/etc/kaori/deploy.env'
state_dir='/var/lib/kaori/deploy-state'
backup_dir='/var/lib/kaori/backups'

fail() {
  printf 'KAORI server host preparation failed: %s\n' "$*" >&2
  exit 1
}

usage() {
  cat <<'USAGE'
Usage:
  sudo bash deploy/server/bootstrap-host.sh --ssh-public-key-file PATH [options]

Required:
  --ssh-public-key-file PATH   RSA public key retained by the operator off-host.

Options:
  --deploy-user USER           Dedicated non-root deployment user (default: kaori-deploy).
  --deploy-root PATH           KAORI release root (default: /opt/kaori).
  --app-env-template PATH      Portable app env template.
  --secrets-env-template PATH  Portable secret env template.
  --deploy-env-template PATH   Server deployment-adapter env template.
  --ssh-port PORT              SSH port reported for GitHub Environment configuration.
  -h, --help                   Show this help.
USAGE
}

while (($#)); do
  case "$1" in
    --ssh-public-key-file) ssh_public_key_file="${2:?}"; shift 2 ;;
    --deploy-user) deploy_user="${2:?}"; shift 2 ;;
    --deploy-root) deploy_root="${2:?}"; shift 2 ;;
    --app-env-template) app_env_template="${2:?}"; shift 2 ;;
    --secrets-env-template) secrets_env_template="${2:?}"; shift 2 ;;
    --deploy-env-template) deploy_env_template="${2:?}"; shift 2 ;;
    --ssh-port) ssh_port="${2:?}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) fail "unknown argument: $1" ;;
  esac
done

(( EUID == 0 )) || fail 'run this script as root (sudo)'
[[ -n "$ssh_public_key_file" ]] || fail '--ssh-public-key-file is required'
[[ "$deploy_user" =~ ^[a-z_][a-z0-9_-]{0,30}$ ]] || fail 'deploy user contains unsupported characters'
[[ "$deploy_user" != 'root' && "$deploy_user" != 'github-runner' ]] || fail 'deploy user must remain a dedicated non-root identity'
[[ "$deploy_root" =~ ^/[A-Za-z0-9._/-]+$ && "$deploy_root" != '/' ]] || fail 'deploy root must be a safe absolute path below /'
[[ "$ssh_port" =~ ^[0-9]{1,5}$ ]] || fail 'SSH port must be numeric'
(( 10#$ssh_port >= 1 && 10#$ssh_port <= 65535 )) || fail 'SSH port must be between 1 and 65535'

if [[ -d /opt/actions-runner ]]; then
  printf 'GitHub runner co-location detected; preserving GitHub runner operations at /opt/actions-runner.\n'
fi

for required_command in apt-get dpkg getent id install useradd usermod runuser systemctl; do
  command -v "$required_command" >/dev/null 2>&1 || fail "$required_command is required"
done

[[ -f /etc/os-release ]] || fail '/etc/os-release is required'
# shellcheck source=/dev/null
source /etc/os-release
case "${ID:-}" in
  ubuntu|debian) ;;
  *) fail "unsupported distribution: ${ID:-unknown}; supported hosts are Ubuntu and Debian" ;;
esac
codename="${VERSION_CODENAME:-${UBUNTU_CODENAME:-}}"
[[ -n "$codename" ]] || fail 'unable to determine distribution codename'

[[ -f "$ssh_public_key_file" && -r "$ssh_public_key_file" && ! -L "$ssh_public_key_file" ]] || fail 'SSH public key must be a readable regular non-symlink file'
mapfile -t public_key_lines < <(sed -e 's/\r$//' -e '/^[[:space:]]*$/d' "$ssh_public_key_file")
(( ${#public_key_lines[@]} == 1 )) || fail 'SSH public key file must contain exactly one non-empty line'
public_key="${public_key_lines[0]}"
[[ "$public_key" =~ ^ssh-rsa[[:space:]]+[A-Za-z0-9+/]+={0,3}([[:space:]].*)?$ ]] || fail 'SSH public key must be one RSA OpenSSH line'

install_docker_if_needed() {
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    printf 'Docker Engine and Compose plugin already available; preserving existing installation.\n'
    return
  fi

  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install -y ca-certificates curl
  install -d -m 0755 /etc/apt/keyrings
  curl --fail --silent --show-error --location "https://download.docker.com/linux/${ID}/gpg" --output /etc/apt/keyrings/docker.asc
  chmod 0644 /etc/apt/keyrings/docker.asc
  architecture="$(dpkg --print-architecture)"
  printf 'deb [arch=%s signed-by=%s] https://download.docker.com/linux/%s %s stable\n' \
    "$architecture" /etc/apt/keyrings/docker.asc "$ID" "$codename" > /etc/apt/sources.list.d/docker.list
  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
}

ensure_deploy_user() {
  if id "$deploy_user" >/dev/null 2>&1; then
    (( $(id -u "$deploy_user") != 0 )) || fail 'existing deploy user resolves to UID 0'
    printf 'deploy user already exists; preserving: %s\n' "$deploy_user"
  else
    useradd --create-home --shell /bin/bash "$deploy_user"
  fi
  deploy_home="$(getent passwd "$deploy_user" | cut -d: -f6)"
  deploy_group="$(id -gn "$deploy_user")"
  [[ "$deploy_home" =~ ^/[^[:space:]]+$ && "$deploy_home" != '/' ]] || fail 'unable to resolve safe deploy-user home'
  [[ -d "$deploy_home" ]] || fail "deploy-user home directory is missing: $deploy_home"
  getent group docker >/dev/null 2>&1 || fail 'Docker installation did not provide docker group'
  usermod -aG docker "$deploy_user"
}

prepare_ssh_access() {
  ssh_dir="$deploy_home/.ssh"
  authorized_keys="$ssh_dir/authorized_keys"
  install -d -m 0700 -o "$deploy_user" -g "$deploy_group" "$ssh_dir"
  printf '%s\n' "$public_key" > "$authorized_keys"
  chown "$deploy_user:$deploy_group" "$authorized_keys"
  chmod 700 "$ssh_dir"
  chmod 600 "$authorized_keys"
}

install_env_if_missing() {
  local template="$1"
  local destination="$2"
  local mode="$3"
  if [[ -e "$destination" ]]; then
    [[ -f "$destination" && ! -L "$destination" ]] || fail "existing environment path must be a regular non-symlink file: $destination"
    printf 'environment file already exists; preserving: %s\n' "$destination"
  else
    [[ -n "$template" && -f "$template" && -r "$template" && ! -L "$template" ]] || fail "reviewed environment template is required for $destination"
    install -m "$mode" -o "$deploy_user" -g "$deploy_group" "$template" "$destination"
    printf 'environment file initialized: %s\n' "$destination"
  fi
  chown "$deploy_user:$deploy_group" "$destination"
  chmod "$mode" "$destination"
}

prepare_paths_and_environment() {
  install -d -m 0755 /etc/kaori
  install -d -m 0755 -o "$deploy_user" -g "$deploy_group" "$deploy_root" "$deploy_root/releases"
  install -d -m 0700 -o "$deploy_user" -g "$deploy_group" "$state_dir" "$backup_dir"
  install_env_if_missing "$app_env_template" "$app_env_file" 0640
  install_env_if_missing "$secrets_env_template" "$secrets_env_file" 0600
  install_env_if_missing "$deploy_env_template" "$deploy_env_file" 0640
}

verify_runtime_access() {
  systemctl enable --now docker
  systemctl is-active --quiet docker || fail 'Docker service is not active'
  runuser -u "$deploy_user" -- docker info >/dev/null 2>&1 || fail 'deploy user cannot reach Docker daemon; re-login/group initialization may be required'
  runuser -u "$deploy_user" -- docker compose version >/dev/null 2>&1 || fail 'deploy user cannot execute Docker Compose plugin'
}

install_docker_if_needed
ensure_deploy_user
prepare_ssh_access
prepare_paths_and_environment
verify_runtime_access

cat <<EOF

KAORI SERVER HOST PREPARATION PASS

Deploy user : $deploy_user
Deploy root : $deploy_root
App env     : $app_env_file
Secrets env : $secrets_env_file
Deploy env  : $deploy_env_file
Release env : $state_dir/release.env (generated after governed deploy)
SSH port    : $ssh_port
Docker      : PASS
Compose     : PASS

WARNING: membership in the docker group grants root-equivalent privilege on this host.
EOF

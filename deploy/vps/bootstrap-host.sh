#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "$SCRIPT_DIR/../.." 2>/dev/null && pwd || true)"

deploy_user='kaori-deploy'
deploy_root='/opt/kaori'
env_template="${ROOT_DIR:+$ROOT_DIR/.env.production.example}"
ssh_public_key_file=''
ssh_port='22'
env_file='/etc/kaori/.env.production'
state_dir='/var/lib/kaori/deploy-state'
backup_dir='/var/lib/kaori/backups'

fail() {
  printf 'KAORI VPS host preparation failed: %s\n' "$*" >&2
  exit 1
}

usage() {
  cat <<'USAGE'
Usage:
  sudo bash deploy/vps/bootstrap-host.sh --ssh-public-key-file PATH [options]

Required:
  --ssh-public-key-file PATH   RSA public key generated and retained by the operator off-host.

Options:
  --deploy-user USER           Dedicated non-root deployment user (default: kaori-deploy).
  --deploy-root PATH           KAORI release root (default: /opt/kaori).
  --env-template PATH          Source .env.production.example used only when the real env is absent.
  --ssh-port PORT              SSH port reported for GitHub Environment configuration (default: 22).
  -h, --help                   Show this help.

This bootstrap installs only the operator-supplied public key. The private key
and passphrase must remain off-host and are supplied to GitHub Environment uat.
USAGE
}

while (($#)); do
  case "$1" in
    --ssh-public-key-file)
      (($# >= 2)) || fail '--ssh-public-key-file requires a value'
      ssh_public_key_file="$2"
      shift 2
      ;;
    --deploy-user)
      (($# >= 2)) || fail '--deploy-user requires a value'
      deploy_user="$2"
      shift 2
      ;;
    --deploy-root)
      (($# >= 2)) || fail '--deploy-root requires a value'
      deploy_root="$2"
      shift 2
      ;;
    --env-template)
      (($# >= 2)) || fail '--env-template requires a value'
      env_template="$2"
      shift 2
      ;;
    --ssh-port)
      (($# >= 2)) || fail '--ssh-port requires a value'
      ssh_port="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      fail "unknown argument: $1"
      ;;
  esac
done

(( EUID == 0 )) || fail 'run this script as root (sudo)'
[[ -n "$ssh_public_key_file" ]] || fail '--ssh-public-key-file is required'
[[ "$deploy_user" =~ ^[a-z_][a-z0-9_-]{0,30}$ ]] || fail 'deploy user contains unsupported characters'
[[ "$deploy_user" != 'root' ]] || fail 'deploy user must not be root'
[[ "$deploy_root" =~ ^/[A-Za-z0-9._/-]+$ && "$deploy_root" != '/' ]] || fail 'deploy root must be a safe absolute path below /'
[[ "$ssh_port" =~ ^[0-9]{1,5}$ ]] || fail 'SSH port must be numeric'
(( 10#$ssh_port >= 1 && 10#$ssh_port <= 65535 )) || fail 'SSH port must be between 1 and 65535'

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

[[ -f "$ssh_public_key_file" && -r "$ssh_public_key_file" ]] || fail 'SSH public key file must be a readable regular file'
[[ ! -L "$ssh_public_key_file" ]] || fail 'SSH public key file must not be a symbolic link'
mapfile -t public_key_lines < <(sed -e 's/\r$//' -e '/^[[:space:]]*$/d' "$ssh_public_key_file")
(( ${#public_key_lines[@]} == 1 )) || fail 'SSH public key file must contain exactly one non-empty public key line'
public_key="${public_key_lines[0]}"
# Accepted public-key prefix: ssh-rsa 
[[ "$public_key" =~ ^ssh-rsa[[:space:]]+[A-Za-z0-9+/]+={0,3}([[:space:]].*)?$ ]] || fail 'SSH public key must be one RSA OpenSSH public-key line beginning with ssh-rsa'

install_docker_if_needed() {
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    printf 'Docker Engine and Compose plugin already available; preserving existing installation.\n'
    return
  fi

  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install -y ca-certificates curl
  command -v curl >/dev/null 2>&1 || fail 'curl installation did not provide an executable'
  install -d -m 0755 /etc/apt/keyrings
  curl --fail --silent --show-error --location \
    "https://download.docker.com/linux/${ID}/gpg" \
    --output /etc/apt/keyrings/docker.asc
  chmod 0644 /etc/apt/keyrings/docker.asc

  architecture="$(dpkg --print-architecture)"
  printf 'deb [arch=%s signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/%s %s stable\n' \
    "$architecture" "$ID" "$codename" > /etc/apt/sources.list.d/docker.list

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
  [[ "$deploy_home" =~ ^/[^[:space:]]+$ && "$deploy_home" != '/' ]] || fail 'unable to resolve a safe deploy-user home directory'
  [[ -d "$deploy_home" ]] || fail "deploy-user home directory is missing: $deploy_home"

  getent group docker >/dev/null 2>&1 || fail 'Docker installation did not provide the docker group'
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

prepare_paths_and_environment() {
  install -d -m 0755 /etc/kaori
  install -d -m 0755 -o "$deploy_user" -g "$deploy_group" "$deploy_root"
  install -d -m 0755 -o "$deploy_user" -g "$deploy_group" "$deploy_root/releases"
  install -d -m 0700 -o "$deploy_user" -g "$deploy_group" "$state_dir"
  install -d -m 0700 -o "$deploy_user" -g "$deploy_group" "$backup_dir"

  if [[ -e "$env_file" ]]; then
    [[ -f "$env_file" && ! -L "$env_file" ]] || fail "existing environment path must be a regular non-symlink file: $env_file"
    printf 'environment file already exists; preserving: %s\n' "$env_file"
  else
    [[ -n "$env_template" && -f "$env_template" && -r "$env_template" ]] || fail 'environment template is required when /etc/kaori/.env.production does not exist'
    [[ ! -L "$env_template" ]] || fail 'environment template must not be a symbolic link'
    install -m 0600 -o "$deploy_user" -g "$deploy_group" "$env_template" "$env_file"
    printf 'environment file initialized from reviewed template: %s\n' "$env_file"
  fi

  chown "$deploy_user:$deploy_group" "$env_file"
  chmod 600 "$env_file"
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

KAORI VPS HOST PREPARATION PASS

Deploy user : $deploy_user
Deploy root : $deploy_root
Environment : $env_file
SSH home    : $deploy_home/.ssh
SSH port    : $ssh_port
Docker      : PASS
Compose     : PASS

WARNING: membership in the docker group grants root-equivalent privilege on this host.

GitHub Environment variables:
KAORI_VPS_USER=$deploy_user
KAORI_VPS_PORT=$ssh_port
KAORI_VPS_DEPLOY_ROOT=$deploy_root
KAORI_VPS_HOST=<set-to-the-reviewed-vps-hostname-or-ip>

GitHub Environment secrets still required:
KAORI_VPS_SSH_PRIVATE_KEY
KAORI_VPS_SSH_PASSPHRASE
KAORI_VPS_KNOWN_HOSTS
KAORI_DOCKER_REGISTRY_USERNAME
KAORI_DOCKER_REGISTRY_PASSWORD

Next operator actions:
1. Review and complete $env_file without committing its contents.
2. Verify SSH login using the private key retained on the laptop.
3. Verify the VPS host-key fingerprint out-of-band before setting KAORI_VPS_KNOWN_HOSTS.
4. Run the governed UAT deployment only from an admitted intentional RC.
EOF

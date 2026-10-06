#!/usr/bin/env bash
set -euo pipefail

RUNNER_VERSION="${RUNNER_VERSION:-2.328.0}"
RUNNER_SHA256_X64="${RUNNER_SHA256_X64:-01066fad3a2893e63e6ca880ae3a1fad5bf9329d60e77ee15f2b97c148c3cd4e}"
RUNNER_SHA256_ARM64="${RUNNER_SHA256_ARM64:-b801b9809c4d9301932bccadf57ca13533073b2aa9fa9b8e625a8db905b5d8eb}"
RUNNER_USER="${RUNNER_USER:-github-runner}"
RUNNER_HOME="${RUNNER_HOME:-${RUNNER_DIR:-/opt/actions-runner}}"
WITH_RUNNER_BINARY=false

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

usage() {
  cat <<'USAGE'
Usage: sudo ops/github-runner/bootstrap-host.sh [options]

Options:
  --with-runner-binary  Download and prepare the pinned GitHub Actions Runner archive.
  --runner-user NAME    Service account to provision (default: github-runner).
  --runner-home PATH    Runner installation directory (default: /opt/actions-runner).
  -h, --help            Show this help.
USAGE
}

while (($#)); do
  case "$1" in
    --with-runner-binary)
      WITH_RUNNER_BINARY=true
      ;;
    --runner-user)
      shift
      (($#)) || fail '--runner-user requires a value'
      RUNNER_USER="$1"
      ;;
    --runner-home)
      shift
      (($#)) || fail '--runner-home requires a value'
      RUNNER_HOME="$1"
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      fail "unknown argument: $1"
      ;;
  esac
  shift
done

[[ $EUID -eq 0 ]] || fail 'run as root'
[[ -r /etc/os-release ]] || fail '/etc/os-release is required'
command -v systemctl >/dev/null 2>&1 || fail 'systemd is required'
[[ -d /run/systemd/system ]] || fail 'systemd is not running'

case "$(uname -m)" in
  x86_64)
    runner_arch='x64'
    runner_sha="$RUNNER_SHA256_X64"
    ;;
  aarch64|arm64)
    runner_arch='arm64'
    runner_sha="$RUNNER_SHA256_ARM64"
    ;;
  *)
    fail "unsupported CPU architecture: $(uname -m)"
    ;;
esac

install_apt_prerequisites() {
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install -y ca-certificates curl gnupg git jq sudo tar gzip

  install -m 0755 -d /etc/apt/keyrings
  if [[ ! -s /etc/apt/keyrings/docker.asc ]]; then
    curl -fsSL "https://download.docker.com/linux/${ID}/gpg" -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc
  fi

  local codename="${VERSION_CODENAME:-}"
  [[ -n "$codename" ]] || fail 'VERSION_CODENAME is required for Docker repository setup'
  local docker_id="$ID"
  [[ "$docker_id" == 'ubuntu' || "$docker_id" == 'debian' ]] || fail "unsupported apt distribution for Docker: $docker_id"

  cat > /etc/apt/sources.list.d/docker.sources <<DOCKER_REPO
Types: deb
URIs: https://download.docker.com/linux/${docker_id}
Suites: ${codename}
Components: stable
Signed-By: /etc/apt/keyrings/docker.asc
DOCKER_REPO

  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin
}

install_dnf_prerequisites() {
  dnf install -y ca-certificates curl git jq sudo tar gzip dnf-plugins-core
  dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
  dnf install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin
}

# shellcheck disable=SC1091
source /etc/os-release
case "${ID:-}" in
  ubuntu|debian)
    command -v apt-get >/dev/null 2>&1 || fail 'apt-get is required'
    install_apt_prerequisites
    ;;
  rhel|centos|rocky|almalinux)
    command -v dnf >/dev/null 2>&1 || fail 'dnf is required'
    install_dnf_prerequisites
    ;;
  *)
    fail "unsupported Linux distribution: ${ID:-unknown}"
    ;;
esac

systemctl enable --now docker

group_name='docker'
getent group "$group_name" >/dev/null 2>&1 || fail 'docker group was not created by Docker installation'
if ! id "$RUNNER_USER" >/dev/null 2>&1; then
  useradd --create-home --shell /bin/bash "$RUNNER_USER"
fi
usermod -aG "$group_name" "$RUNNER_USER"
install -d -m 0750 -o "$RUNNER_USER" -g "$RUNNER_USER" "$RUNNER_HOME"

if [[ "$WITH_RUNNER_BINARY" == 'true' ]]; then
  [[ "$runner_sha" =~ ^[0-9a-f]{64}$ ]] || fail 'runner archive SHA256 must be exactly 64 lowercase hex characters'

  if [[ -e "$RUNNER_HOME/.runner" ]]; then
    fail "runner registration already exists at $RUNNER_HOME; binary replacement is intentionally blocked"
  fi

  if [[ -x "$RUNNER_HOME/bin/Runner.Listener" ]]; then
    installed_version="$(sudo -u "$RUNNER_USER" "$RUNNER_HOME/bin/Runner.Listener" --version 2>/dev/null | tail -n1 | tr -d '\r')"
    if [[ "$installed_version" == "$RUNNER_VERSION" ]]; then
      printf 'Runner binary %s already prepared at %s.\n' "$RUNNER_VERSION" "$RUNNER_HOME"
    else
      fail "runner binary already exists at $RUNNER_HOME (version: ${installed_version:-unknown}); remove or upgrade it explicitly"
    fi
  else
    archive="$(mktemp)"
    trap 'rm -f "$archive"' EXIT
    asset="actions-runner-linux-${runner_arch}-${RUNNER_VERSION}.tar.gz"
    url="https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/${asset}"

    curl -fL --retry 3 --retry-delay 2 "$url" -o "$archive"
    printf '%s  %s\n' "$runner_sha" "$archive" | sha256sum -c -
    tar -xzf "$archive" -C "$RUNNER_HOME"
    chown -R "$RUNNER_USER:$RUNNER_USER" "$RUNNER_HOME"
    "$RUNNER_HOME/bin/installdependencies.sh"
  fi
fi

printf '\nKAORI runner host provisioning complete.\n'
printf 'Next: sudo ops/github-runner/verify-host.sh\n'
if [[ "$WITH_RUNNER_BINARY" != 'true' ]]; then
  printf 'Runner binary preparation was not requested; use --with-runner-binary when needed.\n'
fi

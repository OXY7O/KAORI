#!/usr/bin/env bash
set -euo pipefail

RUNNER_USER="${RUNNER_USER:-github-runner}"
RUNNER_HOME="${RUNNER_HOME:-${RUNNER_DIR:-/opt/actions-runner}}"
DOCKER_SMOKE=false
failures=0

usage() {
  cat <<'USAGE'
Usage: ops/github-runner/verify-host.sh [--docker-smoke]

Read-only validation of the KAORI GitHub Actions runner host substrate.
--docker-smoke additionally runs a disposable hello-world container as the runner user.
USAGE
}

check() {
  local label="$1"
  shift
  if "$@"; then
    printf 'PASS  %s\n' "$label"
  else
    printf 'FAIL  %s\n' "$label" >&2
    failures=$((failures + 1))
  fi
}

while (($#)); do
  case "$1" in
    --docker-smoke)
      DOCKER_SMOKE=true
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'ERROR: unknown argument: %s\n' "$1" >&2
      exit 2
      ;;
  esac
  shift
done

[[ "$(uname -s)" == 'Linux' ]] || {
  printf 'FAIL  Linux host required\n' >&2
  exit 1
}

case "$(uname -m)" in
  x86_64|aarch64|arm64)
    printf 'PASS  supported CPU architecture (%s)\n' "$(uname -m)"
    ;;
  *)
    printf 'FAIL  unsupported CPU architecture (%s)\n' "$(uname -m)" >&2
    failures=$((failures + 1))
    ;;
esac

check 'systemctl available' command -v systemctl
check 'systemd running' test -d /run/systemd/system
check 'curl available' command -v curl
check 'docker CLI available' command -v docker
check 'sudo available' command -v sudo
check 'Docker service active' systemctl is-active --quiet docker
check 'Docker daemon reachable' docker info
check 'Docker Buildx available' docker buildx version
check 'runner user exists' id "$RUNNER_USER"
check 'runner home exists' test -d "$RUNNER_HOME"
check 'runner listener exists' test -x "$RUNNER_HOME/bin/Runner.Listener"
check 'runner configuration entrypoint exists' test -x "$RUNNER_HOME/config.sh"

if id "$RUNNER_USER" >/dev/null 2>&1; then
  if id -nG "$RUNNER_USER" | tr ' ' '\n' | grep -Fxq docker; then
    printf 'PASS  runner user belongs to docker group\n'
  else
    printf 'FAIL  runner user is not in docker group\n' >&2
    failures=$((failures + 1))
  fi
  check 'runner user can reach Docker' sudo -u "$RUNNER_USER" docker info
fi

if [[ -x "$RUNNER_HOME/bin/Runner.Listener" ]]; then
  if runner_version="$(sudo -u "$RUNNER_USER" "$RUNNER_HOME/bin/Runner.Listener" --version 2>/dev/null | tail -n1 | tr -d '\r')" && [[ -n "$runner_version" ]]; then
    printf 'PASS  Runner.Listener version (%s)\n' "$runner_version"
  else
    printf 'FAIL  Runner.Listener version cannot be read\n' >&2
    failures=$((failures + 1))
  fi
fi

check 'GitHub web connectivity' curl -fsSI --connect-timeout 10 --max-time 20 https://github.com
check 'GitHub API connectivity' curl -fsSI --connect-timeout 10 --max-time 20 https://api.github.com

if [[ "$DOCKER_SMOKE" == 'true' ]] && id "$RUNNER_USER" >/dev/null 2>&1; then
  check 'runner-user Docker smoke' sudo -u "$RUNNER_USER" docker run --rm hello-world
fi

if ((failures > 0)); then
  printf '\nKAORI runner host verification failed: %d check(s).\n' "$failures" >&2
  exit 1
fi

printf '\nKAORI runner host verification passed.\n'

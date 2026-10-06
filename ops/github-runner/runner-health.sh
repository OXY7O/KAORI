#!/usr/bin/env bash
set -euo pipefail

RUNNER_USER="${RUNNER_USER:-github-runner}"
RUNNER_HOME="${RUNNER_HOME:-${RUNNER_DIR:-/opt/actions-runner}}"
failures=0

pass() {
  printf 'PASS  %s\n' "$1"
}

fail() {
  printf 'FAIL  %s\n' "$1" >&2
  failures=$((failures + 1))
}

if systemctl is-active --quiet docker; then
  pass 'Docker service active'
else
  fail 'Docker service inactive'
fi

if docker info >/dev/null 2>&1; then
  pass 'Docker daemon reachable'
else
  fail 'Docker daemon unreachable'
fi

if docker buildx version >/dev/null 2>&1; then
  pass 'Docker Buildx available'
else
  fail 'Docker Buildx unavailable'
fi

if id "$RUNNER_USER" >/dev/null 2>&1; then
  pass 'runner user exists'
  if sudo -u "$RUNNER_USER" docker info >/dev/null 2>&1; then
    pass 'runner user can reach Docker'
  else
    fail 'runner user cannot reach Docker'
  fi
else
  fail 'runner user missing'
fi

if [[ -x "$RUNNER_HOME/bin/Runner.Listener" ]]; then
  if version="$(sudo -u "$RUNNER_USER" "$RUNNER_HOME/bin/Runner.Listener" --version 2>/dev/null | tail -n1 | tr -d '\r')" && [[ -n "$version" ]]; then
    pass "Runner.Listener available (${version})"
  else
    fail 'Runner.Listener version unreadable'
  fi
else
  fail 'Runner.Listener missing'
fi

if [[ -s "$RUNNER_HOME/.runner" ]]; then
  pass 'runner registration state present'
else
  fail 'runner registration state missing'
fi

mapfile -t services < <(systemctl list-unit-files 'actions.runner*.service' --type=service --no-legend 2>/dev/null | awk '{print $1}')
if ((${#services[@]} == 0)); then
  fail 'actions.runner service not installed'
else
  active_service=false
  for service in "${services[@]}"; do
    if systemctl is-active --quiet "$service"; then
      pass "actions.runner service active (${service})"
      active_service=true
    fi
  done
  if [[ "$active_service" != 'true' ]]; then
    fail 'no actions.runner service is active'
  fi
fi

if ((failures > 0)); then
  printf '\nKAORI runner health failed: %d check(s).\n' "$failures" >&2
  exit 1
fi

printf '\nKAORI runner health passed.\n'

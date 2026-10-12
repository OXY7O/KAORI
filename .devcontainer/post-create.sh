#!/usr/bin/env bash
set -Eeuo pipefail

cd /workspace/kaori

# Register the bind-mounted workspace without duplicating safe.directory entries.
if ! git config --global --get-all safe.directory | grep -Fxq /workspace/kaori; then
    git config --global --add safe.directory /workspace/kaori
fi

# The Node Dev Container feature supplies npm. Avoid a network-dependent
# global npm upgrade on every container creation; npm ci uses the lockfile.
node --version
npm --version
bash .devcontainer/ensure-frontend.sh

python --version
python -m pip --version
python -m pip check
node --version
npm --version

printf '\nKAORI development container is ready.\n'
printf 'Frontend vendor assets and Tailwind CSS were rebuilt and validated locally.\n'
printf 'Virgin PostgreSQL schema is initialized by the guarded db-first-run service.\n'
printf 'If bootstrap fails, use Database Setup Required Copy Command in the host terminal.\n'
printf 'Press F5 to start Flask with the debugger.\n'

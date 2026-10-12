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
printf 'For a NEW database, use docs/operations/devcontainer-postgres-fresh-bootstrap.md.\n'
printf 'Provision the restricted runtime login before the read-only Setup Required UI preview.\n'
printf 'Alembic/RBAC/admin bootstrap requires a transient KAORI_DB_MIGRATION_URL; do not migrate as the runtime.\n'
printf 'Press F5 after the runtime connection is ready (schema may still be empty).\n'

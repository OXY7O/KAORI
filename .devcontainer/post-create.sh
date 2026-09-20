#!/usr/bin/env bash
set -Eeuo pipefail

cd /workspace/kaori

git config --global --add safe.directory /workspace/kaori

sudo npm install --global npm@10.9.9
npm --version

bash .devcontainer/ensure-frontend.sh --install-always

python --version
python -m pip --version
python -m pip check
node --version
npm --version

printf '\nKAORI development container is ready.\n'
printf 'Frontend vendor assets and Tailwind CSS were rebuilt and validated locally.\n'
printf 'Run "bash scripts/init_db.sh --bootstrap-admin" for the first clean database setup.\n'
printf 'Press F5 to start Flask with the debugger.\n'

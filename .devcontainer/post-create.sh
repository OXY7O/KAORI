#!/bin/bash
set -euo pipefail

cd /workspace/kaori

git config --global --add safe.directory /workspace/kaori

npm ci

python --version
python -m pip --version
python -m pip check
node --version
npm --version

printf '\nKAORI development container is ready.\n'
printf 'Run "bash scripts/init_db.sh --bootstrap-admin" for the first clean database setup.\n'
printf 'Press F5 to start Flask with the debugger.\n'

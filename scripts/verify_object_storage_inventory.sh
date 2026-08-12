#!/usr/bin/env bash
set -euo pipefail

FULL=false
if [[ "${1:-}" == "--all" ]]; then
  FULL=true
fi

printf '[1/6] Ruff\n'
python -m ruff check \
  app/storage_inventory \
  app/models/object_storage.py \
  app/models/__init__.py \
  app/integrations/minio/client.py \
  app/integrations/minio/adapter.py \
  app/bootstrap/blueprints.py \
  scripts/verify_sidebar_navigation_standard.py \
  tests/contracts/storage_inventory \
  tests/storage_inventory

printf '\n[2/6] djLint\n'
python -m djlint \
  app/templates/object_storage_inventory \
  app/templates/components/navigation/object_storage_menu.html \
  app/templates/components/navigation/sidebar.html \
  --check

printf '\n[3/6] Sidebar Navigation Standard\n'
python scripts/verify_sidebar_navigation_standard.py

printf '\n[4/6] Object Storage Inventory Contracts\n'
pytest -q tests/contracts/storage_inventory

printf '\n[5/6] Object Storage Inventory Unit Tests\n'
pytest -q tests/storage_inventory

printf '\n[6/6] Regression Contracts\n'
if [[ "$FULL" == "true" ]]; then
  pytest -q tests/contracts
else
  pytest -q \
    tests/contracts/design/test_sidebar_navigation_standard_contract.py \
    tests/contracts/design/test_kaori_styling_guide_contract.py \
    tests/contracts/integrations
fi

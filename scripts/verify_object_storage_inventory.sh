#!/usr/bin/env bash
set -euo pipefail

FULL=false
if [[ "${1:-}" == "--all" ]]; then
  FULL=true
fi

printf '[1/6] Ruff\n'
python -m ruff check \
  app/storage/object_storage/inventory \
  app/models/object_storage.py \
  app/models/__init__.py \
  app/integrations/storage/object_storage/providers/minio/client.py \
  app/integrations/storage/object_storage/providers/minio/adapter.py \
  app/integrations/storage/object_storage/providers/minio/__init__.py \
  app/platform_operations/jobs/configuration.py \
  app/platform_operations/jobs/definitions/object_storage_inventory_sync.py \
  app/storage/object_storage/inventory/job_adapter.py \
  app/storage/object_storage/inventory/sync_jobs.py \
  app/storage/object_storage/inventory/tasks.py \
  app/access/rbac/defaults.py \
  app/access/rbac/service.py \
  migrations/versions/20260813_object_storage_inventory_jobs.py \
  migrations/versions/20260813_object_storage_bucket_container_contract.py \
  migrations/versions/20260813_object_storage_bucket_enrichment.py \
  migrations/versions/20260813_object_storage_bucket_quota.py \
  migrations/versions/20260813_object_storage_quota_diagnostics.py \
  app/bootstrap/blueprints.py \
  scripts/verify_sidebar_navigation_standard.py \
  tests/contracts/storage/object_storage/inventory \
  tests/storage/object_storage/inventory \
  tests/integrations/test_minio_bucket_enrichment.py

printf '\n[2/6] djLint\n'
python -m djlint \
  app/templates/storage/object_storage/inventory \
  app/templates/components/navigation/object_storage_menu.html \
  app/templates/components/navigation/sidebar.html \
  app/templates/platform_operations/jobs/configuration/definitions/object_storage_inventory_sync.html \
  app/templates/integrations/storage/object_storage/providers/minio/partials/_detail_validation.html \
  app/templates/integrations/storage/object_storage/providers/minio/partials/_detail_runtime.html \
  app/templates/integrations/storage/object_storage/providers/minio/partials/_detail_scope.html \
  --check

printf '\n[3/6] Sidebar Navigation Standard\n'
python scripts/verify_sidebar_navigation_standard.py

printf '\n[4/6] Object Storage Inventory Contracts\n'
pytest -q tests/contracts/storage/object_storage/inventory

printf '\n[5/6] Object Storage Inventory Unit Tests\n'
pytest -q tests/storage/object_storage/inventory tests/integrations/test_minio_bucket_enrichment.py

printf '\n[6/6] Regression Contracts\n'
if [[ "$FULL" == "true" ]]; then
  pytest -q tests/contracts
else
  pytest -q \
    tests/contracts/design/test_sidebar_navigation_standard_contract.py \
    tests/contracts/design/test_kaori_styling_guide_contract.py \
    tests/contracts/integrations
fi

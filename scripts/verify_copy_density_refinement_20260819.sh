#!/usr/bin/env bash
set -euo pipefail

printf '\nKAORI Copy Density Refinement Verification\n'
printf '========================================\n'

printf '\n[1/4] Copy density regression contract\n'
pytest -q tests/contracts/design/test_copy_density_refinement_20260819_contract.py

printf '\n[2/4] Kubernetes Analytics presentation contracts\n'
pytest -q \
  tests/contracts/analytics/test_all_analytics_hero_standard_contract.py \
  tests/contracts/analytics/test_kubernetes_analytics_copy_boundary_20260815_contract.py \
  tests/contracts/analytics/test_kubernetes_analytics_final_lock_v2_20260813_contract.py

printf '\n[3/4] MinIO and Metrics Source boundary contracts\n'
pytest -q \
  tests/contracts/integrations/test_minio_object_storage_provider_contract.py \
  tests/contracts/integrations/test_minio_provider_workspace_alignment_contract.py \
  tests/contracts/integrations/test_metrics_source_identity_validation_contract.py \
  tests/contracts/integrations/test_metrics_source_detail_configuration_validation_v2_contract.py

printf '\n[4/4] PASS — copy density refinement verified.\n'

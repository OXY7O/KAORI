#!/usr/bin/env bash
set -euo pipefail

mode="${1:-targeted}"

printf '\n[1/5] Ruff\n'
python -m ruff check .

printf '\n[2/5] djLint + Integrations Title Case\n'
python -m djlint app/templates --check
python scripts/verify_integrations_title_case.py

printf '\n[3/5] Provider workspace contracts\n'
pytest -q \
  tests/contracts/integrations/test_provider_workspace_alignment_20260812_contract.py \
  tests/contracts/integrations/test_provider_workspace_followup_20260812_contract.py \
  tests/contracts/integrations/test_provider_workspace_followup_v2_20260812_contract.py \
  tests/contracts/integrations/test_provider_workspace_followup_v3_20260812_contract.py \
  tests/contracts/integrations/test_provider_workspace_followup_v4_20260812_contract.py \
  tests/integrations/test_minio_compatibility_profiles.py \
  tests/integrations/test_kubernetes_readiness_messages.py \
  tests/contracts/integrations/test_kubernetes_integration_v2_contract.py \
  tests/contracts/integrations/test_minio_provider_workspace_alignment_contract.py \
  tests/contracts/integrations/test_integration_domain_ui_refinement_contract.py

if [[ "$mode" == "--all" || "$mode" == "all" ]]; then
  printf '\n[4/5] Full contract suite\n'
  pytest -q tests/contracts
else
  printf '\n[4/5] Full contract suite skipped (run with --all to include it)\n'
fi

printf '\n[5/5] Provider workspace alignment verification passed.\n'

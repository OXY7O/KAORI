#!/usr/bin/env bash
set -euo pipefail

mode="${1:-targeted}"

printf '\n[1/4] Ruff\n'
python -m ruff check .

printf '\n[2/4] djLint\n'
python -m djlint app/templates --check

printf '\n[3/4] Provider workspace contracts\n'
pytest -q \
  tests/contracts/integrations/test_provider_workspace_alignment_20260812_contract.py \
  tests/contracts/integrations/test_kubernetes_integration_v2_contract.py \
  tests/contracts/integrations/test_minio_provider_workspace_alignment_contract.py \
  tests/contracts/integrations/test_integration_domain_ui_refinement_contract.py

if [[ "$mode" == "--all" || "$mode" == "all" ]]; then
  printf '\n[4/4] Full contract suite\n'
  pytest -q tests/contracts
else
  printf '\n[4/4] Full contract suite skipped (run with --all to include it)\n'
fi

printf '\nKAORI provider workspace alignment verification passed.\n'

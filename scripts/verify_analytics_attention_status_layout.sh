#!/usr/bin/env bash
set -euo pipefail

printf '\n[1/3] Analytics attention-strip layout contract\n'
pytest -q tests/contracts/analytics/test_overview_semantic_visual_hierarchy_contract.py

printf '\n[2/3] Analytics final-lock verification\n'
python scripts/verify_analytics_final_lock.py

printf '\n[3/3] Analytics attention status layout verification passed.\n'

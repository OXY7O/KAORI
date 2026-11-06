#!/usr/bin/env bash
# Read-only branch ruleset inventory for #4216. Requires authenticated gh CLI.
# Usage: bash scripts/audit_branch_rulesets.sh [owner/repository ...]
# Prints no tokens, bypass actor identities, or organization security settings.
set -euo pipefail

if ! command -v gh >/dev/null 2>&1; then
  echo "ERROR: gh CLI is required" >&2
  exit 2
fi

if (( "$#" == 0 )); then
  set -- OXY7O/KAORI OXY7O/kaori-website OXY7O/kaori-docs
fi

failed=0
for repo in "$@"; do
  if [[ ! "$repo" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]]; then
    echo "ERROR: invalid owner/repository argument" >&2
    exit 2
  fi

  printf '\n=== %s ===\n' "$repo"
  # These commands enumerate configured/effective rules; they do not test
  # legacy protection, bypass actors, required checks or negative push cases.
  if ! gh ruleset list --repo "$repo"; then
    echo "UNKNOWN: ruleset inventory failed; check auth and repository access" >&2
    failed=1
    continue
  fi
  for branch in main kaori/staging; do
    printf '\n--- %s ---\n' "$branch"
    if ! gh ruleset check "$branch" --repo "$repo"; then
      echo "UNKNOWN: effective ruleset lookup failed; do not claim protection" >&2
      failed=1
    fi
  done
done

if (( failed )); then
  echo "INCOMPLETE: one or more read-only lookups failed" >&2
  exit 1
fi
echo "INVENTORY COMPLETE: manual legacy protection, required-check and negative tests remain pending"

#!/usr/bin/env bash
# Offline regression for read-only ruleset inventory (#4216).
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/bin"
cat > "$tmp/bin/gh" <<'MOCK'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$GH_AUDIT_CALLS"
if [[ "${GH_AUDIT_FAIL:-}" == "list" && "$1 $2" == "ruleset list" ]]; then exit 1; fi
if [[ "${GH_AUDIT_FAIL:-}" == "check" && "$1 $2" == "ruleset check" ]]; then exit 1; fi
printf 'mock rule\n'
MOCK
chmod +x "$tmp/bin/gh"
export PATH="$tmp/bin:$PATH" GH_AUDIT_CALLS="$tmp/calls"
: > "$GH_AUDIT_CALLS"
bash "$root/scripts/audit_branch_rulesets.sh" OXY7O/KAORI > "$tmp/success"
grep -q 'INVENTORY COMPLETE' "$tmp/success"
[[ "$(wc -l < "$GH_AUDIT_CALLS")" -eq 3 ]]
grep -q '^ruleset list --repo OXY7O/KAORI$' "$GH_AUDIT_CALLS"
grep -q '^ruleset check main --repo OXY7O/KAORI$' "$GH_AUDIT_CALLS"
grep -q '^ruleset check kaori/staging --repo OXY7O/KAORI$' "$GH_AUDIT_CALLS"

: > "$GH_AUDIT_CALLS"
if bash "$root/scripts/audit_branch_rulesets.sh" OXY7O/KAORI invalid-repo > "$tmp/invalid" 2>&1; then
  echo 'FAIL: invalid argument accepted' >&2; exit 1
fi
grep -q 'invalid owner/repository argument' "$tmp/invalid"
[[ ! -s "$GH_AUDIT_CALLS" ]] || { echo 'FAIL: partial inventory ran before validation' >&2; exit 1; }

: > "$GH_AUDIT_CALLS"
if GH_AUDIT_FAIL=list bash "$root/scripts/audit_branch_rulesets.sh" OXY7O/KAORI > "$tmp/list-fail" 2>&1; then
  echo 'FAIL: list failure accepted' >&2; exit 1
fi
grep -q 'INCOMPLETE' "$tmp/list-fail"

: > "$GH_AUDIT_CALLS"
if GH_AUDIT_FAIL=check bash "$root/scripts/audit_branch_rulesets.sh" OXY7O/KAORI > "$tmp/check-fail" 2>&1; then
  echo 'FAIL: check failure accepted' >&2; exit 1
fi
grep -q 'INCOMPLETE' "$tmp/check-fail"
echo 'PASS: ruleset audit offline contract (success, invalid input, list/check failure)'

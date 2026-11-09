# Disposable negative main promotion source test — #4304

This file exists ONLY on the deliberately unauthorized issue-linked test branch.
The test PR targets `main` from `kaori/chore-4304-negative-main-route-20261109`, which MUST be rejected by the existing
`Full Admission / CI Admission` pre-checkout route guard because the sole
authorized PR source for `main` is the same-repository `kaori/staging` branch.

Expected:
- `Resolve Profile`: SKIPPED (invalid branch/source route).
- `CI Admission`: explicitly FAILURE, not SKIPPED.
- No untrusted source checkout or privileged validation/deployment.
- The test PR is CLOSED UNMERGED and the probe file never reaches main.

This is NOT a security vulnerability report, release, approval, or planned
shipping documentation. It contains no tokens, secrets, private endpoints, or
provider mutation commands. Delete the disposable branch after safe review.

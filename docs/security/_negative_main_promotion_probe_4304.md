# Disposable negative Draft main promotion CI Admission probe — #4304

This is a **non-shipping, non-executable** source identity probe for the existing
KAORI main promotion required-check safeguard. It belongs only to
`kaori/test-4304-draft-main-denial-20261119`, based on the already-existing
`main` source; it MUST NEVER merge into `main`, `kaori/staging`, or an RC.

## Expected negative evidence

- Open a **Draft** PR targeting `main` from this same-repository non-staging branch.
- GitHub Actions `Full Admission` starts because the workflow observes `pull_request.opened`.
- `Resolve Profile` is SKIPPED because this PR is Draft and not from `kaori/staging`.
- The existing hosted **CI Admission** (`if: always()`) executes its first
  pre-checkout guard and concludes **FAILURE**, not SKIPPED or SUCCESS.
- The downstream Full Admission matrix and Fast Smoke remain SKIPPED; there is
  no untrusted source checkout, release, deployment, secret access, or provider mutation.
- Record the exact job/run identity in #4304, then CLOSE the probe PR **UNMERGED**.

This file contains no production configuration, runnable code, credentials, or
security findings; it is not a main promotion or a request for approval.

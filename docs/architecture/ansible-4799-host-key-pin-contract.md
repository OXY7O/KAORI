# #4799 — Exact known_hosts key pin contract (review-only)

This bounded module validates an **already independently approved** SSH
`ssh-ed25519` public key against a canonical SHA-256 fingerprint and one exact
asset hostname. It parses the SSH public-key wire format, rejects malformed
or trailing bytes and enforces canonical Base64. Host aliases, markers, hashed
known_hosts entries, wildcards, comments and certificates are deliberately
unsupported in this first narrow contract.

## Trust boundary

- The hostname and expected fingerprint must be retrieved from a protected,
  independently approved canonical asset/SSH host-key authority. **Never**
  populate them from browser input, SSH keyscan, Ansible output or the
  candidate known_hosts line itself.
- This predicate is **not** proof that a protected authority was consulted.
  It cannot turn a self-declared key into trusted host identity.
- Dedicated queue-isolated worker admission must bind the asset, source Git
  SHA, signed EE digest, protected credential reference, exact target lock and
  latest canonical JobExecution before any read-only remote contact.
- This module performs no network I/O, SSH, credential resolution, worker
  dispatch, Ansible execution or Kubernetes mutation. #4800 Plan remains
  review-only; #4801 and lifecycle Run stay blocked.
- Existing stacked Draft PRs #4905/#4907/#4908/#4909/#4911/#4914/#4915/
  #4919 must be reconciled separately. Do not infer their mergeability from
  this independent review candidate.

## Verification and admission

Run `python -m ruff check` and `python -m ruff format --check` on the
module and focused test, then
`python -m pytest -q -p no:cacheprovider tests/contracts/integrations/test_ansible_host_key_pin_contract.py`.
Run relevant existing integration/JobExecution regressions, Pyright and
UI verifiers before review-branch integration. GitHub content commits alone
are **not** executed checks, CI or real-host UAT. Human Acceptance pending.

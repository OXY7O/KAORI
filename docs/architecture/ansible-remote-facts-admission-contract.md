# #4799 — Remote facts admission predicate (review-only)

This issue-scoped increment introduces a **pure source-only predicate** for
authority-bound remote facts candidates. It does not register a provider,
create a JobExecution, fetch a credential, establish SSH trust, or dispatch
ansible-runner. A positive predicate result means **qualified for review only**,
never approved for execution.

## Authority and trust boundary

The candidate carries asset and target identifiers, the SHA-256-format SSH
host-key fingerprint, a protected-secret **reference**, exact Git SHA, and EE
digest. Independently obtained authority fields must match the asset, target,
fingerprint, and credential reference exactly. Explicit source review, EE
signature verification, credential scope and SSH trust evidence must all be
true. The predicate cannot establish the authenticity of those fields by
itself: caller must obtain them from canonical asset/credential/source/worker
authorities, not a browser request, remote host, or a worker's self-declaration.

Never log or persist secret material. The credential reference format is a
structural guard, **not** proof of secret-manager admission. SSH host-key
fingerprint equality is not trust-on-first-use or a known_hosts implementation.
A worker must independently verify the actual negotiated key against an
authorized pinned known_hosts record before any read-only SSH contact.
Unknown or changed keys fail closed; no StrictHostKeyChecking bypass.

## Integration sequencing

1. Reconcile dependent Draft #4905/#4907/#4908; run exact-branch gates.
2. Resolve approved asset registry, canonical IntegrationBinding, secret
   reference authority and signed/pinned EE source. Keep #2/#6 in
   kaori-operations nonexecutable until reviewed and admitted.
3. Add dedicated non-mutating worker route, immutable inventory target lock,
   host-key verification and sanitized JobExecution evidence in a separately
   reviewed slice. No Flask-request runner, generic playbook console or
   new JobExecution/Cluster/credential model.
4. #4800 Plan review remains non-executable. Independent maker/checker/window
   and authorized disposable nonprod target are required before #4801.

## Verification and status

Focused contract: `python -m pytest -q -p no:cacheprovider tests/contracts/integrations/test_ansible_remote_admission_contract.py`.
Run `python -m ruff check` and `python -m ruff format --check` on both
Python files; then relevant Ansible/JobExecution regressions, pyright and UI
reuse/style verifiers where applicable. This connector-created increment has
**not** run Ruff, pytest, pyright, CI or real host UAT. Do not promote without
independent source review and executed gates. Human Acceptance remains pending.

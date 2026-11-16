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

## Strict admission input boundary

The review-only predicate rejects non-string authority identity fields, Unicode
category-C asset identifiers (including zero-width and bidi controls), and
truthy non-boolean values masquerading as independent approval evidence.
Invalid input returns a rejection, not a worker permit or an exception.
Canonical asset, trusted host-key, protected credential, source review and
signed EE authorities must still supply independent evidence. No dispatch,
SSH connection, secret retrieval or Kubernetes mutation is enabled.

Focused regression:
`python -m pytest -q -p no:cacheprovider tests/contracts/integrations/test_ansible_remote_admission_contract.py`.
Ruff, pytest, pyright, CI and UAT have **not been run** for this connector
increment. Reconcile #4905–#4909 and run checks before review-branch promotion.

## Canonical identity and locator hardening (dependent increment)

Remote target identifiers now use the same bounded, whitespace-free,
Unicode-category-C-free, NFC-normalized check as asset identifiers. A caller
cannot manufacture a separate authority target with invisible controls or an
oversized identifier. Secret references reject empty, dot and parent-directory
segments even when their outer syntax matches. Host-key fingerprints must
encode a valid 32-byte SHA-256 digest; they remain **untrusted** until an
independent approved known_hosts authority verifies the actual SSH key.

These are pure admission-input checks only. They do not implement registry
lookup, credential retrieval, SSH transport, host-facts collection, approval,
or a dispatch permit. The predicate's synthetic positive test is not evidence
of real host trust. Focused Ruff/format/pytest and source review are required
before temporary holding-branch integration. CI, real worker execution,
provider UAT and Human Acceptance are not established by these commits.

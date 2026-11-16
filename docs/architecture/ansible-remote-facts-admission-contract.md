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


## Canonical SSH SHA-256 fingerprint representation (#4799)

The candidate fingerprint now requires exactly 43 unpadded RFC 4648 Base64
characters after `SHA256:`. Decode must yield 32 bytes and round-trip to
the identical unpadded encoding. Padding, alternate pad-bit encodings and
non-Base64 characters fail closed before comparison to the approved host-key
fingerprint. This prevents multiple textual representations of one key from
passing an exact-match authority boundary.

**This is not host-key trust establishment.** A fingerprint supplied by a
browser or by the candidate worker is never independent verification. A
future dedicated, non-mutating worker must obtain the canonical pinned key
from approved host-key authority, verify the SSH handshake with strict
known_hosts enforcement, and bind its JobExecution to the authorized asset,
credential reference, exact Git source and signed EE. No SSH connection,
credential resolution, or execution permission is introduced here.

Review commands (not executed in this connector-only increment):

```sh
python -m ruff check app/integrations/orchestration/configuration_automation/providers/ansible/remote_admission.py tests/contracts/integrations/test_ansible_remote_admission_contract.py
python -m ruff format --check app/integrations/orchestration/configuration_automation/providers/ansible/remote_admission.py tests/contracts/integrations/test_ansible_remote_admission_contract.py
python -m pytest -q -p no:cacheprovider tests/contracts/integrations/test_ansible_remote_admission_contract.py
```

Continue existing Pyright, integration regressions, UI reuse verifiers and
Developer Check against the reconciled dependent PR stack before holding-branch
promotion. No CI, real host UAT, source/EE approval or Human Acceptance is
asserted.

## Exact source and EE authority binding (issue #4799)

The review-only admission predicate now compares `source_sha` and `ee_digest` with separately supplied `authorized_source_sha` and `authorized_ee_digest`, in addition to validating the immutable Git SHA and `sha256:` image digest syntax. Boolean `source_reviewed` / `ee_signature_verified` flags alone cannot qualify a different source revision or EE image. The authorized values **must** be populated by trusted, independently verified canonical source/EE admission services, never copied from the caller's request. Equality of caller-supplied values does not establish independent provenance or a worker execution permit.

Negative contracts cover candidate drift, authority drift, malformed authority types and existing source/EE format checks. This remains a pure predicate: no SSH, secret resolution, worker dispatch or cluster mutation. The stacked Draft PR requires reconciliation with current `kaori/review/staging-uat` and actual Ruff, pytest, Pyright, CI and real-host UAT before admission; no tests or UAT are asserted passed by this document.

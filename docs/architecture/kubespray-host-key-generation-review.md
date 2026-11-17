# #4799 — SSH host-key generation coherence (review-only)

This narrow pure predicate compares **independently obtained** expected and observed records for exact asset, inventory fingerprint, trusted known-hosts reference, host-key generation and fingerprint. Any rotation, revocation, malformed record, secret-bearing extra field, or drift returns `blocked`. Equality returns `requires_independent_admission`, **never Run**.

It does **not** establish that a reference came from a trusted signed inventory, that the host key was authenticated, or that a credential authority issued a protected locator. It must not be used to bypass the canonical JobExecution/IntegrationBinding/Cluster/Activity Audit, dedicated remote-facts worker, source/EE qualification, maker/checker or change window. No SSH/Ansible/Kubernetes call is implemented.

Dependency: reconcile Draft #4905–#4934, including canonical inventory membership and host-key syntax, before integration. Review source OXY7O/kaori-operations Draft #2/#6 separately; neither is executable/admitted.

Run on the **exact candidate SHA**: `python -m ruff check app/platform_operations/host_key_generation_review.py tests/unit/platform_operations/test_host_key_generation_review.py`, `python -m ruff format --check ...` on the same paths, `python -m pytest -q -p no:cacheprovider tests/unit/platform_operations/test_host_key_generation_review.py`, Pyright and relevant `verify_*` gates. Developer Check, Full Admission, authenticated visual/real-host UAT and Human Acceptance are **NOT RUN** here. #4799 and #4800 remain open; no promotion or execution permission.

## Canonical evidence object boundary

Review accepts only exact built-in `dict` records representing already decoded, independently supplied JSON objects. Custom `Mapping` implementations and `dict` subclasses are rejected *before* iteration or field access: an attacker-controlled mapping can override iteration, lookup, or length with side effects or exceptions. The record must contain exactly the six allowed fields (five identity fields and `revoked`); unknown, missing or secret-bearing fields remain blocked. This is deliberately narrower than a general-purpose mapping API and does not authenticate the evidence producer. Upstream serializers must normalize and authenticate their own inputs before invoking the review predicate; never coerce untrusted mappings here.

The follow-up regression suite covers hostile `Mapping` callbacks, overridden `dict` lookup, non-mapping payloads and existing rotation/revocation cases. It must be executed on the exact candidate SHA; GitHub source readback alone is not a test pass. This change is stacked on Draft #4935 and must be reconciled with #4905–#4934 before any integration. No Run permission or remote operation is introduced.

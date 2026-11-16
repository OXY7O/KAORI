# #4799 — Protected credential authority identity evidence (review-only)

This bounded, pure predicate checks the *identity binding* of a credential authority's projected decision to a canonical asset, JobExecution public ID, exact Git source SHA, immutable EE digest, and opaque protected credential locator. It never reads or resolves the referenced secret. It does not dispatch Celery work or initiate SSH.

## Authority and trust boundaries

The calling integration must obtain the record from a separately authenticated and authorized secret authority; a browser request, worker self-attestation, or untrusted Ansible event cannot be the evidence source. A syntactically valid `secretref:` locator does **not** establish that the reference exists or that the caller may use it. Exact matching and positive, non-revoked flags are necessary but insufficient. A successful projection returns only `requires_independent_admission` with `execution_authorized=False`.

The eventual adapter must verify secret authority issuer, credential access policy, credential lifecycle/revocation, canonical asset ownership, independently pinned SSH host key, signed source and EE provenance, queue-isolated non-mutating worker identity, canonical JobExecution attempt freshness and Activity Audit before scheduling any facts read. Do not persist raw secret bytes in JobExecution, events, logs or Celery arguments. Failure, unknown, drift or revoked state must block.

## Verification and admission

Focused regression contract: `tests/contracts/integrations/test_remote_facts_credential_authority_contract.py`. The tests cover exact-match review state, source/job/asset drift, revoked/incorrect boolean flags, malformed evidence and secret-bearing fields. Ruff, pytest, Pyright, CI and real-host UAT have **not** been executed for this candidate; this document is not verification evidence.

This is an independent #4799 review-only slice. Reconcile with stacked Draft PRs #4905–#4928 and approved #556/#4796 boundaries before integration. #4800 Plan remains review-only; #4801 provisioning and all SSH/Kubernetes mutations remain blocked. Temporary holding-branch integration requires source review; official staging/main requires Developer Check, Full Admission, real-host UAT and Human Acceptance.

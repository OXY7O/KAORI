# Remote facts event batch review (#4799)

This issue-scoped, **non-executable** candidate extends the draft allowlisted event projection in PR #4928. It does not change merged preflight #4899, immutable Plan #4906, or Plan currentness #4917.

## Boundary

The pure batch reviewer accepts at most 64 runner events and projects only `(host, task, status)` from the existing allowlisted projector. Exactly one successful setup/gather_facts event for the expected host is reviewable. Empty, oversized, malformed, mixed success/failure, unreachable, foreign-host, unknown-task and duplicate-success batches fail closed. No raw stdout, ansible_facts, environment or credential material is persisted by this function. A reviewable batch **never** grants execution permission.

This intentionally conservative single-event contract is not a complete Ansible-runner lifecycle state machine. The authoritative worker must independently bind the result to the canonical JobExecution attempt, trusted asset identity, SSH host key, credential authority, immutable signed source/EE and worker route. Runner completion, latest-attempt semantics and real host readback remain separate prerequisites.

## Verification and admission

Regression cases are committed in `tests/integrations/test_remote_facts_event_batch.py`. Execute Ruff, Ruff Format, pytest, Pyright and relevant verify gates on the exact combined candidate; **not executed by this connector session**. Review dependency PR #4928 before integration. No SSH/Ansible/Kubernetes execution, source repository admission, UAT, staging/main promotion or Human Acceptance is implied.

Open dependencies: #4799 canonical asset/host-key and protected credential authority; dedicated non-mutating worker; independent signed source/EE; #4800 maker/checker/window; #4801 disposable nonprod authorization and independent Kubernetes API readback. Operations source Draft PRs #2/#6 remain nonexecutable until admitted.

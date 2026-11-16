# Remote facts worker isolation — #4799 review contract

Authority: #556 → #4796 → #4799. This document describes a **pure configuration gate**; it is not a deployed Celery worker or execution authorization.

## Scope

`app/integrations/ansible/remote_facts_worker_isolation.py` rejects configurations without the exact dedicated `automation-remote-facts` queue, dedicated worker role, sole `linux_facts_readonly` operation, no mutation/shell/privilege escalation, protected worker credential references, immutable source and EE pins, and authorized-host-only network scope. Unknown fields and type coercion fail closed. The successful outcome is `requires_independent_admission`, always `execution_authorized=False`.

## Required authority before any real dispatch

- Reconcile concurrent #4799 PRs (#4905/#4907/#4908/#4909/#4911/#4914/#4915/#4919/#4923/#4924/#4925/#4926) against the holding branch; do not infer merged or tested state.
- Independently attest canonical asset identity, approved SSH host-key pin, protected credential locator and its resolution policy, exact signed Git source and EE digest.
- Enforce queue routing and isolation in **actual** Celery deployment, restrict outbound network access, prohibit arbitrary playbook/command invocation, and persist canonical JobExecution and Activity Audit evidence.
- Verify runner execution and sanitized read-only facts against an explicitly authorized disposable host; ambiguous, stale or failed attempts must not become Ready.
- #4800 Plan is review-only, never Run approval. #4801 and all lifecycle mutation remain blocked pending independent maker/checker, window, target lock, trusted execution source and Kubernetes API postcondition readback.

## Verification

Issue-scoped regression test: `python -m pytest -q tests/integrations/test_remote_facts_worker_isolation_contract.py`. Also run Ruff, Ruff Format, Pyright and existing integration/JobExecution regression gates in the project Dev Container. **Not executed in this connector-only authoring environment.** No CI, real-host UAT, Developer Check, Full Admission or Human Acceptance claim. Project custom fields require manual verification.

No SSH, Ansible, Kubernetes mutation, credential resolution, or worker dispatch is introduced by this slice.

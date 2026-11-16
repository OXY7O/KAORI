# #4799 Remote facts latest-attempt selection — review-only

## Scope and dependency

This pure selector is stacked on Draft PR #4925 (exact JobExecution envelope).
It prevents replay of a successful remote-facts observation when the canonical
JobExecution contains a newer attempt that is failed, queued, running, cancelled
or unknown. The selector sorts by the persisted attempt number, not client or
worker-provided ordering. Duplicate identifiers, duplicate sequence numbers,
foreign jobs and malformed records are blocked.

The caller must read the complete bounded attempt history and the expected
attempt identifier from the canonical JobExecution persistence layer under
the same consistent snapshot. A caller-supplied list is not an authority.
Pagination gaps or a stale snapshot must fail closed. This contract is not
wired to a dispatch route and does not prove a trusted host or worker.

## Integration boundary

After canonical latest-attempt selection, #4925's exact attempt envelope and
#4924's remote facts projection must be reconciled against independently
approved asset identity, SSH host-key authority, protected credential locator,
source Git SHA, signed EE digest and immutable inventory. Do not promote a
review-only result to execution permission. No SSH, runner, Celery dispatch,
Kubernetes API mutation or arbitrary playbook console is introduced here.

## Verification and admission hold

Positive and negative pytest contracts are committed for ordering, replay,
duplicate identities, foreign job and malformed attempts. Local Ruff, pytest,
Pyright, CI, visual UAT and real-host UAT are **not executed** by this connector
run. The stacked #4799 Draft PRs require dependency reconciliation and quality
gates before temporary holding merge. #4800 remains OPEN; #4801 mutation and
official staging/main remain blocked pending independent approvals, change
window, source/EE trust and real postcondition verification.

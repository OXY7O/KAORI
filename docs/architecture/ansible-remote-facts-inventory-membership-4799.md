# #4799 — Exact committed inventory membership candidate (review only)

This pure validator pairs an exact canonical asset ID with a single committed
inventory alias. It rejects missing assets, cross-asset aliases, case-insensitive
duplicate alias ownership, malformed membership records, group selectors, and
literal IP destinations. It composes the existing immutable setup-only selector
contract from Draft #4933 instead of reimplementing it.

**Trust boundary:** The supplied mapping is caller-provided candidate data, not
proof of committed or approved inventory. The independent worker must verify
the immutable Git SHA, trusted signed source and EE, canonical asset registry
identity, SSH host-key reference, protected credential authority, exact target
lock and latest JobExecution attempt against trusted backends. A matching alias
is only review evidence: never SSH permission, Plan admission or Run permission.

Focused verification (not yet executed):
`python -m ruff check app/infrastructure_automation/remote_facts_inventory_membership.py tests/unit/infrastructure_automation/test_remote_facts_inventory_membership.py`
`python -m ruff format --check app/infrastructure_automation/remote_facts_inventory_membership.py tests/unit/infrastructure_automation/test_remote_facts_inventory_membership.py`
`python -m pytest -q tests/unit/infrastructure_automation/test_remote_facts_inventory_membership.py tests/unit/infrastructure_automation/test_remote_facts_command.py`

Review stacked Draft PRs #4905–#4933 for duplicate authority logic before
integration. #4899, #4906 and #4917 are already in temporary holding and are
not to be recreated. OXY7O/kaori-operations Draft #2/#6 remain non-executable.
No worker dispatch, SSH, Ansible, Kubernetes changes or infrastructure access.
#4799/#4800 remain OPEN; #4801 and subsequent mutation operations stay HOLD.
Official staging/main requires Developer Check, Full Admission, real-host UAT
and Human Acceptance. Connector writes do not establish CI PASS.

# #4799 — Fixed remote facts command boundary (review-only)

Authority: approved Ansible foundation #556, lifecycle contract #4796, read-only worker #4799. This is **not** #4800 Plan admission and does not authorize #4801 provisioning.

`app/infrastructure_automation/remote_facts_command.py` supplies an immutable, narrowly fixed Ansible `setup` module specification for an independently authorized existing Linux inventory host. It accepts only a canonical inventory alias, with no shell, playbook selection, extra-vars, privilege escalation, wildcard host patterns, caller-controlled module arguments, or arbitrary command execution. Single fork, 30-second module timeout, and check mode are defensive defaults, **not** a proof that a host operation is harmless.

This module does not execute Ansible, resolve DNS, construct inventory, read credentials, retrieve host keys, enqueue Celery, or persist JobExecution. It does not assert any independent authority. A dedicated isolated worker must separately bind the exact IntegrationBinding, canonical asset, immutable Git source SHA, signed EE digest, protected credential reference, trusted SSH known_hosts reference and approved non-mutating target before any SSH. The worker must enforce command semantics and runtime isolation, verify the latest JobExecution attempt and sanitize evidence. Never derive these authorities from browser or Runner self-assertions.

## Selector hardening follow-up

Ansible's implicit `all` and `ungrouped` inventory groups (including case variants) must not be interpreted as one authorized host. IPv4 literals are also rejected: an IP address cannot substitute for the canonical inventory asset alias and trusted asset-to-host mapping. Explicit aliases such as `all-nodes` remain valid because they must be resolved against a separately approved inventory. This is a **syntactic denial boundary only**: the module still does not prove that an alias is unique, committed, or authorized. A future worker must independently enforce exact inventory membership, canonical asset identity and target lock before dispatch.

## Verification and promotion hold

Focused command: `python -m pytest -q tests/unit/infrastructure_automation/test_remote_facts_command.py`. Also run Ruff check/format, Pyright, applicable contracts, Developer Check and Full Admission on the exact integrated SHA. Connector-only source writes are **not** executed QA evidence. Review the stacked #4905–#4931 candidates for overlap before merging this PR. Existing #4899/#4906/#4917 are already in temporary holding and must not be recreated.

No worker dispatch, SSH, Ansible or Kubernetes mutation is permitted by this change. No claim of CI PASS, real-host UAT, approved Plan, or Human Acceptance. #4799/#4800 remain open; #4801/#4802/#4895/#4896/#4897 stay blocked. Source OXY7O/kaori-operations Draft #2/#6 remain unmerged and non-executable. Official staging/main promotion requires the existing gates and human approval.

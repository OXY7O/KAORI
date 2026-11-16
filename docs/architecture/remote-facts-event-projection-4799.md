# #4799 — Read-only remote facts event projection

This review-only slice introduces a strict metadata projection for native `ansible-runner` facts events. It intentionally discards all raw event results, stdout, environment, credentials, and `ansible_facts` to avoid accidental persistence of secrets through canonical JobExecution or Activity Audit.

The allowlist accepts only `runner_on_ok`, `runner_on_failed`, and `runner_on_unreachable` for `setup`/`gather_facts`, with an exact ASCII host identifier. A successful projection is **not** proof of SSH host-key trust, protected credential authority, signed Git/EE provenance, worker isolation, or host facts correctness. Unknown events fail closed. A failure/unreachable outcome remains explicitly non-successful.

Integration hold: connect this projection only after the #4799 worker is independently admitted, canonical JobExecution/IntegrationBinding identities are checked, and authority-backed host/credential/source verification is present. This is not a runner dispatcher, a replacement for native facts, or a mutation permission.

Verification required on exact PR HEAD: Ruff, Ruff format, pytest for `tests/integrations/test_remote_facts_event_projection.py`, Pyright and the existing admission gates. Real-host UAT and Human Acceptance remain pending. No SSH/Ansible/Kubernetes execution was performed by this slice.

# Kubernetes Lifecycle inventory/Plan binding — non-mutating evidence contract

Authority: #5163 under #5155 and #4800. Related #5161 canonical host persistence, #5162 SSH credential/host-key reference, #5156 execution compatibility, #556 Ansible foundation and #4796 architecture.

The new pure `inventory_plan_binding.py` verifies a **sanitized review snapshot contract** across an exact Ansible connection, source SHA, Execution Environment image digest, three-host pre-provision inventory reference, access-reference state and canonical Kubespray Plan summary. All inputs must originate from authorized KAORI committed state, never HTTP-submitted inventory or secret values. It allows only the established statuses `review_only` and `references_recorded` plus a review Plan with `approval_status=not_requested`, `execution_status=blocked`, and `mutation_authorized=false`.

A matching state returns **review_material_only**, not execution approval. The output contains only a deterministic correlation fingerprint and expiry; it contains no addresses, hostnames, SSH credential paths, private key material, or approval token. Host-access fingerprint changes, wrong inventory/source/EE, stale/expired Plan, any claim of approval or mutation all invalidate the projection. SHA-256 is not a signed attestation and cannot be used as a Run token.

This first slice intentionally **does not** persist a JobExecution, write a new database table, rewire the established `plan_dispatch.py` or query an external Ansible/Kubernetes provider. Binding to an actual canonical Plan generation must wait for source-of-truth #5161 persistence, #5162 credential trust, independent remote worker evidence #4799/#5066 and #4800 exact latest-attempt currentness. Until those are admitted, an operational page must continue showing independent admission missing; no new provisioning button should be activated.

Validation: Ruff/format, Pyright, focused pytest, Developer Check, Full Admission and independent reviewer on exact commit. Future staged hosted UAT requires real non-production target and human acceptance. No direct main, provider mutation or production SSH.

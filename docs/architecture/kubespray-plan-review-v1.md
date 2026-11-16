# Kubespray Plan Review — canonical JobExecution evidence contract v1

Authority: #556 → #4796 → #4799 → #4800. Provisioning #4801 is a separate infrastructure-mutation authority. Source-first review profile: `kubernetes-sigs/kubespray` v2.32.0 pinned commit. This implementation is review-only and **not approved to execute a Kubernetes run**.

## Flow and ownership

1. The operator views the existing Ansible connection's committed source and the latest trusted remote-host preflight in Validation & Capabilities. Normal page rendering does not call SSH, Git providers or Kubernetes.
2. `Generate Review-only Plan` is visible but disabled until all eight non-mutating gates are qualified and the actor has both `integrations.manage` and `jobs.execute`. The server independently repeats permission, CSRF, source, current preflight and worker validation. No host address, password, private key, extra-vars, playbook name or inventory text is accepted from the form.
3. The canonical `enqueue_canonical_job` dispatcher records one connection-scoped JobExecution (`automation_kubespray_plan_review`, `automation` queue, `max_attempts=1`) and requires a live worker advertising the exact task. Only the integer connection ID and integer preflight job ID cross Celery; the worker fetches source and evidence from committed KAORI state.
4. A pure policy builds a Plan candidate from the exact pinned source and upstream Kubespray release, the current qualified preflight job, authorized non-production environment and three bounded Linux host observations. It reuses the existing static Kubespray Plan validator; no new asset/provider registry is created.
5. The Plan fingerprint hashes normalized repository/commit, connection identity/environment, pinned Kubespray version, deterministic inventory fingerprint, canonical preflight JobExecution ID, evidence timestamp and expiry. The canonical Plan JobExecution stores only fingerprint, source SHA, upstream SHA, preflight job reference, expiry and explicit `approval_status=not_requested`, `execution_status=blocked`, `mutation_authorized=false`. Raw host addresses, usernames, secrets and SSH material are excluded.
6. Worker rechecks the newest preflight evidence and Plan fingerprint at a cooperative checkpoint. Any mismatch, unavailable connection, stale/failed/in-flight later preflight, invalid host/overlay network, unavailable worker or canceled job fails closed with sanitized canonical errors.

## Security and independent authority

- **No automatic approval:** A successful Plan materialization job means only that a review artifact was committed, not that the Plan was accepted. No provision endpoint, SSH execution path, shell command console, kubeconfig creation or cluster mutation is added.
- Worker-supplied `maker_checker_approval_verified`, `maintenance_window_verified` and `worker_execution_admitted` fields are ignored. They are not permitted to satisfy runtime/approval gates.
- The fingerprint is a correlation checksum, **not a signature, authorization bearer token or immutable external approval record**. The eventual #4801 executor must independently validate current committed target/identity, source/EE, Plan generation, maker/checker, active change window and cluster lock immediately before mutation.
- The current localhost-only #4799 worker and OXY7O/kaori-operations Draft PRs #2/#6 are non-executable. Until an independently admitted remote-host JobExecution exists, the Generate button remains disabled and no Plan can be created in a real environment.
- Successful JobExecution completion is truthful only for **Plan materialization**. Runner exit code alone may never mark cluster provisioning successful. Kubernetes API read-back and owner verification belong to #4801.
- All operator feedback uses the shared KAORI Operational Toast plus Activity Audit. Preview/Plan validation warnings must not flood Notification Deck. Job progress and terminal state use canonical Jobs & Executions.

## Quality and UAT

Focused tests cover deterministic/stale/altered fingerprint, source SHA, wrong queue or identity, overlapping CIDRs, missing host address, secret-free result and non-approved Plan state. Dispatcher, worker, and form negative tests must prove no unauthorized remote action and canonical job ownership.

Run existing Ruff check/format, Pyright, djlint, focused pytest, verify_ui_reuse and verify_ui_style against the exact issue head. Also validate Celery worker task registration and a PostgreSQL-backed fake preflight/job in Dev Container. **These executable checks and real-host UAT have not been run in this connector session.**

Before #4800 can close: complete an independently trusted read-only remote preflight through #4799, prove immutable Plan persistence and invalidation on real host inventory change, reconcile external maker/checker approval and expiry, complete Human Acceptance, and pass Developer Check/Full Admission and official staging/UAT.

No in-place automatic deployment or release is authorized by this document.

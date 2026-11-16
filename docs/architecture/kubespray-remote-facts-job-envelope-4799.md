# Kubespray #4799 — exact remote-facts JobExecution attempt envelope

This issue-scoped slice is **pure, review-only validation**. It is not a
worker implementation and does not add a provider, queue, permission, model,
HTTP route, secret resolver, SSH call, or Kubernetes mutation.

## Contract

`qualify_facts_job_envelope` requires the caller to supply canonical persisted
JobExecution job/attempt/integration identity and independently resolved asset,
source commit and pinned EE digest. A completed worker observation must match
all six values exactly, be on the dedicated `automation` queue, report only
`ansible.host_facts.read_only`, have a successful integer return code,
`changed is False`, a bounded event count, a maximum ten-minute duration,
and completion within fifteen minutes. Unknown fields, including raw events,
stdout and credentials, fail closed. Every result has
`execution_authorized=False`.

The expected values **must not** be accepted from browser payloads or from
the same untrusted runner event. This module deliberately does not assert
independent authority, signed source, trusted known_hosts, credential access,
worker isolation or provider readback. A positive result means
`requires_independent_admission`, not Ready, approved, or Run permission.

## Required integration before worker dispatch

1. Reconcile the concurrent #4799 Draft PR stack and source/EE provenance.
2. Resolve canonical asset/host-key authority and protected credential reference.
3. Enforce worker queue isolation and trust verification outside Flask.
4. Persist through existing JobExecution and Activity Audit; reject old success
   after a newer failed or pending attempt. Reuse currentness semantics rather
   than treating this envelope as a latest-attempt query.
5. Independently verify host facts and use the existing IntegrationBinding and
   Cluster authority. No arbitrary playbook console.
6. Obtain controlled real-host UAT and Human Acceptance before official admission.

## Verification and hold

Committed regression tests cover exact success and denial for stale evidence,
identity/source/EE drift, wrong queue/operation, mutations, bad return codes,
unexpected secret-bearing fields, malformed identifiers and timestamps.
**Ruff, pytest, pyright, CI, Dev Container, real-host UAT: NOT RUN** at
authoring. This PR is Draft and not an authorization to execute.

#4800 remains OPEN and Plan is review-only. #4801 and later mutating
lifecycle issues remain blocked. Operations source Draft PRs #2/#6 remain
non-executable until independently admitted.

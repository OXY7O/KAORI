# Remote facts cross-record coherence (#4799)

This narrow pure validator compares exact identity across separately obtained canonical
JobExecution, host evidence, and authority evidence snapshots. It is a **necessary
consistency check**, not proof that the records were obtained from independent trusted
issuers. No worker dispatch, SSH, Ansible, credential resolution, or Kubernetes mutation
is implemented. Successful comparison yields `requires_independent_admission`, never Run.

## Integration contract

The caller must retrieve records server-side from approved authorities and authenticate
their provenance before invoking the comparison. The strict allowlist is JobExecution ID,
attempt number, IntegrationBinding ID, canonical asset ID, exact source Git SHA, exact
EE digest and inventory fingerprint. Unknown keys (including secrets) fail closed.
The latest-attempt selector, evidence freshness, signed source/EE qualification,
approved SSH host-key reference, protected credential access, dedicated remote-facts
worker isolation, event redaction and Activity Audit remain separate mandatory gates.
Do not allow a browser to supply an authority snapshot.

## Dependencies and verification

Review alongside #4905–#4930, especially the worker and credential authority contracts.
This candidate does not supersede the merged #4899 preflight, #4906 immutable Plan or
#4917 Plan currentness. #4800 remains open and review-only. #4801 and later lifecycle
operations remain blocked. The added pytest suite covers identity drift, malformed
records, unknown fields and exact-match non-authorization. Ruff, pytest, Pyright, CI,
real-host UAT and Human Acceptance require execution on the exact candidate SHA
before admission; no PASS is asserted here.

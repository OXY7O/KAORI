# #4799 — bounded remote facts evidence contract

Authority: #556 → #4796 → #4799. This incremental contract is deliberately **not** a remote facts worker or an authorization decision. It must not be used to mark #4799, #4800 or #4801 complete.

## Scope and provenance

`app/infrastructure_automation/remote_facts_evidence.py` defines an allowlisted, pure evidence projection. It checks exact asset identity, 40-character immutable source Git SHA, pinned `sha256:` EE digest, SSH host-key fingerprint, native read-only operation `linux.host_facts.v1`, successful runner return code and strictly `changed is False`. It accepts only bounded OS/kernel/architecture/CPU/RAM facts. Any extra keys, including raw Runner events, hostvars or secret material, cause denial; errors return only a generic finding code.

A successful projection returns **requires_independent_admission**, never Ready, Approved or Run permission. Its expected identifiers are parameters for a future worker to obtain from canonical asset/IntegrationBinding, protected secret reference, trusted known_hosts and source/EE authorities. Supplying matching values from a browser or worker self-assertion does not prove independent trust. The contract does not retrieve credentials, resolve SSH trust, dispatch Celery, persist JobExecution, execute Runner, or mutate hosts.

## Integration gates still required

1. Reconcile concurrent #4799 Draft PRs #4905/#4907/#4908/#4909/#4911/#4914/#4915/#4919/#4923 before integrating overlapping validators; do not overwrite their changes.
2. Resolve approved asset identity, exact SSH host key from a trusted authority, protected credential reference, qualified signed EE and exact admitted Git source; OXY7O/kaori-operations #2/#6 are still Draft/nonexecutable.
3. Implement isolated, read-only Celery automation worker with canonical JobExecution, source-owned native Ansible facts, strict worker route, cancellation, redacted events and independent provider readback. Connect this projection only after authority review.
4. #4800 immutable Plan remains review-only; maker/checker/window and exact target lock must be independent before #4801 disposable nonproduction provisioning. No privileged operations are admitted by this change.

## Verification (not yet run in Dev Container)

```bash
python -m ruff check app/infrastructure_automation/remote_facts_evidence.py tests/contracts/platform_operations/test_ansible_remote_facts_evidence_contract.py
python -m ruff format --check app/infrastructure_automation/remote_facts_evidence.py tests/contracts/platform_operations/test_ansible_remote_facts_evidence_contract.py
python -m pytest -q -p no:cacheprovider tests/contracts/platform_operations/test_ansible_remote_facts_evidence_contract.py
python -m pyright app/infrastructure_automation/remote_facts_evidence.py
```

GitHub commit confirmation is not executable QA. Dev Container, CI, Visual UAT, controlled real-host readback and Human Acceptance remain **PENDING**. This issue branch must not be promoted into temporary holding until review and relevant gates are evidenced.

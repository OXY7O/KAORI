# #4799 — Remote host evidence hardening checkpoint

This candidate tightens the **read-only** Kubespray host preflight projection.
An attested asset identifier must be an exact nonblank bounded string: leading
or trailing whitespace and identifiers longer than 96 characters are rejected.
A host-network observation of `0.0.0.0/0` is not a concrete network read-back
and must not qualify CIDR readiness. These are negative validation changes,
not SSH admission or executable inventory construction.

## Evidence and authorization boundaries

- Canonical IntegrationInstance and latest scoped JobExecution remain the
  evidence sources. Browser input cannot substitute for worker observations.
- Source-only checks are not host-key verification. No credentials, trusted
  known_hosts binding, signed EE, or authorized remote worker are introduced.
- The dedicated #4799 worker must bind an approved asset identity, pinned
  SSH host-key fingerprint and protected credential reference before any
  read-only remote contact. A worker self-declared approval is never authority.
- #4800 persisted immutable Plan and independent maker/checker/window remain
  unimplemented. #4801 and subsequent mutating lifecycle steps remain blocked.
- Source repository OXY7O/kaori-operations Draft PRs #2/#6 are not admitted
  executable sources. No actual host, Ansible or Kubernetes API was contacted.

## Review verification

Run `python -m ruff check` and `python -m ruff format --check` on the
changed Python files, followed by `python -m pytest -q -p no:cacheprovider
tests/contracts/integrations/test_ansible_remote_host_evidence_contract.py`.
Also run relevant existing Ansible/JobExecution regression suites and
`python scripts/verify_ui_reuse.py` / `python scripts/verify_ui_style.py`
before considering integration. This connector-only commit has **not**
executed those commands, CI or real provider UAT. Human Acceptance HOLD.

## Follow-on #4799 host-network validation

The bounded source-only projection now explicitly rejects IPv4 default routes,
loopback, link-local and multicast networks as observed host interface CIDRs.
A disjoint unicast network is not rejected merely for being outside RFC1918:
publicly routed interfaces may exist, but still require independently admitted
asset identity, authorized target and verified host-key/credential bindings.
This check does **not** establish reachability, SSH trust or worker admission.
Regression cases cover rejected special ranges and accepted disjoint unicast.

Verification remains **NOT RUN** for the follow-on connector commits: execute
Ruff check/format, focused pytest and existing Ansible/JobExecution contracts
on the exact branch SHA before any integration. Keep this dependent candidate
in Draft while #4905 and its review are outstanding; no host contact permitted.

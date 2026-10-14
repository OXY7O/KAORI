# Linux Host Discovery — Read-only Observation Technical Contract

**Authority:** #2014, parent #1907; Infrastructure Automation #556, identity #712, security #638/#641/#724. Docker privilege proof #2013 is an independent workstream.
**Status:** Implementation contract / review candidate only — **NOT IMPLEMENTED, NOT TESTED, NO HOST CONTACT**.
**Branch:** kaori/issue-2014-linux-host-observation-spec.

## Objective

Demonstrate a **minimal, source-qualified Linux host observation** via a pre-approved non-root SSH identity and a pinned Ansible execution environment, using existing KAORI JobDefinition / JobExecution / Celery contracts. Host connectivity and OS facts do not confer Docker daemon, sudo, automation mutation, or asset-adoption authority.

**No change to existing provider authority:** Ansible executes host fact collection; KAORI orchestrates and retains evidence. SSH, OS and hypervisor providers remain authoritative for their own identities. Do not create a generic shell execution API, a universal CMDB, or a new task scheduler.

## Reuse decisions

- Canonical integration instance and asset binding: app/models/integration.py, app/integrations/README.md, #712. Decide owning Host model/type using actual existing asset model baseline **before database changes**; do not claim one is implemented based on foundation #556.
- Canonical execution: docs/architecture/job-execution-foundation.md and app/platform_operations/jobs/README.md. Register the operation in the existing definition registry, with scoped permission, tenant/environment/host and failure evidence. Never dispatch arbitrary Celery tasks from GET/HTMX.
- Python runtime requirements/base.in currently do not declare ansible-core/ansible-runner. Pin a reviewed Ansible EE dependency/digest for the internal worker; do not silently add runtime packages to Flask. Check actual supported OS/Python before qualification.
- SSH host trust: independently verified host public key/fingerprint or trusted host CA, protected deployment-known_hosts, StrictHostKeyChecking=yes or effective equivalent, and explicit key/CA rotation workflow. Reject changing identity, never auto-accept TOFU on a privileged discovery path.
- Credential: store approved reference only in KAORI evidence; key material stays in its authority. Maintain separate SSH principals for *host facts* and any later forced-command Docker snapshot collector #2013.

## Execution path

~~~text
Operator authorizes exact host/source/environment and independently verifies SSH host key
  -> approved host target/source + protected credential reference
  -> canonical JobDefinition and JobExecution (scoped RBAC, quota/dedup, audit)
  -> internal worker with pinned Ansible EE and fixed approved host-facts playbook
  -> SSH trust verification / non-root remote facts account (no become)
  -> bounded OS/architecture/kernel + identity-corrobating facts
  -> local normalization / allowlisted committed evidence
  -> source revision/attempt owner recheck under a short DB transaction
  -> last-qualified observation + freshness and error evidence
  -> normal operator read path uses committed SQL (no SSH/provider GET)
~~~

Do not confuse **registered target**, **observed host**, and **governed/adopted asset**. Host discovery alone never grants permission to run other playbooks, change config, sudo, or open Docker.

## Suggested constrained Ansible setup profile (illustrative, not runnable authority)

Do not enable automatic broad facts. Pin the actual EE/playbook identity, ensure allowed hosts are pre-resolved from an approved asset reference rather than operator-entered arbitrary hostnames, disable become and custom plugin/local-fact execution paths that have not been reviewed.

~~~yaml
- name: Approved bounded Linux facts profile (design illustration)
  hosts: approved_linux_host
  gather_facts: false
  become: false
  tasks:
    - name: Observe approved OS facts
      ansible.builtin.setup:
        gather_subset:
          - "!all"
          - "!min"
          - distribution
          - os_family
          - kernel
          - architecture
          - machine_id
        filter:
          - ansible_distribution
          - ansible_distribution_version
          - ansible_os_family
          - ansible_kernel
          - ansible_architecture
          - ansible_machine_id
        gather_timeout: 10
~~~

The exact ansible.builtin.setup facts availability, gather_subset behavior and fact_path/local executable *.fact handling must be verified against the **pinned** Ansible version and chosen target OS. Ansible modules normally execute remote code and may create temporary files; this is read-only in *workflow intent*, not a guarantee of absolutely no OS writes. Review and explicitly disable any profile that invokes local executable fact scripts, unreviewed plugin/lookup, shell command or Python interpreter substitution. Do not claim safe collection simply because module has check-mode support.

Reference: https://docs.ansible.com/projects/ansible/latest/collections/ansible/builtin/setup_module.html and https://docs.ansible.com/ansible/latest/collections/ansible/builtin/ssh_connection.html .

## Logical result schema (do not create a database table from this alone)

~~~yaml
host_observation_v1:
  canonical_source_ref: <existing approved host/source binding>
  config_generation: <trusted source revision>
  collection_attempt_id: <canonical JobExecution attempt>
  observed_at: <worker observation UTC>
  committed_at: <KAORI DB commit UTC>
  ssh_host_identity: <verified public fingerprint/reference>
  observed:
    os_family: <allowlisted value or unknown>
    distribution: <allowlisted value or unknown>
    distribution_version: <allowlisted value or unknown>
    kernel: <allowlisted value or unknown>
    architecture: <allowlisted value or unknown>
    machine_id: <observed identifier with sensitive/provenance classification>
  aliases:
    hostname: <non-authoritative if collected>
    address: <non-authoritative>
  coverage:
    complete: <validated true/false>
    error_codes: <sanitized bounded list>
~~~

The remote source cannot set KAORI tenant, owner, approval, asset adoption, current source revision, verified status, or arbitrary JSON evidence. Avoid saving raw ansible_facts, SSH stdout/stderr, environment variables, mount tables, running processes, users, packages, IP inventory and unreviewed hardware identifiers. Decide sensitivity and retention under #639 and existing Data Lifecycle. Linux machine-id may duplicate across clones; no automatic asset merge on machine-id/IP/hostname alone.

## Concurrency, recovery and admission

1. Register source/host with current configuration revision and verified host key before dispatch. Permission and exact source selection apply at admission and worker preflight.
2. Collect via dedicated internal worker with bounded timeout, source quota and host-specific concurrency. Do not hold a database row lock while waiting for SSH.
3. Complete and normalize only allowlisted facts locally. Check source/config generation, host-key identity and attempt ownership again at atomic commit. A late worker cannot overwrite a newer generation.
4. Preserve last-known-good on unreachable SSH, changed key, revoked credential, malformed/partial facts, cancellation or broker loss. Label new attempt failed/stale without marking the actual host deleted.
5. Separate lightweight connectivity health, full host-facts collection, authorized asset adoption, and any provider mutation. Do not treat an Ansible exit 0 as proof of asset owner authority or Docker readiness.
6. Five-minute collection freshness is a fleet **design target** subject to measured worker capacity and source eligibility; capture queue wait + connect + facts + commit p50/p95/p99 with honest unknowns. Do not create a separate per-host scheduler.

## Acceptance matrix — before host discovery can be called ready

| ID | Scenario | Required evidence |
|---|---|---|
| HOST-01 | Approved Linux target with pinned host key | Known-host trust proven; only allowlisted OS facts committed |
| HOST-02 | Host-key mismatch or missing independent fingerprint | Rejected before collection, no TOFU |
| HOST-03 | Unauthorized other host/tenant/environment | Server and worker reject; no cross-scope SSH |
| HOST-04 | Non-root identity lacks become/docker privileges | Effective remote account and task evidence |
| HOST-05 | Duplicate hostname or cloned machine-id | Source records distinct; no implicit merge |
| HOST-06 | IP reuse, host OS reinstall or rotated host key | Old lineage retained and new identity reviewed |
| HOST-07 | Remote timeout/SSH denial or malformed facts | Last-good preserved with actionable sanitized diagnostic |
| HOST-08 | Unexpected executable local facts / broad plugin execution | Not executed in the approved facts profile |
| HOST-09 | Concurrent manual+scheduled attempts and changed source revision | Old attempt commit fenced, newer source remains current |
| HOST-10 | Secrets injected into synthetic remote result/error | No leak in committed state, audit, log or export |
| HOST-11 | Worker crash, cancellation and bounded retry | Correct JobExecution truth, no stale overwrite |
| HOST-12 | Source connection validation vs collection vs adoption | No unauthorized implicit provider mutation or management grant |

Companion Gherkin: tests/security/features/linux_host_discovery_boundary.feature (**specification only; no runner registered and no tests run**).

## Delivery / UAT requirements

- Review exact Host model and binding ownership, pinned Ansible EE, restricted SSH user, host-key establishment/rotation, safe facts subset, output redaction, permission semantics, source-generation atomic commit and quality gates before implementation.
- Implementation may proceed independently of Docker socket proof #2013, but **must not gain Docker/sudo or generic configuration mutation rights**. That boundary remains a separate security approval.
- Only use disposable and explicitly permitted Linux targets for initial SSH UAT. Do not use production host or change remote security settings through the fact-collection workflow.
- Run existing focused pytest/architecture/security gates and later Developer Check → PR to kaori/staging → Full Admission → staging/UAT → human acceptance before marking the capability operational.
- Test matrix is **NOT_RUN** until measured source and controlled UAT evidence exist. Never mark all scenarios PASS by writing their Gherkin text.

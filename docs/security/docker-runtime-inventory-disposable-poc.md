# Docker Runtime Inventory — Disposable Security Proof of Boundary

**Authority:** #2013 (security feasibility), parent #1907, host-only prerequisite #2014, downstream Docker provider #2015 and inventory #2016.
**Status:** Test protocol / review candidate — **NOT EXECUTED; NO SECURITY PASS**.
**Branch:** kaori/issue-2013-docker-security-poc-spec.
**Scope:** Disposable, owner-authorized lab only; not production deployment, target onboarding, or a KAORI operator runbook for administering remote Docker.

## 1. Question and non-negotiable boundary

Can a KAORI fleet inventory worker obtain sufficient Docker Engine / Compose observations from an existing *rootful* Engine, while compromise of its remote SSH credential does **not** grant a general interactive shell, Docker API/socket access, sudo or Docker group access, command argument execution, network forwarding, or host mutation?

An SSH command that happens to call docker ps is **not** proof. The privilege boundary must exist on the **host** independently of the worker and the KAORI UI.

Reference authorities:
- Official Docker Engine authorization: https://docs.docker.com/engine/extend/plugins_authorization/
- Docker daemon access security: https://docs.docker.com/engine/security/protect-access/
- OpenSSH authorized_keys restrict/command: https://man7.org/linux/man-pages/man8/sshd.8.html
- OpenSSH sshd_config ForceCommand and DisableForwarding: https://man7.org/linux/man-pages/man5/sshd_config.5.html
- Docker Engine API versioning: https://docs.docker.com/reference/api/engine/version-history/
- KAORI canonical Jobs, Integration Lifecycle, Security Architecture #638, Access #641/#724 and Secrets #714.

## 2. Candidate C1 — two-principal, fixed-command architecture

~~~text
[KAORI canonical JobExecution, authorized source and target identity]
                     |
              Internal Worker
                     |
          verified SSH host identity
                     |
       restricted inventory SSH identity
    (no docker group, no shell or forwarding)
                     |
     exact fixed command / owned executable
         (reject unexpected command)
                     |
        privileged local helper/collector
           (host-owned trusted code)
                     |
           local Docker Unix socket
                     |
   locally projected, validated, bounded JSON
                     |
      worker verifies source/config generation
                     |
          fenced committed observation
~~~

**Privilege boundary:** the inventory SSH identity does not open the Docker socket itself. A separate, administrator-controlled host-local component may have daemon rights, but exposes only one versioned snapshot operation. The collector is privileged trusted code, **not** a read-only Docker daemon user. Installing/updating this helper is an independently approved host mutation. The worker must never receive a Docker API proxy, arbitrary shell, Docker CLI option, daemon TCP endpoint or general privileged token.

**Host-only facts are separate:** #2014 uses an independently authorized non-root SSH/Ansible profile. It is not the collector's forced-command identity. A normal Ansible setup module cannot be assumed to work through this forced command.

Do not enable root login, install helpers, modify sshd/sudoers, open a daemon TCP listener, change Docker group membership or place real SSH keys/secrets in the repository as part of this protocol.

## 3. Lab preconditions (all mandatory)

- Host owner approves a disposable VM on a network segment isolated from production and sensitive provider endpoints; VM is snapshot/reimage capable and can be destroyed after the PoC.
- Test environment has a pinned Linux/OpenSSH version, Docker Engine version/API profile, known target address and out-of-band verified SSH host-key fingerprint. Record the **actual** versions; never borrow a production host.
- Prepare synthetic canary containers/images and synthetic string markers in Env, arbitrary labels, mounts/paths and Compose project/service. **No real sensitive data.**
- Configure distinct host accounts/SSH keys for unrestricted disposable-lab administrator and restricted inventory identity. The inventory account is not root and not in docker/privileged groups. Record groups via administrator, not by assuming UI or SSH identity names imply privileges.
- A reviewed, root-owned, non-user-writable collector/helper and exact invocation boundary must exist **before tests are run**. No generic sudo, shell, python -c, docker CLI forwarding, arbitrary request path, URL, container ID, or argument may be supplied by the inventory principal.
- The restricted SSH authorization policy must cover all authentication paths, not only one authorized_keys line: key-only login or equivalent approved policy; verified host key on the client; shell/subsystem/PTY/port/agent/X11/StreamLocal forwarding disabled; account ownership of home/authorized_keys/config strictly controlled. ForceCommand alone is **insufficient** to disable forwarding.
- Explicitly decide whether invocation requires the one exact command identifier (e.g. kaori-inventory-snapshot-v1) or *no* original command; reject anything else including SSH_ORIGINAL_COMMAND with shell metacharacters. The fixed executable itself must not consume/interpret SSH_ORIGINAL_COMMAND as code.
- Define an administrator-owned method to inspect the actual effective sshd policy, filesystem ownership/ACL, sudo policy (if any), and collector binary/script hash. Use the host's standard sshd configuration validation; do not assume user-input snippets are safe verbatim.
- Obtain an approved scope/timebox, operator, reviewer, cleanup plan, backup/VM snapshot if needed, baseline container/volume state and evidence directory with no credentials. An unknown/incomplete prerequisite means **BLOCKED**, not an invitation to relax permissions.

## 4. Collector observation contract v1 — proposed, not implemented

One bounded operation; no input parameters that select daemon methods, container IDs, arbitrary filters, output formats, or command execution.

Allowed internal Docker API reads (exact API version is pinned during qualification):
- GET /version (extract version/API compatibility only).
- GET /info (extract **only** a reviewed Engine identity subset; never expose the raw response).
- GET /containers/json?all=1 (extract Id, Names, Image, ImageID, Created, State; accept only validated Compose project/service labels).
- Optional GET /images/json?digests=1, **only if the client API version supports it** and needed for repository-qualified RepoDigests. Reject oversized/raw image responses; ImageID is not a registry manifest/index digest.

Disallow inspect, exec, logs, events streaming, processes, mount paths, environment variables, raw labels, device/network internals, credentials, Docker build/create/start/stop/delete APIs, HTTP upgrade, custom headers or arbitrary API calls. An allowlisted GET can itself return sensitive data, so projections and length/type checks happen on the host *before* emitting bytes to the SSH client.

Logical result fields:
- schema_version, collector_version, collection_id, started_at, completed_at;
- engine_identity and observed API/version, **not** self-claimed KAORI governance identity;
- coverage.complete plus explicit truncation/partial/failed reason;
- bounded containers: id, name, image_reference, local_image_id, created_at, state and optional sanitized Compose project/service;
- optional source-qualified repository digest evidence, explicitly distinct from local image ID.

KAORI independently owns IntegrationInstance, target identity, requested scope, source config revision, JobExecution attempt, worker identity, credential reference, observed_at/committed_at and source-generation fencing. The collector must not be able to assign its own tenant, owner, authorization state, or successful JobExecution state.

**Size and completeness invariant:** bound HTTP response bytes, output bytes, per-field lengths, record count, and wall time. If the source exceeds an approved bound, signal qualified *partial/incomplete* and preserve prior last-good; silently truncating and reporting complete is FAIL. If data cannot be safely projected, return a sanitized failure code without raw provider content.

## 5. Required security test gates

These tests run only against the disposable host after separately approved lab provisioning. A negative-case test is PASS only when the **host-side guard** blocks unintended effects and independent administrator read-back confirms the canary baseline is unchanged.

| ID | Test | Required result |
|---|---|---|
| SEC-01 | Pinned trusted SSH key, exact snapshot command | One valid minimal JSON snapshot, no extra stdout/stderr sensitive text |
| SEC-02 | Arbitrary SSH command, interactive shell, user-supplied interpreter/options | Rejected by host policy; no original command executed |
| SEC-03 | SSH PTY, SFTP/SCP, port/StreamLocal/agent/X11 forwarding | All denied; no alternate raw Docker access |
| SEC-04 | Inventory account groups, file ownership, sudo -l and helper paths | No general docker group, shell escalation, writable helper, generic sudo or interpreter escape |
| SEC-05 | Attempt Docker create/run/start/stop/exec/delete, volume mount or socket read | No such capability via inventory SSH principal; canary state unchanged |
| SEC-06 | Unexpected SSH_ORIGINAL_COMMAND, environment variables, symlink/path, replacement race | Reject before any privileged path; helper immutability proved |
| SEC-07 | Untrusted/changed SSH host key and revoked/expired credential | Connection blocked without trust auto-accept or fallback |
| SEC-08 | Docker response with fake secrets in Env, raw labels, path/mount info, console-control bytes | No unauthorized values in stdout, logs, job, database, archive or errors |
| SEC-09 | Docker API timeout, socket denied, daemon down, unsupported API version | Sanitized blocked/partial result; no broad fallback |
| SEC-10 | High item count / oversized JSON / malformed API response | Bounded partial/failure; no silent truncation-as-complete, crash, or secret spill |
| SEC-11 | Source config changed; late old attempt reports success | Atomic generation/attempt guard rejects stale overwrite (once KAORI consumer exists) |
| SEC-12 | Same image ID vs RepoDigest/tag/multi-platform artifact | Never emit an unverified strong Registry binding; unknown clearly marked |
| SEC-13 | Repeated approved collection on quiet host | No provider mutation, no increased privileges, stable normalized evidence |
| SEC-14 | Collector update/revoke and host disposal | Change requires host-owner authorization; former inventory identity loses access, cleanup verified |

**Outcome vocabulary for this proof:** NOT_RUN, BLOCKED, PASS, FAIL with timestamp, source/revision, tester, test host, proof artifact reference and reason. These are proof-record labels for this lab, **not new KAORI JobExecution statuses or Project taxonomy**. Any FAIL on SEC-02 through SEC-08 is a security blocker, not an acceptable “read-only in the UI” compromise.

See companion Gherkin source under tests/security/features/docker_runtime_inventory_boundary.feature. It is **specification only**; no Gherkin runner is registered by merely adding this file.

## 6. Safe operator invocation template — only after approved lab setup

Keep keys, fingerprints and endpoint names outside the repository. Replace variables **only for an expressly approved disposable host**. This template tests transport behaviors, not host provisioning:

~~~bash
# LAB ONLY; never substitute a production target.
# LAB_HOST, LAB_USER, LAB_KEY, LAB_KNOWN_HOSTS must come from the approved lab inventory.
# The key file must be protected and the known_hosts entry verified out of band.
ssh -F /dev/null -i "$LAB_KEY" -o BatchMode=yes \
  -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$LAB_KNOWN_HOSTS" \
  -o IdentitiesOnly=yes -o ClearAllForwardings=yes -T \
  "$LAB_USER@$LAB_HOST" kaori-inventory-snapshot-v1

# One rejected command test; it MUST NOT run echo or return a snapshot as success.
ssh -F /dev/null -i "$LAB_KEY" -o BatchMode=yes \
  -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$LAB_KNOWN_HOSTS" \
  -o IdentitiesOnly=yes -T \
  "$LAB_USER@$LAB_HOST" "echo UNAUTHORIZED_COMMAND"
~~~

For negative forwarding tests, use approved loopback-only disposable canary destinations and timeouts; do not tunnel to Docker socket, provider admin ports, production networks, or secrets systems. For mutation denial tests, issue only approved benign canary attempts using the restricted account and independently recheck the canary via lab administrator. **Do not add privileged mutation commands to the KAORI application.**

## 7. Evidence, scoring and reviewer decision

Evidence folder in the approved lab/test records (not Git secrets): signed/identified disposable host and Docker version, host-key provenance, effective SSH restrictions, account groups and permissions, helper hash/owner, sanitized snapshot schema, negative-test transcripts with canary before/after, collector logs with redaction proof, CPU/memory/time and source complete/partial results. Record all test attempts as executed/failed/skipped with exact reasons.

- **GO for future provider development** requires all critical trust/privilege/redaction negative tests PASS and an explicit security/human acceptance decision; it still does not approve production installation.
- **NO-GO** when any arbitrary shell/socket/sudo/forwarding/daemon mutation becomes reachable by the inventory identity, when secrets leak, when host identity cannot be verified, or when corrupted/partial evidence is marked complete.
- **BLOCKED / UNPROVEN** when the helper, disposable target, independent baseline or runtime test proof is missing. Documentation, mocking, source inspection and CI cannot substitute for real boundary proof.
- Follow-up implementation authorization is separate: #2013 proof, then #2015 provider and #2016 collector/inventory only after accepted constraints. #2014 host-only observation may proceed independently, with its own SSH/Ansible evidence and no Docker privileges.

## 8. Deliberately outside this proof

No second scheduler, CMDB, graph engine, new PKI/SSH CA, remote mTLS gateway, HA redesign, generic remote shell API, live Docker mutation, container/Compose deploy or production credential handling. Preserve #1907 architecture and #556 Ansible execution authority.

**GitHub flow:** Issue #2013 → work branch (this specification) → later controlled lab PoC/test evidence → Developer Check only when PR opened/authorized → PR to kaori/staging → Full Admission → UAT → human acceptance. The current branch is **documentation/test-spec only**; this document alone does not close #2013.

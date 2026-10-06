# KAORI UAT VPS and GitHub Runner Co-location Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Support the temporary UAT topology where the KAORI self-hosted GitHub runner and KAORI deployment target share one VPS without merging their identities, paths, credentials, or lifecycle authority.

**Architecture:** Keep `ops/github-runner/` and `deploy/vps/` as separate operational domains even when they share one physical host. Preserve the existing SSH-based deployment interface as `kaori-deploy`, reject `github-runner` as the deployment identity, and document the Docker root-equivalent co-location risk as temporary UAT infrastructure debt.

**Tech Stack:** Bash, GitHub Actions, Docker Engine/Compose, pytest contract tests, Markdown operating docs.

**Spec:** `docs/superpowers/specs/2026-09-03-vps-runner-colocation-design.md`

## Global Constraints

- Runner account remains `github-runner`; deploy account remains `kaori-deploy`.
- Runner home remains `/opt/actions-runner`; deployment root remains `/opt/kaori`.
- Deployment continues through SSH with pinned `KAORI_VPS_KNOWN_HOSTS`, even while both roles share one VPS.
- `deploy/vps/bootstrap-host.sh` must not modify runner registration, runner service state, or `/opt/actions-runner`.
- `/etc/kaori/.env.production` remains operator-managed and must not be copied into runner workspace.
- Docker group membership is root-equivalent privilege and co-location is accepted only as a temporary UAT constraint.
- NGINX, firewall, SSH daemon hardening, DNS, and TLS remain Issue #50 scope.
- Work branches run Developer Check only; comprehensive authority starts after merge to `kaori/staging`.

---

### Task 1: Lock the co-location contract with RED tests

**Files:**
- Modify: `tests/contracts/release/test_vps_host_bootstrap_contract.py`

**Interfaces:**
- Consumes: existing `BOOTSTRAP` and `README` source paths.
- Produces: contract assertions requiring separate runner/deploy identities and preserving SSH deployment semantics on a shared VPS.

- [ ] **Step 1: Write the failing test**

Add assertions equivalent to:

```python
def test_vps_host_bootstrap_preserves_runner_identity_when_colocated() -> None:
    source = _read(BOOTSTRAP)
    assert "deploy_user != 'github-runner'" in source
    assert '/opt/actions-runner' in source
    assert 'preserving GitHub runner operations' in source


def test_vps_runbook_documents_shared_host_without_collapsing_trust_boundary() -> None:
    source = _read(README)
    for marker in (
        'same physical VPS',
        'github-runner',
        'kaori-deploy',
        '/opt/actions-runner',
        '/opt/kaori',
        'SSH remains the deployment boundary',
        'temporary UAT',
    ):
        assert marker in source
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest -q tests/contracts/release/test_vps_host_bootstrap_contract.py
```

Expected: FAIL only on the new co-location assertions because the current bootstrap/runbook do not yet encode the approved shared-host boundary.

- [ ] **Step 3: Commit RED evidence**

```bash
git add tests/contracts/release/test_vps_host_bootstrap_contract.py
git commit -m "test(deploy): lock shared runner VPS boundary #126"
```

### Task 2: Preserve separate Unix identities on the shared host

**Files:**
- Modify: `deploy/vps/bootstrap-host.sh`
- Test: `tests/contracts/release/test_vps_host_bootstrap_contract.py`

**Interfaces:**
- Consumes: `--deploy-user`, existing `deploy_user` validation and `github-runner` default authority from `ops/github-runner/README.md`.
- Produces: fail-closed validation preventing `github-runner` from becoming the KAORI deployment identity, without altering the existing runner installation.

- [ ] **Step 1: Implement the minimal identity guard**

Keep the existing non-root validation and add an explicit runner-account boundary:

```bash
[[ "$deploy_user" != 'root' ]] || fail 'deploy user must not be root'
[[ "$deploy_user" != 'github-runner' ]] || fail 'deploy user must remain separate from the GitHub runner account'
```

Add a read-only co-location notice when the standard runner home exists:

```bash
if [[ -d /opt/actions-runner ]]; then
  printf 'GitHub runner co-location detected; preserving GitHub runner operations at /opt/actions-runner.\n'
fi
```

Do not modify `/opt/actions-runner`, `config.sh`, `svc.sh`, runner registration, or runner credentials.

- [ ] **Step 2: Run focused contract**

```bash
pytest -q tests/contracts/release/test_vps_host_bootstrap_contract.py
```

Expected: bootstrap identity assertions PASS; runbook assertions may remain RED until Task 3.

- [ ] **Step 3: Commit implementation**

```bash
git add deploy/vps/bootstrap-host.sh
git commit -m "fix(deploy): preserve runner identity on shared VPS #126"
```

### Task 3: Document the temporary shared-host UAT topology

**Files:**
- Modify: `deploy/vps/README.md`
- Modify: `ops/github-runner/README.md`
- Test: `tests/contracts/release/test_vps_host_bootstrap_contract.py`

**Interfaces:**
- Consumes: approved co-location spec and existing SSH deployment authority.
- Produces: operator-facing explanation that physical co-location does not collapse operational boundaries.

- [ ] **Step 1: Update deployment runbook**

Document these exact operating facts:

```text
During UAT the GitHub runner and KAORI deployment target may share the same physical VPS.
The runner remains github-runner under /opt/actions-runner.
Deployment remains kaori-deploy under /opt/kaori.
SSH remains the deployment boundary even when source runner and target are currently the same host.
The workflow must use the reviewed VPS hostname/IP and pinned KAORI_VPS_KNOWN_HOSTS entry rather than a localhost bypass.
Docker access for both identities is root-equivalent privilege and this co-location is a temporary UAT constraint.
```

Keep `/etc/kaori/.env.production` outside runner workspace and preserve all Issue #50 boundaries.

- [ ] **Step 2: Update runner operations runbook**

Add a short co-location section stating that `ops/github-runner/` may share a host with KAORI during UAT but does not own `/opt/kaori`, `/etc/kaori`, `/var/lib/kaori`, deployment credentials, or application lifecycle.

- [ ] **Step 3: Run focused contract**

```bash
pytest -q tests/contracts/release/test_vps_host_bootstrap_contract.py
```

Expected: PASS.

- [ ] **Step 4: Commit docs**

```bash
git add deploy/vps/README.md ops/github-runner/README.md
git commit -m "docs(deploy): document runner and runtime co-location #126"
```

### Task 4: Validate the final work-branch candidate

**Files:**
- No new source files.
- Verify the PR diff and existing release/deployment contracts.

**Interfaces:**
- Consumes: Tasks 1-3 final candidate.
- Produces: exact-SHA Developer Check evidence for PR #127.

- [ ] **Step 1: Run/observe path-aware Developer Check**

Expected gates for this deployment/release-sensitive change include workflow lint, Ruff, formatting, code health, Pyright, migration graph, release contracts, and frontend format according to repository routing.

- [ ] **Step 2: Verify final diff**

Expected bounded source changes:

```text
deploy/vps/bootstrap-host.sh
deploy/vps/README.md
ops/github-runner/README.md
tests/contracts/release/test_vps_host_bootstrap_contract.py
docs/superpowers/specs/2026-09-03-vps-runner-colocation-design.md
docs/superpowers/plans/2026-09-03-vps-runner-colocation.md
```

No application runtime, database migration, NGINX, TLS, firewall, or `main` changes are permitted.

- [ ] **Step 3: Synchronize PR evidence and freeze candidate**

Update PR #127 with RED→GREEN evidence, confirm zero unresolved review threads, mark Ready, and require the exact frozen head SHA for merge.

### Task 5: Integrate through staging authority

**Files:**
- No direct source edits unless staging Full Admission finds a concrete regression.

**Interfaces:**
- Consumes: frozen GREEN PR #127.
- Produces: merge commit on `kaori/staging`, fresh Full Admission evidence, and a new intentional RC for actual VPS UAT.

- [ ] **Step 1: Merge with merge commit to `kaori/staging`**

Use the exact frozen PR head SHA. Do not squash/rebase.

- [ ] **Step 2: Observe comprehensive KAORI CI**

Expected: fresh or reusable evidence only when repository authority permits it. Any staging failure returns to an issue-linked repair branch; no direct staging fix.

- [ ] **Step 3: Record staging admission**

Keep #126 and #49 OPEN at UAT boundary. Do not claim VPS bootstrap smoke until the operator runs the admitted script on the actual shared VPS.

- [ ] **Step 4: Cut a fresh intentional RC**

`v0.1.0-rc.2` remains historical. Actual VPS UAT must use the next intentional RC from the newly admitted staging SHA.

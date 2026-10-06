# RC Tag Reuse Guard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent KAORI from ever overwriting or reusing a Release Candidate tag after the candidate number has been consumed by registry or partial publication history.

**Architecture:** Reserve the candidate Git tag against the exact admitted staging SHA before any registry mutation. Then authenticate to the registry, fail closed if the candidate tag already exists, and only then push the immutable candidate. If a reserved tag has no GitHub prerelease because a prior publisher attempt failed, treat that RC number as consumed and advance monotonically instead of reusing it.

**Tech Stack:** GitHub Actions YAML, Bash, GitHub REST API, Docker CLI, pytest contract tests.

**Spec:** GitHub Issue #138 (`Prevent RC tag reuse after partial registry publication`).

## Global Constraints

- Preserve `Issue → work branch → PR kaori/staging → Full Admission → intentional RC → UAT → main` authority.
- Exact `kaori/staging` SHA and successful Full Admission remain mandatory before RC publication.
- Trivy HIGH/CRITICAL and runtime/DAST gates remain before registry publication.
- No mutable `latest` authority.
- Existing immutable digest evidence is historical and must never be rewritten.
- Registry credentials remain isolated to the publisher job and use `--password-stdin`.
- No new helper script is introduced solely for workflow behavior.

---

### Task 1: Lock the collision-safe publication contract

**Files:**
- Modify: `tests/contracts/release/test_staging_image_publish_contract.py`

**Interfaces:**
- Consumes: `.github/workflows/publish-staging-image.yml` as text authority.
- Produces: regression assertions requiring tag reservation, incomplete-reservation monotonic advancement, and a registry existence guard before push.

- [ ] **Step 1: Write the failing contract**

Add a test that requires all of the following:

```python
def test_rc_publish_reserves_tag_and_refuses_registry_tag_reuse() -> None:
    workflow = publish_source()
    semver_section = workflow.split('      - name: Resolve Intentional SemVer Candidate\n', 1)[1].split(
        '\n  publish:\n', 1
    )[0]
    publish_section = workflow.split('\n  publish:\n', 1)[1]

    assert 'Reserved RC tag has no GitHub prerelease; its number remains consumed.' in semver_section
    assert 'Reserve RC Git Tag' in publish_section
    assert 'refs/tags/${CANDIDATE_TAG}' in publish_section
    assert '"sha": "${ACCEPTED_SHA}"' in publish_section
    assert 'Refuse Existing Registry Tag' in publish_section
    assert 'docker manifest inspect "$CANDIDATE_IMAGE"' in publish_section
    assert publish_section.index('Reserve RC Git Tag') < publish_section.index('Refuse Existing Registry Tag')
    assert publish_section.index('Refuse Existing Registry Tag') < publish_section.index('Push Exact Candidate')
```

- [ ] **Step 2: Run the focused contract and verify RED**

Run through the canonical Developer Check on the PR branch. Expected failure: the new contract cannot find tag reservation / collision-guard behavior in `publish-staging-image.yml`.

- [ ] **Step 3: Record exact RED SHA and Developer Check run in PR evidence**

The expected RED must be limited to the new #138 contract; unrelated quality failures are not acceptable evidence.

---

### Task 2: Make RC allocation monotonic across partial publication

**Files:**
- Modify: `.github/workflows/publish-staging-image.yml`
- Test: `tests/contracts/release/test_staging_image_publish_contract.py`

**Interfaces:**
- Consumes: `ACCEPTED_SHA`, `CANDIDATE_TAG`, `CANDIDATE_IMAGE`, GitHub token, registry credentials.
- Produces: one reserved Git tag per attempted RC number before registry mutation; next runs consume the next number when prior reservation is incomplete.

- [ ] **Step 1: Change incomplete existing-RC handling**

When an RC tag already points at `ACCEPTED_SHA` but `/releases/tags/${existing_rc}` is missing, do not reuse it and do not stop before calculating the next RC. Emit exactly:

```bash
printf 'Reserved RC tag has no GitHub prerelease; its number remains consumed: %s\n' "$existing_rc"
```

Continue to the normal `latest_rc` scan so the reserved number contributes to monotonic allocation.

- [ ] **Step 2: Reserve the Git tag before registry mutation**

After image scan/runtime validation and before Docker registry login/push, create `refs/tags/${CANDIDATE_TAG}` against `ACCEPTED_SHA` through the GitHub REST API using the publisher job's existing `contents: write` authority. The request must fail closed if the ref cannot be created.

- [ ] **Step 3: Refuse an already-existing registry tag**

After registry login but before `docker push`, execute:

```bash
if docker manifest inspect "$CANDIDATE_IMAGE" >/dev/null 2>&1; then
  printf 'Registry tag already exists and will not be overwritten: %s\n' "$CANDIDATE_IMAGE" >&2
  exit 1
fi
```

Because the Git tag was reserved first, a collision consumes that RC number; the next intentional run advances to the next RC rather than retrying the same mutable tag.

- [ ] **Step 4: Run focused contract and canonical Developer Check**

Expected result: #138 contract GREEN and all existing route-selected checks PASS.

- [ ] **Step 5: Commit exact GREEN candidate**

Commit only the workflow, contract, and this plan; no application/runtime behavior changes.

---

### Task 3: Integrate and verify release governance

**Files:**
- No additional source files unless staging validation exposes a directly related defect.

**Interfaces:**
- Consumes: GREEN work-branch SHA.
- Produces: admitted staging SHA eligible for a fresh intentional RC cut.

- [ ] **Step 1: Merge PR to `kaori/staging` only after Developer Check PASS**

Preserve exact reviewed head SHA in merge evidence.

- [ ] **Step 2: Require fresh staging Full Admission**

Do not reuse run `33814353368` because the workflow changes after #138 merge.

- [ ] **Step 3: Cut a fresh intentional RC from the newly admitted staging SHA**

The new run must allocate a candidate number greater than the already consumed `v0.1.0-rc.6` and must not overwrite any existing registry tag.

- [ ] **Step 4: Verify immutable artifact evidence**

Record candidate tag, exact source SHA, image digest, publisher run, and Full Admission run.

- [ ] **Step 5: Resume Issue #50 UAT deployment**

Move `kaori/uat-request` only to the exact admitted source represented by the new non-colliding RC, then verify Compose edge, DNS, TLS, HTTPS readiness, private-port exposure, and human UAT gate.

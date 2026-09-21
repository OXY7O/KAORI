# KAORI CI, Delivery, Deployment, and Recovery Contract

This document defines the operational contract for KAORI delivery and recovery. Existing workflows, release-state tooling, and repository verifiers remain the executable authorities; this document does not introduce a parallel pipeline.

## Lifecycle and authority

KAORI separates integration, delivery, deployment, and production promotion deliberately.

| Stage | Transition | Required authority | Result |
| --- | --- | --- | --- |
| Continuous Integration | issue branch -> PR | Developer Check on the exact PR head | source is eligible for staging review |
| Staging admission | PR -> `kaori/staging` | synchronized branch plus exact-head Developer Check, followed by `quality.yml` Full Admission on the exact staging SHA | staging SHA is admitted |
| Continuous Delivery | admitted staging SHA -> immutable release candidate | release-candidate workflow, release governance, OCI digest identity, SBOM/provenance/signature evidence | deployable release evidence exists; production has not advanced |
| Governed deployment | immutable RC -> UAT/staging host | staging deployment workflow plus release-state and deployment evidence | exact digest is running in the governed non-production target |
| Production promotion | accepted UAT -> production | explicit human UAT acceptance, immutable digest/transition lineage, promotion governance, smoke and post-promotion verification | production release state may advance |

`quality.yml`, release-candidate publication, staging deployment, promotion, release governance, and existing delivery verifiers are the only pipeline authorities. Documentation, comments, labels, or a previously green run never substitute for exact-source evidence.

## Continuous Integration

CI proves the exact source under review. Required evidence includes the repository-owned static/governance checks, security checks, functional/integration tests, frontend reproducibility, production-image runtime validation/DAST, and admission aggregation already implemented by `quality.yml` and the canonical quality-gate scripts.

A PR must not enter `kaori/staging` unless its branch is synchronized with current staging and the required Developer Check is green on that exact head SHA. After merge, staging Full Admission must be green on the exact resulting staging SHA before that SHA can be used as delivery evidence.

## Continuous Delivery

Continuous Delivery begins only from an admitted staging SHA. It produces an immutable release candidate and digest-bound release evidence suitable for deployment. Delivery does **not** imply production rollout.

The release candidate must preserve source SHA, release version, OCI digest, SBOM, provenance, signature/verification evidence, and transition lineage. Tags are references; the captured digest is the deployable identity. Old tags or digests are never mutated to manufacture a new release lineage.

## Continuous Deployment

Automatic deployment is allowed only for environments whose governance explicitly permits it. Production is not such an environment under the current KAORI contract.

Production remains policy-controlled and human-UAT-gated. A workflow being technically capable of deployment is not authority to promote. Promotion requires explicit acceptance plus the repository's existing release-governance, transition, smoke, and post-promotion integrity evidence.

## Release-state transaction boundary

Release state advances only after the target deployment has satisfied the required deployment and verification contract. A failed, cancelled, or partially completed deployment must leave the previously accepted release state authoritative.

The server deployment adapter and `deploy/server/release-state.sh` own runtime identity validation. Release state must identify a digest-qualified image together with its version, source SHA, and build/deployment metadata. A mutable tag alone is insufficient evidence.

No failure handler may mark a failed deployment as accepted merely to make a retry possible. Retry must either safely reuse the same immutable candidate or create a fresh admitted candidate according to the existing release workflow.

## Rollback contract

Rollback is a coordinated application-and-data transaction, not an image-only operation. `deploy/server/rollback.sh` is the executable authority and must fail closed unless the operator supplies the previous immutable image together with the corresponding source SHA, release version, and reviewed pre-migration database backup required by that release transition.

Rollback is appropriate only when all of the following are true:

- the previous application image is immutable and its identity is known;
- the matching reviewed backup/source/version lineage is available;
- restoring the previous database state is safe for the incident and data-loss window;
- external/API consumers will remain compatible with the restored state;
- the rollback path itself has not been invalidated by irreversible external side effects.

The recovery sequence is conceptually one transaction: validate previous release identity and backup -> restore reviewed database state -> deploy the previous immutable image -> verify readiness/smoke -> record recovery evidence. An image-only rollback is prohibited.

## Roll-forward contract

Roll-forward is preferred when restoring old state is unsafe or would discard/contradict valid data, schema, API, or external-system changes. Typical triggers include irreversible migrations, accepted writes after deployment, incompatible downstream state, or a defect whose safest correction is an admitted patch.

A roll-forward must:

1. create the corrective change on a governed issue branch;
2. receive fresh exact-head Developer Check evidence;
3. merge through `kaori/staging` and receive fresh Full Admission on the resulting staging SHA;
4. publish a new immutable release candidate with a new lineage identity;
5. deploy and verify that new candidate through the normal governed path;
6. obtain the same human acceptance required for production promotion;
7. preserve old tags, digests, evidence, and transition records unchanged.

A roll-forward is never permission to retag an old digest, edit prior evidence, skip admission, or mutate an already published release.

## Rollback versus roll-forward decision

| Condition | Default recovery |
| --- | --- |
| clean pre-migration backup exists and restoring it is safe | rollback may be used |
| image rollback would require keeping a newer incompatible schema/data state | roll-forward |
| irreversible migration or external side effect occurred | roll-forward |
| valid production writes would be lost beyond the accepted recovery window | roll-forward |
| previous image + matching reviewed backup/source/version cannot be proven | roll-forward |
| defect is isolated to application behavior and complete prior transaction state is safely restorable | rollback may be used |

When uncertain, do not perform an image-only rollback. Preserve the current evidence, stop promotion, and prepare a newly admitted roll-forward candidate.

## Failure and retry invariants

- No failed deployment may silently advance release state.
- No stage may bypass exact-SHA admission evidence.
- No promotion may replace digest identity with a mutable tag-only assertion.
- No recovery may rewrite historical release evidence.
- Reusing an immutable candidate is allowed only when the existing workflow's identity checks prove that candidate belongs to the same source/version lineage.
- A new source SHA requires fresh admission and a new candidate lineage.
- Smoke and post-promotion integrity checks remain required after production transition.

## CDEvents relationship

Issue #440 tracks CDEvents standardization for delivery-event observability. CDEvents are an observability representation of delivery transitions; they do not become an authorization plane. An emitted event may describe CI admission, candidate publication, deployment, UAT acceptance, promotion, rollback, or roll-forward, but it cannot replace the workflow/verifier evidence that authorizes those transitions. `docs/architecture/cdevents-delivery-lineage.md` is the pinned CDEvents vocabulary, identity, trust, retry/idempotency, sensitive-data, and failure-semantics authority.

## Operational drill

A recovery drill should prove, without weakening production controls, that operators can identify the active digest/source/version, locate the corresponding previous immutable release and reviewed backup, explain whether rollback is safe, and otherwise prepare a fresh roll-forward path. Drill evidence should record the decision and references used; it must not mutate historical release identity.

## Related authorities

- `.github/workflows/quality.yml`
- release-candidate and staging deployment workflows under `.github/workflows/`
- `deploy/server/release-state.sh`
- `deploy/server/rollback.sh`
- `docs/deployment/RELEASE_GOVERNANCE.md`
- `docs/setup/GITHUB_ACTIONS_CI_CD.md`
- `docs/architecture/cdevents-delivery-lineage.md`
- existing release-governance, delivery, and final-release verifiers under `scripts/`

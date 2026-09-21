# KAORI CDEvents Delivery Lineage Architecture

**Status:** CURRENT — architecture contract for #440 / #529  
**Scope:** delivery observability and interoperability  
**Authority boundary:** observational evidence only; existing KAORI delivery/release controls remain authoritative

## Purpose

KAORI uses CDEvents to describe delivery lineage consistently across source change, CI, build, immutable artifact publication, UAT deployment, rollback, and stable promotion. The event stream is evidence for observability, provenance exploration, and later Delivery Intelligence. It is not a command or authorization plane.

**CDEvents cannot authorize** a merge, admission decision, deployment, rollback, UAT acceptance, or stable promotion. Those transitions remain controlled by the existing exact-SHA, immutable-digest, release-state, human-acceptance, rollback, and promotion authorities.

This architecture introduces **no broker**, receiver, persistence model, workflow behavior, deployment behavior, or UI. Later #440 children implement those bounded capabilities against this contract.

## Specification pin and binding authority

KAORI pins the Phase 1 contract to **CDEvents v0.5.0** from the upstream `cdevents/spec` tag `v0.5.0`.

The version surfaces are deliberately distinct:

| Surface | KAORI pin | Meaning |
| --- | --- | --- |
| CDEvents specification release | `v0.5.0` | repository/tag and schema set reviewed by KAORI |
| CDEvents `context.specversion` | `0.5.0` | version carried inside the CDEvent payload |
| CloudEvents specversion | `1.0` | transport-envelope version when the CloudEvents binding is used |
| Event-type suffix | schema-specific | vocabulary version for that event type; it is not the specification release number |

The upstream v0.5.0 CloudEvents binding maps CDEvents context into CloudEvents 1.0 and keeps the complete CDEvent JSON as event data. KAORI therefore never derives a CDEvents version from the CloudEvents envelope or assumes that an event-type suffix must equal `0.5.0`.

### Upstream authority precedence

When upstream prose, examples, and machine schemas disagree, KAORI resolves the pinned contract in this order:

1. exact upstream tag `v0.5.0` and its `version.txt`;
2. the v0.5.0 JSON schema for the concrete event type;
3. `cloudevents-binding.md` for the CloudEvents mapping;
4. explanatory prose/examples.

This is intentional because the tagged prose may retain historical wording while the tag, schemas, and binding define the reviewed machine contract. Do not follow the upstream default branch implicitly.

Canonical upstream references:

- `https://github.com/cdevents/spec/tree/v0.5.0`
- `https://github.com/cdevents/spec/blob/v0.5.0/cloudevents-binding.md`
- `https://github.com/cdevents/spec/tree/v0.5.0/schemas`

## Initial KAORI event map

Only emit an event after the represented predicate actually occurred. Do not manufacture a success event from intent, a queued operation, a mutable tag, or a missing downstream observation.

| Delivery occurrence | CDEvents type | Intended KAORI producer boundary |
| --- | --- | --- |
| change created | `dev.cdevents.change.created.0.4.0` | governed GitHub change boundary when a reliable producer is introduced |
| change updated | `dev.cdevents.change.updated.0.3.0` | governed GitHub change boundary |
| change reviewed | `dev.cdevents.change.reviewed.0.3.0` | governed GitHub review boundary |
| change merged | `dev.cdevents.change.merged.0.3.0` | accepted GitHub merge occurrence |
| pipeline run started | `dev.cdevents.pipelinerun.started.0.3.0` | existing KAORI CI workflow boundary |
| pipeline run finished | `dev.cdevents.pipelinerun.finished.0.3.0` | existing KAORI CI terminal outcome |
| build started | `dev.cdevents.build.started.0.3.0` | real production-image build boundary |
| build finished | `dev.cdevents.build.finished.0.3.0` | real production-image build terminal outcome |
| artifact packaged | `dev.cdevents.artifact.packaged.0.3.0` | immutable image/digest exists and packaging evidence exists |
| artifact published | `dev.cdevents.artifact.published.0.3.0` | immutable digest is present in the governed registry |
| artifact signed | `dev.cdevents.artifact.signed.0.3.0` | signature evidence has actually been produced |
| service deployed | `dev.cdevents.service.deployed.0.3.0` | first successful deployment of the exact digest to the logical environment |
| service upgraded | `dev.cdevents.service.upgraded.0.3.0` | successful replacement by a different exact digest |
| service rolled back | `dev.cdevents.service.rolledback.0.3.0` | governed rollback actually completed |

`dev.cdevents.service.published.0.3.0` is reserved for a later explicit public-publication producer if needed. It must remain distinct from application `service.deployed` / `service.upgraded` evidence so the #496/#527 shared-edge boundary is preserved. A public-edge publication failure is not an application deployment rollback.

Stable promotion may emit another artifact occurrence only when the corresponding CDEvents predicate genuinely occurs. A stable tag must not create a new artifact identity or imply a rebuild. KAORI stable promotion continues to reuse the accepted RC digest.

## Canonical identity model

Identity fields are normalized before any event is retained. A display label, mutable branch/tag, user-entered description, or free-form log line is never an identity authority.

### Repository identity

- Subject repository ID: `OXY7O/KAORI`.
- Canonical repository URI: `https://github.com/OXY7O/KAORI`.
- Repository ownership is immutable input to every KAORI delivery identity.

### Change identity

A GitHub Pull Request is represented as `pull/<number>` within the canonical repository identity. The PR number is stable; title/body text is descriptive metadata and is not copied into retained event evidence by default.

Issue number, branch name, and review URLs may be allowlisted as references where useful, but they do not replace the change subject ID.

### Source SHA

The **Source SHA** is the exact 40-character Git commit SHA validated by the governing workflow. It remains the source-code identity carried through admission, RC, deployment, and stable promotion.

The **commit SHA is not a chain ID**. It is stored as source identity and may participate as an input to deterministic correlation, but `chainId` remains a UUID.

### Workflow run identity

A GitHub Actions occurrence uses:

`github-actions/<workflow-file>/<run-id>/attempt/<run-attempt>`

The run ID identifies the Actions run and the attempt distinguishes reruns. Workflow name alone, job name alone, or a branch name is insufficient.

### Event ID

Every retained **Event ID** is a deterministic UUIDv5 derived from:

`producer-source | event-type | subject-id | authoritative-occurrence-key`

The occurrence key is based only on reviewed immutable identifiers, for example workflow run/attempt, exact source SHA, digest, environment ID, or release transition identity. It never includes a secret or mutable human description.

A retransmission of the same occurrence reuses the same Event ID and original occurrence timestamp. A genuine workflow rerun is a new occurrence and therefore receives a new Event ID because its run attempt is different.

### chainId

KAORI requires `chainId` even though upstream v0.5.0 treats it as optional. KAORI `chainId` is a deterministic **UUIDv5** derived from the canonical repository identity and exact delivery source SHA.

Consequences:

- all pipeline/build/artifact/deployment/promotion events for the same exact delivery source SHA share the same `chainId`;
- a new source SHA creates a new delivery chain;
- workflow retries/reruns for the same source SHA stay in the same chain but have distinct Event IDs when they are distinct occurrences;
- pre-merge change events may have change-local source SHA chains; the accepted merge/integration source establishes the artifact/deployment chain;
- later query logic must use explicit subject/source links rather than pretending different source SHAs are one chain.

The implementation child must use one repository-owned UUID namespace constant. Changing that namespace is a versioned compatibility change.

### RC identity

The **RC identity** is the governed `vX.Y.Z-rc.N` candidate tag together with its exact Source SHA and immutable OCI digest. The tag is useful release metadata but is not sufficient by itself.

### Artifact identity and OCI PURL

The artifact subject uses a canonical **OCI PURL** whose version component identifies the immutable digest, following the CDEvents v0.5.0 artifact vocabulary. The digest remains the release authority.

Example shape:

`pkg:oci/kaori@sha256%3A<digest>?repository_url=<registry-repository>`

The exact registry/repository qualifier is normalized by the future reusable emitter. A **mutable tag is never artifact authority**.

### UAT environment

The logical **UAT environment** identity is `kaori/uat/vps`. Its public URL may be retained as safe descriptive evidence, but `https://kaori.cloud` does not replace the logical environment ID.

Application deployment identity ends at the KAORI runtime boundary. Standalone shared-edge publication remains separate infrastructure evidence.

### Stable release identity

The **Stable release identity** is the Semantic Versioning stable release/tag plus the previously accepted RC Source SHA and the **same immutable OCI digest**. Stable promotion must not assign a new artifact identity to identical application bits.

## Retry, retransmission, deduplication, and idempotency

CDEvents evidence must be safe under GitHub Actions retries and later transport redelivery.

Rules:

1. **Retransmission** of the same occurrence keeps `context.id`, `context.timestamp`, `context.source`, event type, subject identity, and `chainId` unchanged.
2. A GitHub **retry/rerun** with a new run attempt is a new pipeline/build occurrence. It gets a new Event ID but retains the same `chainId` when Source SHA is unchanged.
3. Artifact events reuse the same OCI PURL for the same digest. Retrying publication or validation must not manufacture another artifact identity.
4. Later persistence performs **deduplication** primarily by `context.source + context.id`; exact duplicates are idempotent.
5. Duplicate or out-of-order evidence must never infer a successful predicate that was not observed.
6. Conflicting events for the same immutable occurrence are rejected rather than resolved by "last write wins".
7. Stable promotion of the same accepted digest is an idempotency-sensitive transition; it must never rebuild or silently move historical identity.

## CloudEvents binding

When CDEvents are transported through CloudEvents, KAORI follows the pinned v0.5.0 binding:

- CloudEvents `specversion = 1.0`;
- CloudEvents `id` = CDEvents `context.id`;
- CloudEvents `source` = CDEvents `context.source`;
- CloudEvents `type` = CDEvents `context.type`;
- CloudEvents `subject` = CDEvents `subject.id`;
- CloudEvents `time` = CDEvents `context.timestamp`;
- event data contains the complete schema-valid CDEvent JSON.

Phase 1 does not require network transport. Structured evidence retained as workflow artifacts may stay as validated CDEvent JSON until a receiver exists.

## Producer trust

**Producer trust** is allowlist-based. A payload is not trusted merely because its fields look like a CDEvent.

Accepted Phase 1 producer classes are:

- repository-owned GitHub Actions running a reviewed workflow from the exact source authority;
- repository-owned release/deployment tooling after it has verified the exact source/version/digest lineage it already governs.

Future receivers must validate producer/source identity before accepting an event. A user-provided webhook payload, arbitrary fork workflow, external comment, issue/PR body, or unreviewed runtime script is not a trusted producer.

The canonical `context.source` must identify the KAORI producer boundary using a repository-owned URI. Producer identity and subject/source identities must never be taken directly from untrusted request fields.

## Sensitive-data exclusion

**Sensitive-data exclusion** is fail-safe and deny-by-default. Delivery events retain normalized identifiers and outcomes, not raw runtime context.

Never retain or transport:

- `github.token`, raw `secrets`, or a full serialized GitHub context;
- passwords, database URL credentials, DSNs containing credentials, API keys, OAuth tokens, session cookies, or bearer headers;
- SSH private key material, including `KAORI_HOST_SSH_PRIVATE_KEY`, SSH passphrases, or credential-agent output;
- kubeconfig content, Kubernetes bearer tokens, client private keys, cloud credentials, or registry passwords;
- environment dumps or command output that may contain secret values;
- raw issue/PR body text, commit-message bodies, or user-entered descriptions unless a later explicit allowlist proves they are required and safe.

URLs retained as evidence must have credentials and secret-bearing query parameters removed.

### customData

`customData` is empty by default. A producer may populate it only from a reviewed field allowlist for that event type. Arbitrary `github`, `env`, webhook, process-environment, or user-supplied objects must never be copied wholesale.

Safe examples include exact source SHA, normalized workflow run/attempt, normalized RC version, immutable digest, stable environment ID, and a non-secret evidence URL.

## Failure semantics

CDEvents evidence has two different failure classes and they must not be conflated.

### Producer-side validation — fail closed

If a governed producer declares CDEvents evidence required for its boundary, failure to construct a schema-valid event, deterministic identity, or sensitive-data-safe payload must **fail closed** for that evidence-producing stage. The workflow must not label malformed/missing evidence as successful or write a partial event that could later be interpreted as truth.

This failure does not grant or revoke release authority by itself. Existing KAORI quality/release checks remain the authority; the event contract is an additional evidence invariant at the producer boundary.

### Non-authoritative consumer / transport failure

A downstream **non-authoritative consumer**, receiver, broker, indexer, dashboard, or Delivery Intelligence surface must not become a hidden release dependency.

If schema-valid evidence has already been produced/retained and a later transport or consumer is unavailable:

- do not rewrite CI/admission/deployment/release state;
- do not emit a synthetic success;
- do not roll back the application solely because observability delivery failed;
- preserve retryable evidence and report the observability degradation separately.

This is why Phase 1 has **no broker** requirement. Any future mandatory receiver changes the delivery dependency graph and requires a separate governance decision.

## Source-of-truth separation

CDEvents mirrors authoritative facts; it does not replace them.

| Fact | Existing authority |
| --- | --- |
| exact source admission | Developer Check / Full Admission evidence |
| RC source/version/digest | release-candidate workflow and release evidence |
| OCI artifact identity | immutable registry digest and verified OCI evidence |
| UAT runtime state | deployment/release-state tooling and verification |
| public shared-edge publication | standalone shared-edge authority |
| human UAT acceptance | explicit acceptance evidence |
| stable promotion | release governance and same-digest promotion |
| rollback transaction | reviewed image/source/version/backup lineage |

Consumers must treat missing events as unknown/incomplete, never as success.

## Version upgrade and compatibility policy

A **version upgrade** from CDEvents v0.5.0 is a governed compatibility change.

Every upgrade requires:

1. a dedicated Issue and reviewable PR;
2. an exact upstream tag, never an implicit default-branch dependency;
3. a diff of `version.txt`, relevant schemas, event-type versions, and CloudEvents binding;
4. explicit mapping for renamed/removed/changed required fields;
5. compatibility tests for retained historical events and current producers;
6. an updated event matrix and security review;
7. Developer Check and staging Full Admission before adoption.

Historical events remain interpreted according to the version they were produced with. Producers must not silently rewrite old event type strings or mutate retained evidence after an upgrade.

A vocabulary suffix change is reviewed separately from a CDEvents specification-release change. A CloudEvents binding upgrade is also separate.

## Implementation sequence

This document is the architecture prerequisite only.

The intended #440 dependency order is:

`architecture/identity/security -> reusable emitter/schema validation -> CI pipeline events -> RC artifact events -> deployment/rollback events -> stable-promotion events -> persistence -> query/metrics -> Delivery Intelligence UI -> end-to-end lineage validation`

Later children must extend existing KAORI quality/release authorities rather than create an ad-hoc parallel verifier or alternative release pipeline.

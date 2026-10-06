# RC Tag Reuse Guard Design

## Context

KAORI RC publication historically created durable Git/GitHub prerelease evidence only after the image had already been pushed to the registry. Publisher run `33783069100` pushed `v0.1.0-rc.6` for staging SHA `40b90b5a2c85a34a4c142a44ddecd7fb6a0bc2d9` with immutable digest `sha256:793d5140df3ec43aa1859c1aa3bcb052302dadbc03bbd243fe9cf72d89954b81`, then failed while generating release notes. Because no Git tag/GitHub prerelease survived that partial publication, the later resolver considered RC6 free.

Run `33816147707` then published the same mutable tag `v0.1.0-rc.6` for admitted staging SHA `5ab3242dbbdf3218f92218d19f76576ca17051ad` with a different immutable digest, `sha256:b2fe0323361ea02d08150bf6e0027870ac3220e3074c9d5ef2ae20e213283860`.

Both immutable digests remain historical evidence. The mutable tag collision must not be hidden or rewritten.

## Required invariant

An RC number becomes consumed **before any registry mutation can occur**.

The publisher must therefore establish durable Git authority first, then prove the registry tag is unused, then push.

## State machine

```text
admitted staging SHA
        ↓
resolve next RC number
        ↓
scan + runtime/DAST
        ↓
reserve refs/tags/vX.Y.Z-rc.N → exact staging SHA
        ↓
registry login
        ↓
assert candidate registry tag does not already exist
        ↓
push candidate image
        ↓
record immutable digest
        ↓
create GitHub prerelease using the already-reserved tag
```

If the run fails after tag reservation, the reserved Git tag is retained as historical consumed state. A subsequent intentional RC run must not reuse it; allocation advances to the next RC number.

If the registry already contains the candidate tag, the run fails before `docker push`. Because the Git tag was reserved first, the next intentional run advances rather than attempting to overwrite the same registry tag.

## Existing source idempotency

If the accepted staging SHA already owns an RC tag with a valid GitHub prerelease, the workflow remains idempotent and does not consume another RC.

If the accepted staging SHA owns one or more reserved RC tags without a GitHub prerelease, those numbers are treated as consumed/incomplete publication evidence. They are not reused. Candidate calculation continues and includes them in the latest RC number scan.

## Security and authority boundaries

- `wait-for-quality` remains GitHub-hosted with read-only contents authority.
- The self-hosted publisher retains `contents: write` because it already creates GitHub release/tag authority.
- Tag reservation uses the GitHub REST API with the workflow token; persisted Git credentials remain disabled.
- Docker registry credentials remain available only to the publisher job and continue using `--password-stdin`.
- Trivy HIGH/CRITICAL and runtime/DAST validation remain before tag reservation and registry mutation.
- No mutable `latest` tag is introduced.
- Immutable image digest remains deployment authority; mutable RC tags are discovery/history labels only.

## Incident evidence

Historical RC6 publication attempt:
- source SHA: `40b90b5a2c85a34a4c142a44ddecd7fb6a0bc2d9`
- publisher run: `33783069100`
- immutable digest: `sha256:793d5140df3ec43aa1859c1aa3bcb052302dadbc03bbd243fe9cf72d89954b81`

Current GitHub RC6 publication:
- source SHA: `5ab3242dbbdf3218f92218d19f76576ca17051ad`
- publisher run: `33816147707`
- immutable digest: `sha256:b2fe0323361ea02d08150bf6e0027870ac3220e3074c9d5ef2ae20e213283860`

Neither immutable digest may be rewritten. Future release evidence must explicitly use the digest corresponding to its accepted source SHA.

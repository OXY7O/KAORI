# RC6 Collision Reconciliation

## Purpose

Preserve exact evidence for the `v0.1.0-rc.6` mutable-tag collision discovered while continuing Issue #50 UAT preparation. This record does not alter either immutable image digest.

## Historical publication attempt

- Workflow run: `33783069100`
- Accepted staging SHA: `40b90b5a2c85a34a4c142a44ddecd7fb6a0bc2d9`
- Candidate tag: `v0.1.0-rc.6`
- Registry digest after push: `sha256:793d5140df3ec43aa1859c1aa3bcb052302dadbc03bbd243fe9cf72d89954b81`
- Registry evidence artifact: `staging-image-40b90b5a2c85a34a4c142a44ddecd7fb6a0bc2d9`
- Failure: release-note generation exited `141` after image publication; GitHub prerelease creation was skipped.

## Later complete publication

- Workflow run: `33816147707`
- Accepted staging SHA: `5ab3242dbbdf3218f92218d19f76576ca17051ad`
- Candidate tag: `v0.1.0-rc.6`
- GitHub prerelease: `KAORI v0.1.0-rc.6`
- Registry digest: `sha256:b2fe0323361ea02d08150bf6e0027870ac3220e3074c9d5ef2ae20e213283860`

## Interpretation

The mutable Docker tag `v0.1.0-rc.6` was reused for two different admitted source revisions. The current GitHub prerelease and current mutable registry tag represent the later SHA/digest pair. The earlier immutable digest remains historical evidence and must never be presented as the digest of the current GitHub RC6 prerelease.

## Forward rule

After Issue #138 merges, an RC tag is reserved in Git before registry mutation and an existing registry tag is rejected before push. A partial publication therefore consumes an RC number permanently, and a retry advances to the next candidate number.

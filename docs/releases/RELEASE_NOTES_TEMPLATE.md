# KAORI vX.Y.Z

Accepted RC: vX.Y.Z-rc.N
Human UAT evidence: https://github.com/OXY7O/KAORI/issues/ISSUE#issuecomment-COMMENT

## Highlights

- Summarize the primary user-visible outcome of this accepted release.

## Improvements

- Describe the meaningful capability or workflow changes.

## Fixes

- Describe the important fixes, or explicitly state that there were none.

## Known Limitations

- Record relevant limitations or explicitly state that none are known.

---

This is a **template**, not an accepted release or Human UAT record. The referenced KAORI issue comment must exist, have a human repository owner/member author, and contain exactly one `KAORI_APP_UAT_ACCEPTED:<source SHA>:<RC tag>:<OCI digest>` marker for the approved signed artifact. A syntactically valid URL is insufficient. After real UAT, create a reviewed, version-specific file such as `docs/releases/KAORI_0_3_0.md`; use the exact accepted RC and an actual Human Acceptance issue-comment link. The stable release workflow verifies the notes on protected `main` before privileged publication and appends signed OCI/approval evidence automatically.

Do not create a dated stable `CHANGELOG.md` entry until the corresponding stable release actually exists. Keep accepted changes under `[Unreleased]` while the release is pending.

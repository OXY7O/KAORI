# KAORI vX.Y.Z

Accepted RC: vX.Y.Z-rc.N
Human UAT evidence: https://github.com/OXY7O/KAORI/issues/ISSUE#issuecomment-COMMENT

## Highlights

- Summarize one to three verified outcomes users can recognize. Explain who benefits and why the release matters; do not paste commit or PR titles.

## Improvements

- Describe meaningful new capabilities or workflow improvements in ordinary language and their operational impact.
- Explain relevant security, compatibility, migration or configuration changes; state explicitly when none apply.

## Fixes

- Explain user-relevant bugs or reliability/security issues fixed and the observable result; explicitly state if no fixes are included.

## Known Limitations

- Describe known limitations, upgrade/rollback considerations and workarounds, or state that none are known.

---

This is a **template**, not an accepted release or Human UAT record. The referenced KAORI issue comment must exist, have a human repository owner/member author, and contain exactly one `KAORI_APP_UAT_ACCEPTED:<source SHA>:<RC tag>:<OCI digest>` marker for the approved signed artifact. A syntactically valid URL is insufficient. After real UAT, create a reviewed, version-specific file such as `docs/releases/KAORI_0_3_0.md`; use the exact accepted RC and an actual Human Acceptance issue-comment link. The stable release workflow verifies the notes on protected `main` before privileged publication and appends signed OCI/approval evidence automatically.

Do not create a dated stable `CHANGELOG.md` entry until the corresponding stable release actually exists. Keep accepted changes under `[Unreleased]` while the release is pending.

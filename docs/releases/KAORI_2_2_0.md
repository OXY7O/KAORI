# KAORI 2.2.0 Release Notes

**Release date:** 2026-08-11  
**Git tag:** `v2.2.0`  
**Release type:** Minor release  
**Status:** Approved release baseline

## Summary

KAORI 2.2.0 consolidates the pre-release hardening cycle into a controlled release baseline. The release keeps the existing product contracts backward-compatible while adding deterministic release-surface coverage, final-lock evidence across reviewed operational domains, stronger runtime/test isolation, and narrower security and failure boundaries.

## Release Focus

### Deterministic final release gate

- `python scripts/verify_final_release.py --all --runtime` is the canonical final approval command.
- Release ownership covers 49 authenticated navigation links and 21 registered Flask Blueprints.
- Static quality, full tests, frontend formatting, endpoint registration, and Reports worker readiness are evaluated from one release entry point.
- Successful verifier output remains concise (`PASS — KAORI <Area>`); failures retain actionable diagnostics.

### Locked operational surfaces

The current release baseline protects the reviewed Welcome, Dashboard, Kubernetes Inventory, Kubernetes Governance, Kubernetes Operations, Kubernetes Analytics, Reports, Integrations, Platform Operations, Access, Settings, Authentication, and Notification surfaces with permanent contracts/verifiers.

Intelligence is **baseline-locked rather than feature-complete**. Kubernetes evidence/read surfaces remain available, while unfinished Server/HCI and Automation Control mutation paths remain explicitly Reserved Plan / fail-closed.

### Runtime, security, and test hardening

- Authorization-sensitive Inventory, Governance, and Kubernetes Operations readiness checks execute after route RBAC.
- Protected Secret Reveal and TLS governance retain minimized evidence and controlled mutation boundaries.
- Reports storage/runtime behavior is fail-fast and sanitized for disconnected S3-compatible storage.
- Analytics capability and dependency failures use canonical, operator-safe failure envelopes.
- Test prerequisites, unique module naming, and restore-safe module isolation prevent collection/session contamination.
- Code-health ceilings remain bounded rather than being raised to absorb release debt.

## Compatibility

This is a backward-compatible minor release. Existing deployment contracts continue to use `APP_VERSION`, `APP_BUILD_SHA`, and `APP_BUILD_DATE`; provider compatibility remains governed by the canonical Kubernetes, Prometheus, Alertmanager, and Thanos Query profiles shown in System Information.

## Continuing Work

Detailed technical test expansion, script refinement, and documentation maintenance continue in subsequent releases. New defects should be addressed through the narrowest owning domain and accompanied by updated tests, verifier evidence, and documentation rather than broad release-scope changes.

Feature work that is intentionally incomplete remains outside the 2.2.0 feature-complete claim and should preserve the locked baseline until its own scoped review is approved.

## Release Verification

Before tagging the release commit, run:

```bash
python scripts/verify_final_release.py --all --runtime
```

The release is approved only when the command ends with:

```text
PASS — KAORI Final Release
```

After the release metadata commit is created, tag that exact commit:

```bash
git tag -a v2.2.0 -m "KAORI 2.2.0"
git show --no-patch --decorate v2.2.0
```

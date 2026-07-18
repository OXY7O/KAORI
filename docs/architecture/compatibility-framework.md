# Compatibility Framework

Compatibility profiles translate detected provider versions and behavior into a stable KAORI support contract.

## Purpose

A profile documents:

- supported version range;
- supported APIs;
- capability expectations;
- known limitations;
- deprecations; and
- KAORI support posture.

## Separation from capability

Compatibility is a profile-level expectation. Capability is observed runtime evidence.

Example:

```text
Compatibility profile
alertmanager-v0-33

Observed capabilities
status_v2, alerts_v2, silences_v2, fingerprint
```

A compatible profile may still be unhealthy because the endpoint is currently unreachable. A healthy endpoint may still have degraded feature readiness because optional metadata is absent.

## Registry pattern

Provider profiles should be isolated from service branching:

```text
app/<provider>/profiles/
├── __init__.py
├── base.py
└── <profile>.py
```

Adding a provider version should normally add or update a profile rather than introduce scattered version comparisons in routes, services, readers, or analytics.

## Profile selection

```text
Detect version and behavior
        ↓
Select the most specific supported profile
        ↓
Record compatibility status and limitations
        ↓
Discover actual capabilities
```

Unknown future versions must not automatically be declared fully compatible. They may be treated as unverified while basic API evidence remains available.

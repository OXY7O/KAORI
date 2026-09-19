# Domain 20 — Production Readiness & Controlled Rollout Closure

## Purpose

Domain 20 closes the remediation foundation with auditable evidence and staged rollout. It does not automatically enable production mutation.

## Required evidence

Every cluster/action pair must prove architecture boundaries, functional and contract tests, migration upgrade/downgrade, web/worker registry parity, Kubernetes RBAC, API-server dry-run, duplicate-delivery safety, worker-loss recovery, optimistic-lock conflict handling, kill switch, maintenance mode, circuit breaker, recovery/compensating-action drill, and Activity Audit coverage.

Evidence is canonicalized and hashed. Changing any result invalidates prior approval.

## Rollout stages

`disabled → shadow → non_production → canary → production`

Stages advance one step at a time. Canary and production require all checks to pass. A ResolverDeploymentPolicy must already be active. Migration defaults every record to `disabled` and does not alter the global kill switch.

### Shadow

Alert matching, candidate creation, promotion review, and dry-run evidence may be evaluated, but no provider mutation is allowed by rollout policy.

### Non-production

Mutation is permitted only for explicitly designated non-production clusters and namespaces.

### Canary

A narrowly scoped production action may run under concurrency 1, strict rate limits, and an immediately available kill switch.

### Production

Production approval records actor and timestamp. Execution remains subject to Domain 17 deployment policy and Domain 19 operational controls.

## Runtime enforcement order

Resolver execution workers enforce the complete safety chain before acquiring an
execution lease:

1. the decision must identify an existing cluster;
2. the action must exist in the process registry;
3. an active cluster/action deployment policy must allow the target namespace;
4. the policy fingerprint must match the worker registry fingerprint;
5. the readiness record must be in an executable rollout stage;
6. `non_production` may not execute against a `production` cluster;
7. kill switch, maintenance, concurrency, rate, and circuit-breaker controls must pass;
8. only then may KAORI acquire the distributed lease and dispatch the resolver.

This order prevents an invalid task from becoming `running` before governance and
operational gates are evaluated.

## Threat and failure model

The acceptance bundle must test stale resourceVersion, service-account denial, registry mismatch, replayed authorization, duplicate Celery delivery, worker loss after lease, post-condition failure, database interruption, alert storm, open circuit, and recovery/compensating-action evidence preservation.

## Rollback drill

Before production approval, operators must demonstrate: activate kill switch, disable deployment policy, stop execution consumers, classify queued/running journals, preserve audit evidence, revert application release, downgrade migration only when no active execution remains, and verify Kubernetes target state independently.

## Deployment topology

Use separate deployments for web, normal workers, resolver execution, resolver maintenance, and beat. Resolver execution workers must consume only `resolver-execution`; maintenance workers must consume only `resolver-maintenance`.

## Closure decision

After this domain, new work is not another foundation domain. UI authoring/review screens and additional resolver actions are capability sprints built on Domains 8–20.

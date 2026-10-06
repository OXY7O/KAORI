# Prometheus Style and Lifecycle Audit — July 2026

## Scope

This audit covers the complete Prometheus integration experience:

- Integrations → Prometheus landing and connection registry;
- Register and Edit Prometheus Connection;
- Prometheus Instance Manage;
- Prometheus Instances & Bindings;
- cluster-bound Prometheus Configuration;
- Validation & Analytics;
- Runtime & History;
- Scope & Resolution;
- instance and binding lifecycle actions.

The audit uses the current KAORI Violet design system and Alertmanager Manage workspace as the closest provider-neutral reference.

## Findings

### 1. Registered instances had no governed delete lifecycle

The UI allowed binding removal but did not provide an instance deletion route, service boundary, confirmation modal, or Activity Audit event. Operators therefore could not remove an obsolete registered Prometheus connection through KAORI.

### 2. Disabled bindings could be hidden from lifecycle checks

Administrative binding retrieval previously returned enabled bindings only. A disabled binding could remain in the database while the UI appeared clear, which is unsafe for destructive lifecycle actions.

### 3. Prometheus Manage used mixed workspace styling

The instance and cluster workspaces did not consistently use:

- the shared tab treatment;
- three peer-level Violet workspace summaries;
- the primary Info Flow standard;
- the shared Health Interpretation component.

This made Prometheus feel older and structurally different from the standardized Alertmanager workspace.

### 4. Runtime interpretation duplicated provider-local markup

Prometheus maintained its own health score and diagnostic presentation. This duplicated the global runtime interpretation contract and made future changes inconsistent across providers.

### 5. Binding deletion relied on a browser confirmation pattern

The binding workspace needed the same accessible critical modal used by other KAORI destructive actions. Browser `confirm()` behavior is not an acceptable design-system control.

### 6. Several labels and helper strings were stale

Examples included `Run Validation`, `100-record Retention`, and older hero title weight. These were normalized to current Full Validation terminology, Title Case, and semibold hero hierarchy.

## Implementation

### Provider landing and registry

- retained the standardized Hero Context Panel and HTMX registry;
- retained global pagination choices `5`, `10`, `25`, and `50` on the connection registry;
- normalized hero title weight and Full Validation wording;
- kept delete actions out of the landing page because destructive lifecycle actions require instance context.

### Register and Edit Connection

- uses the shared Operational Toggle and Form Action Bar standards;
- uses primary `Info Flow` for the Prometheus Integration Flow;
- preserves Related Page Card placement on the contextual subpage;
- keeps connection registration separate from Full Validation and scope assignment.

### Instance Manage

All four tabs now use one accessible tab contract and begin with three Violet Workspace Summary Cards.

#### Configuration

- Connection Contract;
- Change Impact;
- Integration Flow;
- primary Configuration Flow rendered with `Info Flow`.

#### Validation & Capabilities

- What Validation Does;
- Why It Matters;
- Operator Flow;
- Run Full Validation terminology throughout.

#### Runtime & History

- Readiness Versus Health;
- How Monitoring Works;
- Resolver Correlation;
- shared Health Interpretation;
- ordered Diagnostic Pipeline;
- standard runtime-history pagination and `100-Record Retention` label.

#### Scope & Resolution

- Binding;
- Eligibility;
- Resolution;
- governed Instance Lifecycle & Deletion block.

### Cluster-bound Configuration

The cluster workspace now uses the same tabs, summary rows, primary Configuration Flow, runtime interpretation, and validation semantics as instance management.

### Delete lifecycle

New route:

```text
POST /integrations/prometheus/instances/<instance_id>/delete
```

Lifecycle rules:

- all provider-neutral bindings, enabled or disabled, block deletion;
- the UI disables Delete Instance while bindings remain;
- the service repeats the blocker check;
- provider and canonical identities are removed atomically;
- runtime observation history and Activity Audit records are retained;
- success, rejection, and failure are recorded as operational activities;
- deletion has no live Prometheus or Thanos dependency.

### Confirmation pattern

Prometheus binding removal and instance deletion use one shared provider modal with:

- critical semantic treatment;
- explicit object name;
- precise consequence copy;
- Cancel and destructive confirmation actions;
- Escape and backdrop close behavior;
- focus return to the originating trigger.

## Deliberate placement decision

Delete Instance is not placed in the Hero or provider landing registry. KAORI reserves destructive lifecycle controls for the contextual instance workspace. The discoverable location is:

```text
Scope & Resolution → Instance Lifecycle & Deletion
```

This follows the global Hero action limit and keeps destructive actions adjacent to their binding blockers and authority context.

## Regression contract

- no dynamic or browser-native delete confirmation;
- no instance deletion while any scope binding remains;
- disabled bindings remain visible to administration and lifecycle checks;
- all Prometheus Manage tabs use the shared tab treatment;
- each domain has three peer Violet workspace summaries;
- primary workflows use Info Flow;
- runtime interpretation uses the shared component;
- Full Validation wording remains consistent;
- the connection registry retains standard pagination and empty-state behavior.

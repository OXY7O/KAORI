# Secret Reveal Settings

This Settings domain owns governance configuration for Protected Kubernetes Secret Reveal. It does not read Secret values and does not execute reveal requests.

## Hierarchy

```text
Cluster
└── Namespace
    └── Disabled | Step-up authentication | Approval required
```

Cluster-level fields are limited to security readiness attestations:

- Kubernetes Secret encryption at rest verified;
- Kubernetes audit logging at Metadata level verified.

Namespace policy is explicit and default-deny. No policy row means Reveal is disabled. Namespace choices come from the live Kubernetes API; existing policy records remain visible when a namespace disappears so access can still be disabled. The Add/Edit Cluster form must not contain Reveal controls.

## Ownership

- `app/kubernetes_operations/secrets/reveal_policy.py`: canonical policy and readiness rules.
- `app/settings/secret_reveal/service.py`: Settings page context and summaries.
- `app/settings/secret_reveal/routes.py`: RBAC, CSRF, activity, toast, and save actions.
- `app/templates/settings/secret_reveal/index.html`: cluster selector, readiness controls, and namespace policy table.
- `secret_reveal_namespace_policies`: one unique policy per cluster and namespace.

Every save action emits a toast/notification and Operational Activity record containing only cluster, namespace, readiness, policy, and outcome. It must never contain kubeconfig or Secret data.

## Security rules

- Permission: `kubernetes_secrets.manage_reveal`.
- `clusters.manage` does not grant access to this page.
- A namespace cannot be enabled before both cluster readiness attestations are true.
- New access cannot be granted to a namespace missing from the live Kubernetes namespace list.
- Disabling cluster readiness immediately expires pending/approved requests and suspends all namespace policies without deleting them.
- Changing or disabling a namespace policy expires pending/approved requests for that namespace.
- The global environment switch remains outside the database and is displayed read-only.

## Namespace list behavior

The namespace policy list is intentionally server-side filtered and paginated so the Settings page remains usable for clusters with large namespace inventories.

- default page size: `10`;
- supported page sizes: `10`, `25`, and `50`;
- filters: namespace text and policy state;
- pagination/filter updates use HTMX with full-page fallback;
- policy saves preserve the active search, filter, page, and page-size context;
- rows remain compact and never repeat the selected cluster name.

The canonical namespace table partial is:

```text
app/templates/settings/secret_reveal/_namespace_policy_section.html
```

Filtering and pagination are prepared by `app/settings/secret_reveal/service.py`; do not move this logic back to client-only DOM filtering because that would still render every namespace in the browser.

## Namespace table visual contract

The `Allow Reveal per Namespace` section follows the established Node Inventory table pattern so administrative tables remain visually consistent across KAORI:

- white rounded table card with a dedicated title header;
- blue entity icon and compact selected-cluster/summary labels;
- a separate slate filter band above the data table;
- uppercase slate table header;
- compact rows with entity identity, ring-based status labels, and blue hover treatment;
- rows-per-page selector in the footer, not in the filter band;
- `Previous`, page status, and `Next` controls matching Inventory pagination;
- one HTMX loading bar under the card header;
- empty states use the shared `components/states/_empty_state.html` component.

Template ownership is split as follows:

```text
app/templates/settings/secret_reveal/_namespace_policy_section.html
    card header, loading indicator, filters, and content target

app/templates/settings/secret_reveal/_namespace_policy_table_content.html
    data table, row controls, empty state, page-size selector, and pagination
```

Do not reintroduce a standalone custom table style for this section. Future namespace columns or row actions should extend the Inventory-style table contract above.
### Namespace filter and column alignment

The namespace filter band must remain a single horizontal row from the medium breakpoint upward: the namespace search expands to fill available width and the policy selector keeps a fixed compact width. Do not reintroduce a stacked desktop filter layout.

The table uses an explicit fixed column contract so row controls do not shift between pages or policy labels:

- Namespace: `31%`;
- Live Source: `15%`;
- Current Policy: `20%`;
- Configure: `34%`.

The Configure cell keeps the policy selector flexible and the Save button at a fixed width. The primary Save action uses a borderless blue button with a soft focus ring; native or dark hard outlines must not be added.


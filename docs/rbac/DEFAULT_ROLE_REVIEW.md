# Default Role Review

## 1. Current baseline summary

| Role | Permission count | Intended responsibility |
|---|---:|---|
| Viewer | 11 | General read-only operational visibility. |
| Operator | 18 | Daily operations, sync, report generation, ConfigMap changes, and controlled TLS rotation. |
| Editor | 26 | Infrastructure and integration configuration plus reporting administration. |
| Admin | 44 | Application administration and all registered permissions except direct protected secret reveal. |
| Auditor | 16 | Read-only operational, security, user, role, system, audit, and export visibility. |
| Super Admin flag | All | Emergency/platform authority outside normal role assignment. |

Counts reflect the current registry in `app/access/rbac/defaults.py` and must be revalidated whenever permissions change.

## 2. Viewer

### Current scope

Viewer can access the welcome workspace, Kubernetes dashboard, clusters, inventory, analytics, governance, TLS certificate inventory, ConfigMap values, intelligence, reports, and general settings.

### Assessment

The baseline is internally consistent and read-only.

### Clarification

`kubernetes_configmaps.view` exposes live non-secret configuration values. This is acceptable for a general Viewer only when ConfigMap content is classified as non-sensitive. Teams that store credentials or confidential application data in ConfigMaps must correct that workload design or use a narrower custom role.

### Recommendation

Keep Viewer as the broad operational read-only baseline. Do not add user directory, audit export, Secret Management, or integration configuration permissions.

## 3. Operator

### Current scope

Operator adds cluster sync, ConfigMap create/update, Secret Management view, TLS Secret rotation, TLS inventory sync, and report generation.

### Assessment

The role matches daily infrastructure operations and avoids cluster deletion, generic Secret create/replace/delete, bulk TLS rotation, user administration, and integration administration.

### Risk to monitor

TLS rotation is a high-impact mutation. The current permission is explicit, but it is not approval-gated by RBAC itself.

### Recommendation

Keep the current baseline when Operators are trusted to perform certificate rotation. Environments requiring separation of duties should clone Operator and remove `kubernetes_secrets.rotate_tls`, then use an approval-oriented custom role for certificate maintainers.

## 4. Editor

### Current scope

Editor adds cluster management, Secret create/replace, bulk TLS rotation, report template/schedule/storage management, and integration management.

### Assessment

The permission set is coherent but the name **Editor** is semantically broad. The role is effectively an infrastructure configuration administrator without user/role administration.

### Risk to monitor

`clusters.manage` includes create, edit, and delete cluster records. `integrations.manage` can alter authoritative telemetry connections. `reports.manage_storage` can perform storage verification and cleanup. These are materially different responsibilities.

### Recommendation

Do not expand Editor further. For stricter environments, prefer custom roles split into:

- Cluster Configurator;
- Integration Administrator;
- Report Administrator;
- Secret Maintainer.

A future code-owned display-name change from Editor to **Infrastructure Configurator** would improve clarity, but it should be handled as an explicit product migration rather than an incidental patch.

## 5. Admin

### Current scope

Admin receives every registered permission except `kubernetes_secrets.reveal`.

### Assessment

This preserves a useful distinction:

- Admin can configure and approve protected reveal policy;
- Admin cannot directly reveal a protected Secret value;
- Super Admin remains the explicit emergency authority for direct reveal.

User Management separately prevents a normal Admin from managing peer Admin or Super Admin accounts.

### Recommendation

Keep direct secret reveal excluded. Continue reviewing newly added permissions before allowing the Admin comprehension to include them automatically. Highly sensitive future permissions may require explicit exclusions similar to protected reveal.

## 6. Auditor

### Current scope

Auditor combines read-only infrastructure visibility with user directory view, role view, system information, Activity Audit Log view, and audit archive export.

### Assessment

The role is suitable for compliance and investigation. It does not grant mutations, retention execution, password reset, account activation, role management, integration management, or secret reveal.

### Recommendation

Keep retention execution excluded. Archive export is appropriate only if exported audit data is classified and access-controlled outside KAORI.

## 7. Super Admin

Super Admin is not a default role. It is a user authority flag with universal permission resolution and stricter account lifecycle controls.

### Recommendation

- Keep the number of active Super Admin accounts minimal.
- Maintain at least one local database break-glass Super Admin.
- Do not map SSO/LDAP JIT identities to Super Admin.
- Do not use Super Admin as a daily operations role.
- Review every Super Admin action in Activity Audit Log.

## 8. Missing default roles

No additional default role is required immediately. KAORI already supports custom roles, which is preferable to proliferating protected defaults.

Useful custom-role patterns include:

- Security Auditor;
- TLS Certificate Maintainer;
- Report Administrator;
- Integration Administrator;
- User Administrator without role administration;
- Kubernetes ConfigMap Operator;
- Secret Reveal Approver.

These should remain examples or clone-based custom profiles until repeated customer usage proves that another protected default baseline is necessary.

## 9. Gaps requiring future design

1. **Resource scope:** permissions are global; no cluster or namespace boundary exists.
2. **Separation of duties:** no policy prevents one custom role from combining request, approval, and execution permissions.
3. **Group-to-role mapping:** external identity providers currently use a default role, not ordered group rules.
4. **Time-bound access:** no temporary role assignment or expiry.
5. **Permission lifecycle:** no explicit permission deprecation/version metadata.
6. **Role change impact preview:** the editor shows selected scope but not the exact list of affected users before save.
7. **Authorization test depth:** service-level regression tests now cover seed convergence, dependency expansion, system-role immutability, delete blockers, and slug normalization; route-level authorization and UI regression coverage still need to be added.

Priority recommendation: implement scoped role bindings before adding many more global permissions.

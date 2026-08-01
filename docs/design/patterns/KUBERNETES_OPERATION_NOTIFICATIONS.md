# Kubernetes Operation Notifications


## TLS update validation gate

Single and bulk TLS Secret updates use the validated-operation contract. Update actions start disabled, successful validation enables them, and any certificate-file or target-selection change invalidates the previous validation. Bulk validation requires at least one valid selected target. Apply endpoints continue to validate server-side; the disabled action is an operator workflow guard, not the security boundary.

# Kubernetes Operation Notifications

## Validate versus mutate feedback ownership

- Validation performed through HTMX returns immediate out-of-band feedback in the same response.
- A successful mutating operation that uses `HX-Redirect` must queue its feedback before returning the redirect header.
- The redirected page consumes the queued feedback and displays the persistent KAORI toast.
- Audit and notification persistence remain part of the same `record_operational_activity` call.

This prevents successful create/update/delete operations from losing their toast during navigation while avoiding duplicate validation notifications.

# Related Resource Collection

Use `components/related_resource_collection.html` for related resources that are peers, not chronological events.

## Contract

- compact resource rows;
- primary identity plus two supporting evidence lines;
- borderless semantic status indicator;
- total count and truncation context;
- shared empty evidence;
- optional destination action.

Do not use timeline connectors for peer resources. Reference uses include Workload to Pods, Service to selected Pods, Ingress to backend Services, and Storage to mounted Pods.

## Reference-only rows

`resource.status` is optional. Omit it for factual references such as Pod to ConfigMap, Secret, or PersistentVolumeClaim. The component must not fabricate a health state when only relationship evidence is available.

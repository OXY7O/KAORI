# Analytics Capacity Analysis

Status: KAORI domain presentation standard

## Scope

Capacity Analysis is a cluster-level Ready-worker fleet workspace. It does not expose a node selector. node-level pressure belongs to Resource Utilization. Capacity uses allocatable resources from Ready worker nodes and treats control-plane nodes as context only.

## Page Structure

1. Hero with selected cluster, semantic capacity posture, the resource with the lowest headroom, and the observation window.
2. Controls and Data Readiness with Cluster and Time Range.
3. Bright Capacity Analysis Overview.
4. One tabbed workspace containing Worker Fleet Baseline, Allocation & Headroom, Capacity Risk Summary, and Capacity Recommendations.

## Unavailable Analytics Metric State

Missing capacity evidence is not zero utilization. When allocatable capacity is unavailable, KAORI displays `Unknown` and `N/A`, suppresses the progress bar, and explains that committed evidence must be restored. This contract applies to utilization, used/capacity, and headroom values.

## Semantic Color

Capacity progress bars remain KAORI Violet across Healthy, Watch, and Critical states. Semantic risk belongs to the status label and operational reading. Do not turn an entire resource lane or progress fill red, amber, or green.

## Worker Fleet Baseline

The Summary tab describes the denominator: worker count, Ready/Not Ready state, control-plane context, allocatable CPU, allocatable memory, and pod capacity. It does not repeat utilization percentages already owned by the Overview.

## Allocation & Headroom

Resource Envelope uses the shared Resource Pressure Lane. Commitment Profile remains domain-specific because its Requests, Limits, Actual Usage, and Peak Usage composition is not yet a proven cross-domain abstraction. Primary evidence is bright; How To Read and What To Do use the darker interpretation surface.

## Risk and Review Path

Resource Risk Queue and Governance Findings are bright primary evidence. Recommended Review Path is a darker guidance region and links to Workload Analysis or Storage Analysis. Navigation entries must not be mixed into the findings list.

## Loading and Runtime

Capacity is server-rendered from one committed snapshot and does not use a composite load tracker. The filter owns the page-level HTMX indicator. Capacity does not load Chart.js and has no page-specific chart runtime.

# Analytics Resource Utilization

Status: KAORI domain presentation standard

## Page Structure

1. Hero with selected cluster, concise utilization posture, highest-pressure resource, and actionable count.
2. Controls and Data Readiness with bright cluster and worker snapshot evidence.
3. Quick Resource Utilization Overview.
4. One tabbed workspace containing Summary, Trend Analysis, Node Detail, and Recommendations.

## Summary

Summary is not a duplicate KPI grid. It uses the shared Resource Pressure Lane to explain current percentage, absolute consumption, headroom, and operational reading.

## Trend Analysis

Trend Analysis loads on first activation. It contains a semantic header, four peer metrics, one bright chart evidence panel, one visible CPU/Memory/Pods legend, one bright Resource Trend Outlook, and a darker How To Read / What To Do footer. Chart behavior belongs in `app/static/js/analytics_utilization.js`.

## Node Detail

Node Detail loads on first activation. It uses a bright scope strip, shared Resource Pressure Lanes for CPU, Memory, and Pods, a bright filesystem context panel, and a darker recommended-action region.

## Recommendations

Recommendations remain a paginated bright action list. A utilization recommendation deep-links using the `tab` query parameter; hash compatibility is not supported.

## Loading

Resource Utilization does not use the Analytics Overview composite load tracker. The filter, Trend, and Node Detail own their local loading indicators. Hidden heavy tabs do not request or poll.

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CapabilityDefinition:
    key: str
    label: str
    category: str
    description: str
    required: bool = False
    probe: str = ''
    success_criteria: str = ''
    configuration_guidance: str = ''
    impact: str = ''
    remediation: tuple[str, ...] = ()


CAPABILITIES: tuple[CapabilityDefinition, ...] = (
    CapabilityDefinition(
        'status_v2',
        'Status API',
        'api',
        'Reads Alertmanager runtime, cluster, and build information.',
        True,
        'GET /api/v2/status',
        'The endpoint returns HTTP 2xx with a JSON object containing readable status data.',
        'Configure the Alertmanager base URL, authentication method, trusted TLS chain, and a timeout that permits the status request to complete.',
        'Required for connection verification, version discovery, compatibility evaluation, and runtime observation.',
        (
            'Verify that the registered URL is the Alertmanager base URL and does not already include /api/v2.',
            'Allow the KAORI runtime to reach the endpoint and port through DNS, routing, firewall, proxy, and network policy controls.',
            'Confirm the credential can read /api/v2/status and that the TLS certificate is trusted when verification is enabled.',
        ),
    ),
    CapabilityDefinition(
        'alerts_v2',
        'Alerts API',
        'api',
        'Reads active alert records from Alertmanager API v2.',
        True,
        'GET /api/v2/alerts',
        'The endpoint returns HTTP 2xx and a JSON array. An empty array is still a valid API response.',
        'Expose the Alertmanager API v2 alerts path to KAORI and ensure the selected credential or upstream proxy permits read access.',
        'Required for alert inventory, alert correlation, intelligence, and operational analytics that consume active alerts.',
        (
            'Test /api/v2/alerts from the KAORI network path using the same authentication and TLS settings.',
            'Review reverse-proxy path rewriting and make sure /api/v2/alerts is not blocked or redirected to a login page.',
            'Confirm the response content type and payload are JSON rather than HTML or another proxy-generated response.',
        ),
    ),
    CapabilityDefinition(
        'silences_v2',
        'Silences API',
        'api',
        'Reads silence inventory and lifecycle metadata.',
        True,
        'GET /api/v2/silences',
        'The endpoint returns HTTP 2xx and a JSON array. An empty array is still a valid API response.',
        'Expose the Alertmanager API v2 silences path to KAORI and permit read access through the configured authentication boundary.',
        'Required for silence visibility, governance, and correlation between alerts and suppression controls.',
        (
            'Test /api/v2/silences from the KAORI runtime using the registered connection settings.',
            'Review proxy allow-lists, authentication policy, and path rewriting for the silences endpoint.',
            'Confirm Alertmanager returns JSON and that no intermediary replaces the response with an error document.',
        ),
    ),
    CapabilityDefinition(
        'alert_labels',
        'Alert labels',
        'metadata',
        'Alert payload exposes a labels mapping.',
        True,
        'Inspect each object returned by GET /api/v2/alerts for a labels object.',
        'At least one observed alert contains a labels mapping. No active alerts can make this evidence temporarily unavailable.',
        'Ensure alert-producing rules send standard labels and that proxies or transforms do not strip the labels object.',
        'Required to classify, filter, correlate, and route alert records inside KAORI.',
        (
            'Confirm at least one representative alert is active during validation, then rerun Full Validation.',
            'Inspect the raw /api/v2/alerts payload and verify each alert includes a labels object.',
            'Correct upstream rule or payload transformation when labels are missing from active alert records.',
        ),
    ),
    CapabilityDefinition(
        'alertname_label',
        'Alert name label',
        'metadata',
        'Observed alerts include the alertname label.',
        True,
        'Inspect labels.alertname in GET /api/v2/alerts responses.',
        'At least one observed alert contains a non-empty labels.alertname value.',
        'Apply the conventional alertname label to alerting rules and preserve it through the notification pipeline.',
        'Required for stable alert identity, grouping, correlation, and source-resolution consumers.',
        (
            'Inspect active alert payloads and confirm labels.alertname is present.',
            'Update alerting rules or transformation layers that remove or rename alertname.',
            'Trigger a representative test alert and rerun Full Validation to refresh evidence.',
        ),
    ),
    CapabilityDefinition(
        'severity_label',
        'Severity label',
        'metadata',
        'Observed alerts include a severity label.',
        False,
        'Inspect labels.severity in GET /api/v2/alerts responses.',
        'At least one observed alert contains a non-empty labels.severity value.',
        'Standardize severity values in alerting rules, such as info, warning, and critical, and preserve them in downstream transformations.',
        'Improves prioritization, filtering, routing, notification policy, and intelligence quality.',
        (
            'Add a severity label to alerting rules that currently omit it.',
            'Use a controlled severity vocabulary and document its operational meaning.',
            'Trigger representative alerts for each severity and rerun Full Validation.',
        ),
    ),
    CapabilityDefinition(
        'fingerprint',
        'Fingerprint',
        'metadata',
        'Observed alerts include a stable fingerprint.',
        False,
        'Inspect the fingerprint field in GET /api/v2/alerts responses.',
        'At least one observed alert exposes a non-empty fingerprint.',
        'Use an Alertmanager API response that preserves fingerprint metadata and avoid transformations that discard it.',
        'Improves deduplication, alert lifecycle correlation, and historical intelligence.',
        (
            'Inspect the raw alerts API response for fingerprint.',
            'Review proxy, adapter, or transformation logic that may remove the field.',
            'Rerun Full Validation while representative alerts are active.',
        ),
    ),
    CapabilityDefinition(
        'starts_at',
        'Start timestamp',
        'metadata',
        'Observed alerts include startsAt.',
        False,
        'Inspect startsAt in GET /api/v2/alerts responses.',
        'At least one observed alert contains a parseable startsAt timestamp.',
        'Preserve standard Alertmanager timestamp fields in the API payload.',
        'Supports duration, ordering, aging, and temporal correlation.',
        (
            'Inspect active alert payloads for startsAt.',
            'Correct upstream or proxy transformations that strip timestamp fields.',
            'Rerun validation with an active representative alert.',
        ),
    ),
    CapabilityDefinition(
        'receiver_metadata',
        'Receiver metadata',
        'metadata',
        'Observed alerts identify their receiver.',
        False,
        'Inspect receivers or receiver metadata exposed with active alerts.',
        'At least one observed alert can be associated with a receiver.',
        'Maintain receiver metadata in the Alertmanager response path and avoid transformations that remove routing context.',
        'Improves routing analysis, ownership mapping, and notification diagnostics.',
        (
            'Confirm the alert is routed to a named receiver and inspect the API payload.',
            'Review routing configuration and adapter transformations for receiver metadata.',
            'Rerun validation after a representative routed alert is available.',
        ),
    ),
    CapabilityDefinition(
        'summary_annotation',
        'Summary annotation',
        'metadata',
        'Observed alerts include annotations.summary.',
        False,
        'Inspect annotations.summary in GET /api/v2/alerts responses.',
        'At least one observed alert contains a non-empty annotations.summary value.',
        'Add concise summary annotations to alerting rules and preserve annotations through integrations.',
        'Improves operator readability, notification content, and recommendation context.',
        (
            'Add annotations.summary to alerting rules that do not provide it.',
            'Trigger a representative alert and confirm the summary is visible in /api/v2/alerts.',
            'Rerun Full Validation to refresh capability evidence.',
        ),
    ),
    CapabilityDefinition(
        'runbook_url',
        'Runbook URL',
        'metadata',
        'Observed alerts expose a runbook link.',
        False,
        'Inspect annotations.runbook_url or the normalized runbook URL field in active alert payloads.',
        'At least one observed alert contains a valid runbook URL.',
        'Add a maintained runbook URL annotation to operationally significant alerts.',
        'Enables direct remediation guidance and runbook integration from KAORI.',
        (
            'Create or identify the operational runbook for the alert.',
            'Add the runbook URL to the alerting rule annotation using the organization standard.',
            'Trigger the alert and rerun Full Validation.',
        ),
    ),
    CapabilityDefinition(
        'generator_url',
        'Generator URL',
        'metadata',
        'Observed alerts expose their generator URL.',
        False,
        'Inspect generatorURL in GET /api/v2/alerts responses.',
        'At least one observed alert contains a non-empty generatorURL.',
        'Preserve generatorURL from the originating alert source through Alertmanager and any proxy layer.',
        'Provides direct navigation to the originating rule, query, or monitoring context.',
        (
            'Inspect the raw alert payload for generatorURL.',
            'Review upstream alert generation and intermediary transformations.',
            'Rerun validation with an active alert from the expected source.',
        ),
    ),
    CapabilityDefinition(
        'silence_matchers',
        'Silence matchers',
        'metadata',
        'Observed silences expose matcher definitions.',
        False,
        'Inspect matchers in GET /api/v2/silences responses.',
        'At least one observed silence contains readable matcher definitions. No silences can make this evidence temporarily unavailable.',
        'Use the standard API v2 silence payload and preserve matcher metadata through proxies or adapters.',
        'Improves suppression analysis, governance, and alert-to-silence correlation.',
        (
            'Create a temporary controlled silence with representative matchers when validation evidence is required.',
            'Inspect /api/v2/silences and confirm the matchers array is present.',
            'Remove the temporary silence when complete and rerun Full Validation.',
        ),
    ),
)

CAPABILITY_BY_KEY = {item.key: item for item in CAPABILITIES}


CAPABILITY_KEYS = tuple(item.key for item in CAPABILITIES)
COMPATIBILITY_PROFILES = ('alertmanager-v0-25', 'alertmanager-v0-33')


BINDING_CAPABILITY_KEYS = (
    'alerts',
    'alerts_v2',
    'silences',
    'silences_v2',
    'routing',
    'receivers',
    'status_v2',
)

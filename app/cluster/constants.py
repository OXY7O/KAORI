ENVIRONMENTS = [
    ('development', 'Development'),
    ('staging', 'Staging'),
    ('production', 'Production'),
    ('quality_assurance', 'Quality Assurance'),
    ('user_acceptance_testing', 'User Acceptance Testing'),
    ('testing', 'Testing'),
    ('pre_production', 'Pre-Production'),
    ('non_production', 'Non-Production'),
    ('disaster_recovery', 'Disaster Recovery'),
    ('laboratory', 'Laboratory'),
    ('proof_of_concept', 'Proof of Concept'),
    ('demonstration', 'Demonstration'),
    ('sandbox', 'Sandbox'),
]

_ENVIRONMENT_LABELS = dict(ENVIRONMENTS)


def normalize_environment_value(value: str | None, *, empty: str = '') -> str:
    """Return the normalized canonical storage and filter value."""
    normalized = (value or '').strip().lower().replace('-', '_').replace(' ', '_')
    return normalized or empty


def get_environment_label(value: str | None, *, empty: str = 'Not specified') -> str:
    """Return the full user-facing environment name without exposing abbreviations."""
    canonical = normalize_environment_value(value)
    if not canonical:
        return empty
    return _ENVIRONMENT_LABELS.get(canonical, canonical.replace('_', ' ').title())

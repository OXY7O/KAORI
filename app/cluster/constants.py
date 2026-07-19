ENVIRONMENTS = [
    ('dev', 'Development'),
    ('stg', 'Staging'),
    ('prd', 'Production'),
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

_ENVIRONMENT_ALIASES = {
    'dev': 'development',
    'development': 'development',
    'stg': 'staging',
    'stage': 'staging',
    'staging': 'staging',
    'prd': 'production',
    'prod': 'production',
    'production': 'production',
    'qa': 'quality_assurance',
    'quality-assurance': 'quality_assurance',
    'quality_assurance': 'quality_assurance',
    'uat': 'user_acceptance_testing',
    'user-acceptance-testing': 'user_acceptance_testing',
    'user_acceptance_testing': 'user_acceptance_testing',
    'test': 'testing',
    'testing': 'testing',
    'preprod': 'pre_production',
    'pre-prod': 'pre_production',
    'pre_production': 'pre_production',
    'np': 'non_production',
    'nonprod': 'non_production',
    'non-prod': 'non_production',
    'non_production': 'non_production',
    'dr': 'disaster_recovery',
    'drc': 'disaster_recovery',
    'disaster-recovery': 'disaster_recovery',
    'disaster_recovery': 'disaster_recovery',
    'lab': 'laboratory',
    'laboratory': 'laboratory',
    'poc': 'proof_of_concept',
    'proof-of-concept': 'proof_of_concept',
    'proof_of_concept': 'proof_of_concept',
    'demo': 'demonstration',
    'demonstration': 'demonstration',
    'sandbox': 'sandbox',
}

_ENVIRONMENT_LABELS = {
    'development': 'Development',
    'staging': 'Staging',
    'production': 'Production',
    'quality_assurance': 'Quality Assurance',
    'user_acceptance_testing': 'User Acceptance Testing',
    'testing': 'Testing',
    'pre_production': 'Pre-Production',
    'non_production': 'Non-Production',
    'disaster_recovery': 'Disaster Recovery',
    'laboratory': 'Laboratory',
    'proof_of_concept': 'Proof of Concept',
    'demonstration': 'Demonstration',
    'sandbox': 'Sandbox',
}


def normalize_environment_value(value: str | None, *, empty: str = '') -> str:
    """Return a canonical storage/filter value while accepting legacy aliases."""
    normalized = (value or '').strip().lower().replace(' ', '_')
    if not normalized:
        return empty
    return _ENVIRONMENT_ALIASES.get(normalized, normalized)


def get_environment_label(value: str | None, *, empty: str = 'Not specified') -> str:
    """Return the full user-facing environment name without exposing abbreviations."""
    canonical = normalize_environment_value(value)
    if not canonical:
        return empty
    return _ENVIRONMENT_LABELS.get(canonical, canonical.replace('_', ' ').title())

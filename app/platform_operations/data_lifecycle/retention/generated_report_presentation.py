GENERATED_REPORT_LABEL = 'Generated Reports'
GENERATED_REPORT_ICON = 'file-archive'
GENERATED_REPORT_DESCRIPTION = 'Generated report metadata and retained PDF, XLSX, or CSV artifact evidence.'
GENERATED_REPORT_COVERAGE = (
    {
        'icon': 'table-2',
        'label': 'Generated Registry',
        'description': 'Terminal Ready, Failed, and Archived report records after their status-specific hot-retention window.',
    },
    {
        'icon': 'file-check-2',
        'label': 'Artifact Evidence',
        'description': 'Ready and Archived PDF, XLSX, and CSV files are copied and checksum-verified before cleanup.',
    },
    {
        'icon': 'hard-drive-download',
        'label': 'Report Storage',
        'description': 'Source artifacts remain untouched until the lifecycle archive and supplemental evidence verify successfully.',
    },
)
GENERATED_REPORT_COVERAGE_NOTE = (
    'Ready reports use hot retention; Failed and Archived use dedicated windows. Artifacts archive before cleanup.'
)
GENERATED_REPORT_EXCLUSION_NOTE = (
    'Requested, Queued, Generating, active regeneration jobs, and terminal records without a safe artifact reference '
    'are protected from cleanup.'
)

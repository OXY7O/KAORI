GENERATED_REPORT_LABEL = 'Generated Reports'
GENERATED_REPORT_ICON = 'file-archive'
GENERATED_REPORT_DESCRIPTION = 'Report metadata and retained PDF, XLSX, or CSV evidence.'
GENERATED_REPORT_COVERAGE = (
    {
        'icon': 'table-2',
        'label': 'Generated Registry',
        'description': 'Ready, Failed, and Archived reports past their status-specific hot retention.',
    },
    {
        'icon': 'file-check-2',
        'label': 'Artifact Evidence',
        'description': 'Ready/Archived PDF/XLSX/CSV files are copied and checksum-verified before cleanup.',
    },
    {
        'icon': 'hard-drive-download',
        'label': 'Report Storage',
        'description': 'Source files stay intact until archive and supplements pass verification.',
    },
)
GENERATED_REPORT_COVERAGE_NOTE = (
    'Ready reports use hot retention; Failed and Archived use dedicated windows. Artifacts archive before cleanup.'
)
GENERATED_REPORT_EXCLUSION_NOTE = (
    'Requested, Queued, Generating, active regeneration jobs, and terminal records without a safe artifact reference '
    'are protected from cleanup.'
)

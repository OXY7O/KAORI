# Technical Metadata Collection

Shared owner: `components/technical_metadata_collection.html`

Use this component for Kubernetes labels, annotations, selectors, and other long key/value metadata collections.

## Contract

- one section title and entry count;
- scrollable key/value rows with explicit wrapping;
- proportional KAORI typography by default;
- shared empty-evidence state;
- optional one-line context note;
- no chip cloud for dense or long metadata;
- no semantic status color unless a separate operational state is being shown.

The component is presentation-only and receives an ordered mapping from the page service.

# Technical Metadata Collection

Shared owner: `components/technical_metadata_collection.html`

Use this component for Kubernetes labels, annotations, selectors, and other long key/value metadata collections.

## Contract

- one section title and entry count;
- key/value rows with explicit wrapping and no nested vertical scroll;
- proportional KAORI typography by default;
- shared empty-evidence state;
- optional one-line context note;
- no chip cloud for dense or long metadata;
- no semantic status color unless a separate operational state is being shown.

The component is presentation-only and receives an ordered mapping from the page service.


## Full Workspace Modal wrapping

Pair mode reserves a readable key column (`minmax(15rem, 0.42fr)`) and a flexible value column. Keys and values use `overflow-wrap:anywhere`; values preserve intentional line breaks with `whitespace-pre-wrap`. Long metadata expands the modal body instead of truncating or creating a second vertical scrollbar.

"""Source-controlled KAORI definition registry.

YAML files are definition source-of-truth. Runtime modules consume validated,
normalized Python objects from this package; templates and routes never read
YAML directly.
"""

from app.definitions.loader import DefinitionError, load_definition_document

__all__ = ['DefinitionError', 'load_definition_document']

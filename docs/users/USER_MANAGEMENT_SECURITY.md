# User Management Security

- All mutation routes require CSRF-protected POST requests.
- Every mutation is backend permission-enforced; hidden buttons are not security controls.
- Password operations are Local Database only.
- Passwords, hashes, LDAP bind credentials, SSO tokens, assertions, and provider payloads must never enter toast or audit metadata.
- Non-super-admin actors cannot manage admin-level users.
- Users cannot deactivate or delete themselves through User Management.
- The last active super admin is protected.
- External immutable identifiers must not be editable after binding without a dedicated relink workflow.
- Errors shown to operators are concise; restricted logs retain technical diagnostics.

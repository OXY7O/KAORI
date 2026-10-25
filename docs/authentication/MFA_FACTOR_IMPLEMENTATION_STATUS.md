# MFA-02 factor primitives — UAT implementation status

Authority #562, bounded issue #3134, prerequisite #3133.

The isolated factor primitives are implemented using **PyOTP 2.10.0** (vetted upstream distribution) for TOTP, with the approved KAORI encrypted credential wrapper and high-entropy single-use recovery codes represented only by SHA-256 digests at rest. Tests exercise encryption, provisioning URI, verification and recovery-match contracts without recording secrets.

This source increment **does not constitute active MFA**. No factor model/migration, database enrollment transaction, restricted pending-auth challenge, device binding, recovery-code atomic consumption, admin reset, Settings self-service, session issuance check, or Activity Audit emission is active. Those are mandatory before changing any live login route or permitting an operator to select Required MFA. The existing browser login must stay unchanged.

Security admission checklist:
- Define source-owned `MfaFactor` and `MfaRecoveryCode` models with uniqueness/versioning and immutable ownership; migrate with Alembic.
- Encrypt TOTP key at rest, never persist QR URI plaintext or return secret except during enrollment; ensure key rotation and recovery.
- Activate factor only after verifying OTP; bind server-side enrollment state to identity and expire before confirmation.
- Pending-auth cannot satisfy Flask-Login or RBAC; rate limit and expire; revalidate account/provider state after OTP before committing `auth_session_version`.
- Consume recovery digest atomically with one use; reject concurrent replay and force re-enrollment after administrative reset.
- UAT mandatory Local/LDAP/SSO, step-up failures, remember-cookie revocation, copied-cookie boundary and last active super-admin recovery.

No official CI/CD or promotion is authorized.

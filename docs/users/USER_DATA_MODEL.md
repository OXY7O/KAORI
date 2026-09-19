# User Management Data Model

## Current fields used

`users`: username, email, display_name, password_hash, role/role_id, auth_source, external_id, is_active, is_super_admin, login metadata, timestamps, deleted_at.

## Target external identity model

A future `external_identity_links` table should hold provider ID, provider type, immutable subject/object ID, external username/email snapshot, projection mode, first/last sync, and reconciliation status. Provider configuration and secrets must remain outside the user row.

Do not add `is_super_admin` mapping directly from arbitrary external claims. Elevation requires an explicit trusted mapping policy and protection against removing the final recovery administrator.

## Model location standard

All current and future ORM declarations described in this document belong under `app/models/`. Do not place SQLAlchemy models inside `app/access/users/`, provider packages, or route modules. User-domain services import the required model classes from the centralized model package.

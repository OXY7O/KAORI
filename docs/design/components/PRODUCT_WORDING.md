# KAORI Product Wording

This document defines how product-facing copy refers to KAORI.

## Direct product naming

Use **KAORI** whenever the subject or object is the product itself. Prefer direct wording over generic references such as **the application**, **this application**, **the platform**, or **this system**.

Preferred examples:

- `KAORI stores the selected timezone for this account.`
- `Review KAORI logs before retrying.`
- `This role grants access to KAORI.`
- `The capability is available in this KAORI version.`
- `The endpoint must be reachable from the KAORI runtime.`

Avoid:

- `The application stores the selected timezone.`
- `Review application logs.`
- `This role grants application access.`
- `The capability is available in this application version.`

Direct product naming improves recognition, removes ambiguity, and reinforces the KAORI identity without adding promotional language.

## Valid generic uses

Do not replace **application** when it refers to another technical object or a general engineering concept, including:

- Kubernetes application workloads.
- An OAuth or OpenID Connect application/client registered with an external provider.
- An external business application or application owner.
- MIME types such as `application/json`.
- Application-layer protocols.
- Source-code architecture terms such as application service or application context when the technical distinction is required.

Examples that remain valid:

- `Google OpenID Connect application`
- `Application workloads are usually kept off control-plane nodes.`
- `Content-Type: application/json`
- `Coordinate with application owners.`

## Voice and casing

- Write **KAORI** in uppercase.
- Use **KAORI runtime**, **KAORI logs**, **KAORI access**, **KAORI code**, and **KAORI version** when those are the precise concepts.
- Do not write `KAORI application` unless a technical distinction from another KAORI process is necessary. Prefer `KAORI`, `KAORI web runtime`, or `KAORI worker runtime`.
- Keep descriptions in sentence case and headings in Title Case according to the typography standard.

## UI guidance

Apply this rule to:

- Helper text and descriptions.
- Empty and error states.
- Toasts and operational feedback.
- Modal and drawer copy.
- Permission and access guidance.
- System information.
- User-facing audit and diagnostic summaries.

Do not mechanically replace words. Confirm what **application**, **platform**, or **system** refers to before changing the copy.

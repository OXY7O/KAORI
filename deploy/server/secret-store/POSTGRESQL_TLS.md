# PostgreSQL transport qualification (#5202)

Scope: the bundled Secret Store's dedicated PostgreSQL connection. Preserve
the shared KAORI PostgreSQL server and all existing application connection
rules. Do not enable the overlay or change a running database server just
to pass this test.

## Provider and client boundary

The exact [OpenBao 2.7.3 backend](https://github.com/openbao/openbao/blob/v2.7.3/internal/physical/postgresql/postgresql.go)
reads the service-only BAO_PG_CONNECTION_URL and opens a pgx/v5 connection.
Use a PostgreSQL URI with one explicit DNS hostname covered by the server
certificate, dedicated database and runtime identity, sslmode=verify-full,
and an explicit approved sslrootcert path. The server CA used for PostgreSQL
need not be the CA for the OpenBao HTTPS listener.

Non-secret URI shape (placeholders only; not an executable DSN):

    postgresql://kaori_secret_store@postgres:5432/kaori_secret_store?sslmode=verify-full&sslrootcert=/openbao/config/tls/postgres-ca.pem

Provision the actual encoded authentication component independently, in the
mode-0600 OpenBao-only env file. Never echo the resulting URI, pass it as
an argument, add it to general application env, or commit it. Reject
duplicate/conflicting SSL options, fallback hosts and unapproved trust.
Do not accept sslmode=disable, allow, prefer, require or verify-ca as
equivalent to verify-full. Never turn off certificate verification.

## Existing PostgreSQL server authority

The DBA must confirm exact target/project, backup/rollback, PostgreSQL
version, TLS certificate SAN, private key ownership/mode, approved CA,
and pg_hba.conf rule ordering before any server configuration change.
Use the service's actual private DNS name, not an IP unless the certificate
and explicitly approved trust model support it. For the dedicated database
and runtime role, permit only the approved private source via hostssl and
SCRAM; deny matching non-TLS connections and other unauthorized sources
before any broader rules. Verify ordering and effective behavior, not
merely the presence of a hostssl line. Preserve application access and
verify its health after any separately authorized server change.
Do not copy a generic pg_hba.conf over the running server.

## Read-only verification

From an authorized disposable client on the same private network, use
psql with independently supplied authentication, explicit PGSSLMODE=verify-full,
PGSSLROOTCERT pointing to the approved CA, and PGHOST matching the server SAN.
Do not set PGPASSWORD in command history or export the OpenBao DSN to other
processes. Use native interactive password prompt or an independently
protected temporary passfile. Run the reviewed verify-storage-transport.sql
as the actual dedicated runtime identity, not a DBA with SET ROLE.

The SQL inspects the current pg_stat_ssl session, TLS version and strength,
database/identity, role escalation and database privileges; it never reads
KV rows or changes state. A PASS proves session encryption and selected
runtime constraints, not the client's hostname/CA verification. The
operator must separately capture the exact non-secret client options
and outcomes.

## Required qualification matrix

| Case | Expected |
| --- | --- |
| Approved CA, matching DNS, runtime role, primary DB, verify-full | PASS |
| Wrong CA, same DNS and role | TLS refusal |
| Wrong DNS/SAN, same CA and role | TLS refusal |
| Explicit cleartext attempt, dedicated role | Server rejects before SQL |
| Wrong password or unauthorized source | Server rejects authentication |
| Dedicated role attempting application DB | Server rejects CONNECT |
| Application runtime attempting dedicated DB | Server rejects CONNECT |
| Actual pinned OpenBao starts with approved DSN | Expected uninitialized or sealed state |
| Actual OpenBao with wrong CA or hostname | Startup fails closed |
| Existing application health after authorized TLS change | PASS |

Retain only sanitized outcomes, exact image and target identities, certificate
fingerprint/expiry, timestamps and recovery evidence. A successful psql
test is not sufficient evidence for pgx/OpenBao compatibility; run the
actual pinned provider positive and negative cases separately. No target
change, TLS setup, credential, provider start or runtime acceptance is
performed by this source increment.

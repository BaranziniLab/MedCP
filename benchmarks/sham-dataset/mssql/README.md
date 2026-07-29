# Sham OMOP on SQL Server (AWS RDS)

Scripts to host the sham OMOP dataset on a Microsoft SQL Server instance so you
can exercise MedCP's `mssql` backend against a real server.

## Provision + load

```bash
read -rsp 'RDS master password: ' DB_ADMIN_PASSWORD
echo
export DB_ADMIN_PASSWORD
./provision.sh
unset DB_ADMIN_PASSWORD
```

`provision.sh` creates an RDS SQL Server Express instance (`db.t3.small` by
default), opens a security group to your public IP on port 1433, creates the
`omop` database, loads all 32 OMOP tables (~468K rows) as the RDS admin with
[`../load_omop.py`](../load_omop.py), then creates a dedicated SELECT-only
login and database user. It writes only that reader to a git-ignored `.dbenv`;
it never writes the admin credential there. Override defaults via `AWS_REGION`,
`DB_IDENTIFIER`, `DB_ADMIN_USER`, `DB_NAME`, `DB_CLASS`, `DB_READER_USER`, and
`DB_READER_PASSWORD`. The reader defaults to `medcpreader` with a generated
password. (SQL Server takes ~10–15 min to provision.)

The generated file exports the complete backend-specific family
`MSSQL_HOST`, `MSSQL_PORT`, `MSSQL_USER`, `MSSQL_PASSWORD`, and
`MSSQL_DATABASE`. It also exports the legacy `DB_USER`, `DB_PASSWORD`, and
`DB_NAME` aliases for older benchmark commands. Both families contain the
SELECT-only reader. The test harness prefers the backend-specific values.

For backward-compatible provisioning, `DB_USER` and `DB_PASSWORD` are accepted
as admin-input aliases when the explicit `DB_ADMIN_*` variables are absent.
Prefer `DB_ADMIN_*`, especially if a reader `.dbenv` has previously been
sourced. Database and account names must contain only ASCII letters, digits,
and underscores and may not start with a digit.

### Migrate an existing fixture

For an existing `medcp-mssql` instance created by the older script, rotate in a
reader and replace its admin-bearing `.dbenv` without reloading the tables:

```bash
read -rsp 'Existing RDS master password: ' DB_ADMIN_PASSWORD
echo
export DB_ADMIN_PASSWORD
MIGRATE_EXISTING=1 ./provision.sh
unset DB_ADMIN_PASSWORD
```

Set `DB_IDENTIFIER`, `DB_ADMIN_USER`, or `DB_NAME` if the existing instance
does not use the defaults. The command generates a new reader password, passes
both database passwords only via the loader environment, and atomically
replaces `.dbenv` with the reader values.

## Test MedCP against it

```bash
source ./.dbenv
uv run --directory ../../.. --locked \
  python benchmarks/sham-dataset/test_backends.py
```

This runs the MCP 2026-07-28 backend harness and also performs its explicit,
network-dependent default SPOKE check. Or map the backend-specific values to a
MedCP server directly:

```bash
export CLINICAL_RECORDS_BACKEND=mssql
export CLINICAL_RECORDS_SERVER="$MSSQL_HOST"
export CLINICAL_RECORDS_PORT="$MSSQL_PORT"
export CLINICAL_RECORDS_DATABASE="$MSSQL_DATABASE"
export CLINICAL_RECORDS_USERNAME="$MSSQL_USER"
export CLINICAL_RECORDS_PASSWORD="$MSSQL_PASSWORD"
```

Leave `KNOWLEDGE_GRAPH_*` unset to use the bundled read-only SPOKE production
graph, or set `MEDCP_DISABLE_KNOWLEDGE_GRAPH=1` for an EHR-only server canary.
For a checkout canary, also set `MEDCP_NAMESPACE=MedCPNext` and launch it with
`uv run --directory ../../.. --locked medcp`.

## Tear down (stop billing)

```bash
./teardown.sh
```

> The master password is not hardcoded, printed, passed in a child process
> argument, or written to `.dbenv`. The loader receives it through its
> environment; during instance creation the AWS CLI reads it from a transient
> mode-`0600` JSON file that is removed immediately and on abnormal exit.
> `.dbenv` is still a mode-`0600`, shell-escaped plaintext credential file for
> the SELECT-only reader, not a keyring. Git-ignore is not encryption: never
> commit, print, or share it, and delete it after teardown.

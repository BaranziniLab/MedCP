# Sham OMOP on SQL Server (AWS RDS)

Scripts to host the sham OMOP dataset on a Microsoft SQL Server instance so you
can exercise MedCP's `mssql` backend against a real server.

## Provision + load

```bash
read -rsp 'RDS master password: ' DB_PASSWORD
echo
export DB_PASSWORD
./provision.sh
unset DB_PASSWORD
```

`provision.sh` creates an RDS SQL Server Express instance (`db.t3.small` by
default), opens a security group to your public IP on port 1433, creates the
`omop` database, loads all 32 OMOP tables (~468K rows) with
[`../load_omop.py`](../load_omop.py), and writes a git-ignored `.dbenv` with the
connection details. Override defaults via `AWS_REGION`, `DB_IDENTIFIER`,
`DB_USER`, `DB_NAME`, `DB_CLASS`. (SQL Server takes ~10–15 min to provision.)

The generated file exports the complete backend-specific family
`MSSQL_HOST`, `MSSQL_PORT`, `MSSQL_USER`, `MSSQL_PASSWORD`, and
`MSSQL_DATABASE`. It also exports the legacy `DB_USER`, `DB_PASSWORD`, and
`DB_NAME` aliases for older benchmark commands. The test harness prefers the
backend-specific values.

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

> The master password is not hardcoded or printed, but AWS and the loader receive
> it as a process argument. `.dbenv` is a mode-`0600`, shell-escaped plaintext
> credential file, not a keyring. Git-ignore is not encryption: never commit,
> print, or share it, and delete it after teardown.

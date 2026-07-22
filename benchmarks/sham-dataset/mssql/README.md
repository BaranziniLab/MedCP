# Sham OMOP on SQL Server (AWS RDS)

Scripts to host the sham OMOP dataset on a Microsoft SQL Server instance so you
can exercise MedCP's `mssql` backend against a real server.

## Provision + load

```bash
export DB_PASSWORD='SomeStrongPassword123'   # RDS master password (8+ chars)
./provision.sh
```

`provision.sh` creates an RDS SQL Server Express instance (`db.t3.small` by
default), opens a security group to your public IP on port 1433, creates the
`omop` database, loads all 32 OMOP tables (~468K rows) with
[`../load_omop.py`](../load_omop.py), and writes a git-ignored `.dbenv` with the
connection details. Override defaults via `AWS_REGION`, `DB_IDENTIFIER`,
`DB_USER`, `DB_NAME`, `DB_CLASS`. (SQL Server takes ~10–15 min to provision.)

## Test MedCP against it

```bash
source ./.dbenv
python ../test_backends.py          # exercises sqlite + mssql + SPOKE
```

Or point MedCP directly:

```bash
export CLINICAL_RECORDS_BACKEND=mssql
export CLINICAL_RECORDS_SERVER="$MSSQL_HOST"
export CLINICAL_RECORDS_DATABASE=omop
export CLINICAL_RECORDS_USERNAME="$DB_USER"
export CLINICAL_RECORDS_PASSWORD="$DB_PASSWORD"
```

## Tear down (stop billing)

```bash
./teardown.sh
```

> The scripts never hardcode credentials — the master password comes from
> `DB_PASSWORD`, and the resulting `.dbenv` is git-ignored. Do not commit real
> endpoints or passwords.

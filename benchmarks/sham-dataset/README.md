# Sham OMOP dataset + backend tests

A synthetic (sham) OMOP CDM dataset used to exercise MedCP's three clinical
record backends. Nothing here contains real patient data.

```
sham-dataset/
├── sqlite/                     the dataset itself (a ready-to-query SQLite file)
│   ├── sham_mimic_omop.sqlite  32 OMOP tables, ~468K rows, 100 patients
│   └── README / LICENSE / SOURCE_README
├── mysql/                      host the dataset on AWS RDS MySQL + test
│   ├── provision.sh · teardown.sh · README.md
├── mssql/                      host the dataset on AWS RDS SQL Server + test
│   ├── provision.sh · teardown.sh · README.md
├── load_omop.py                loads sqlite/ → MySQL or SQL Server
└── test_backends.py            verifies MedCP against each configured backend
```

## Quick test — SQLite only (no setup)

The SQLite backend needs no server or credentials:

```bash
# From the repo root, using MedCP's exact locked environment:
uv run --locked python benchmarks/sham-dataset/test_backends.py
```

This reports the SQLite backend (32 tables, 100 patients, writes blocked) and
the default SPOKE knowledge graph. The harness uses the MCP 2026-07-28 client
mode, so it exercises the modern in-process protocol path.

## Test against hosted MySQL / SQL Server

Each backend has a self-contained hosting script under [`mysql/`](mysql) and
[`mssql/`](mssql). They provision an AWS RDS instance, load the dataset, and
write a git-ignored `.dbenv` you can `source` before running
[`test_backends.py`](test_backends.py). See those folders' READMEs. For example:

```bash
cd mysql
read -rsp 'RDS master password: ' DB_PASSWORD
echo
export DB_PASSWORD
./provision.sh                                   # create RDS MySQL + load data
unset DB_PASSWORD
source ./.dbenv
uv run --directory ../../.. --locked \
  python benchmarks/sham-dataset/test_backends.py # sqlite + mysql + SPOKE
./teardown.sh                                    # delete the instance when done
```

`test_backends.py` automatically includes MySQL and/or SQL Server whenever their
backend-specific variables are present:

- MySQL: `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`,
  `MYSQL_DATABASE`
- SQL Server: `MSSQL_HOST`, `MSSQL_PORT`, `MSSQL_USER`, `MSSQL_PASSWORD`,
  `MSSQL_DATABASE`

The generated `.dbenv` files also export legacy `DB_USER`, `DB_PASSWORD`, and
`DB_NAME` aliases for compatibility. Backend-specific values take precedence,
which makes it safe to load both families without sharing one backend's
credentials with the other.

These variables configure the benchmark harness. A MedCP server launch instead
uses `CLINICAL_RECORDS_BACKEND` and the corresponding
`CLINICAL_RECORDS_SERVER`, `_PORT`, `_USERNAME`, `_PASSWORD`, and `_DATABASE`
variables.

The harness intentionally includes a network-dependent default SPOKE check.
Normal MedCP launches also use the bundled read-only SPOKE graph when
`KNOWLEDGE_GRAPH_*` is unset; set `MEDCP_DISABLE_KNOWLEDGE_GRAPH=1` for a
separate EHR-only server canary. That environment flag does not skip the
harness's explicit SPOKE test.

## Requirements

- [`uv`](https://docs.astral.sh/uv/) (runs the loader/tests with the right
  drivers), and the `aws` CLI configured for the hosting scripts.
- MySQL uses `pymysql`; SQL Server uses `pymssql`; SQLite uses the standard
  library.

> Security: the hosting scripts take the RDS master password from
> `DB_PASSWORD`; it is not hardcoded or printed. AWS and the loader still receive
> it as a process argument, and each generated `.dbenv` contains the password in
> plaintext. The scripts shell-escape the values and restrict the file to mode
> `0600`, but git-ignore is not encryption. Never commit, print, or share the
> file, and delete it after teardown.

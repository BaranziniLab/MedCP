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
# From the repo root, with MedCP's deps available (e.g. via uv):
uv run --with fastmcp --with neo4j python benchmarks/sham-dataset/test_backends.py
```

This reports the SQLite backend (32 tables, 100 patients, writes blocked) and
the default SPOKE knowledge graph.

## Test against hosted MySQL / SQL Server

Each backend has a self-contained hosting script under [`mysql/`](mysql) and
[`mssql/`](mssql). They provision an AWS RDS instance, load the dataset, and
write a git-ignored `.dbenv` you can `source` before running
[`test_backends.py`](test_backends.py). See those folders' READMEs. For example:

```bash
cd mysql
export DB_PASSWORD='SomeStrongPassword123'
./provision.sh                                   # create RDS MySQL + load data
source ./.dbenv
python ../test_backends.py                       # sqlite + mysql + SPOKE
./teardown.sh                                    # delete the instance when done
```

`test_backends.py` automatically includes MySQL and/or SQL Server whenever their
`MYSQL_HOST` / `MSSQL_HOST` (and `DB_USER` / `DB_PASSWORD`) variables are set —
exactly what the `.dbenv` files provide.

## Requirements

- [`uv`](https://docs.astral.sh/uv/) (runs the loader/tests with the right
  drivers), and the `aws` CLI configured for the hosting scripts.
- MySQL uses `pymysql`; SQL Server uses `pymssql`; SQLite uses the standard
  library.

> Security: the hosting scripts take the RDS master password from `DB_PASSWORD`
> and never hardcode it. The generated `.dbenv` files (real endpoints +
> passwords) are git-ignored — never commit live credentials.

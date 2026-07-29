# MedCP — BioRouter extension

A [BioRouter](https://biorouter.ucsf.edu) extension (`.brxt`) that exposes
MedCP's read-only clinical-records and knowledge-graph tools, plus a bundled
`medcp-clinical-records` skill. It packages the shared `medcp` core as a
self-contained Python MCP server. See [`../README.md`](../README.md) for how
this integration relates to the others.

## Layout

```text
biorouter/
├── manifest.json                         # BioRouter extension metadata + env vars
├── pyproject.toml                        # Python package (entry_point: medcp)
├── README.md
├── skills/medcp-clinical-records/SKILL.md
├── src/medcp/                            # GENERATED: copy of ../../src/medcp (git-ignored)
└── uv.lock                               # GENERATED: uv lockfile (git-ignored)
```

`src/medcp/` is **copied from the shared core** by
[`../../scripts/build_releases.py`](../../scripts/build_releases.py) at build
time — do not edit it here. That script also generates the `uv.lock`. Both
`src/` and `uv.lock` are git-ignored, but both are bundled into the `.brxt`.

## Build the .brxt

```bash
python3 ../../scripts/build_releases.py --only biorouter
# → releases/MedCP v0.10.0/MedCP.brxt
```

The script copies the core into `src/`, runs `uv lock` (verifying cross-platform
wheel resolution, including Intel macOS), and zips the required entries:
`manifest.json`, `README.md`, `pyproject.toml`, `src/`, `skills/`, and the
generated `uv.lock`.

The bundled server supports sessionless MCP 2026-07-28 and the SDK's legacy
initialization fallback. A BioRouter version that still initializes a legacy
session tests the fallback path, not the modern wire path; keep the modern
in-process and raw-stdio tests in the release gate.

## Install

Requires [`uv`](https://docs.astral.sh/uv/) — BioRouter runs `uv sync` on install.

```bash
# SQLite EHR (e.g. the sham OMOP dataset)
biorouter extension install "releases/MedCP v0.10.0/MedCP.brxt" \
  --env CLINICAL_RECORDS_BACKEND=sqlite \
  --env CLINICAL_RECORDS_SQLITE_PATH=/absolute/path/to/database.sqlite

# MySQL / SQL Server: pass server/database/username + a secret password
biorouter extension install "releases/MedCP v0.10.0/MedCP.brxt" \
  --env CLINICAL_RECORDS_BACKEND=mysql \
  --env CLINICAL_RECORDS_SERVER=db.example.org \
  --env CLINICAL_RECORDS_DATABASE=omop \
  --env CLINICAL_RECORDS_USERNAME=reader
```

`--env` values are ordinary configuration. Store
`CLINICAL_RECORDS_PASSWORD` with BioRouter's secret field in the desktop UI
whenever possible. The CLI's `--secret KEY=value` also stores the value in the
OS keyring, but supplying a literal value can expose it through shell history or
process inspection. The keyring protects the value at rest after installation;
it does not make the command line secret.

The knowledge graph is optional. Leave every `KNOWLEDGE_GRAPH_*` variable unset
to use the bundled read-only SPOKE production graph, set those variables only
for your own Neo4j graph, or pass
`--env MEDCP_DISABLE_KNOWLEDGE_GRAPH=1` for an EHR-only server.

Remove the extension with `biorouter extension remove medcp`.

## Safe checkout canary

BioRouter 1.88.6 can match a dynamically loaded tool to an existing extension's
shorter prefix. If `medcp` is already enabled, a distinct MCP namespace alone
does not isolate an ephemeral canary: the call can reach the installed
extension and fail tool-name validation.

Run the canary with a workflow that disables installed extensions:

```yaml
# /tmp/medcp-canary.yaml
version: 1.0.0
title: MedCP isolated canary
description: Load only the MedCP checkout supplied on the command line.
instructions: Use only the MedCPNext tools requested by the user.
prompt: |-
  Call MedCPNext-list_clinical_tables, then MedCPNext-query_clinical_records
  with sql_query SELECT COUNT(*) AS n FROM person.
extensions: []
parameters: []
```

Then load the checkout as the workflow's only extension:

```bash
biorouter run --workflow /tmp/medcp-canary.yaml --no-session --debug \
  --with-extension 'CLINICAL_RECORDS_BACKEND=sqlite CLINICAL_RECORDS_SQLITE_PATH=/path/to/MedCP-next/benchmarks/sham-dataset/sqlite/sham_mimic_omop.sqlite MEDCP_DISABLE_KNOWLEDGE_GRAPH=1 MEDCP_NAMESPACE=MedCPNext uv run --directory /path/to/MedCP-next --locked medcp'
```

The `extensions: []` workflow setting prevents the installed `medcp` extension
from entering this run; it does not remove or reconfigure that installation.
Omit `MEDCP_DISABLE_KNOWLEDGE_GRAPH=1` only when the canary intentionally tests
the default SPOKE connection. A persistently installed side-by-side artifact
must also use a distinct manifest `name` such as `medcp-next`; installing
another bundle named `medcp` targets the existing extension.

## Use

In a BioRouter session, ask e.g. *"List the clinical tables, then count patients
by gender."* BioRouter auto-loads the `medcp-clinical-records` skill and calls
the read-only MedCP tools.

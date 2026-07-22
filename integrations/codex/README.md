# MedCP — Codex CLI MCP server

Registers MedCP as an MCP server for [Codex](https://developers.openai.com/codex/cli/),
exposing the read-only clinical-records and knowledge-graph tools. Codex runs the
shared `medcp` core with `uvx`, so it's the same engine as the Claude Code plugin
and the BioRouter extension.

## What's in here

```
codex/
├── config.snippet.toml   # paste into ~/.codex/config.toml
├── install.sh            # registers the server with `codex mcp add`
└── README.md
```

## Requirements

- Codex CLI (`codex`) with MCP support (`codex mcp --help`)
- [`uv`](https://docs.astral.sh/uv/) on your PATH (provides `uvx`)

## Install

### Option A — scripted (recommended)

Export the variables for your backend, then run the installer:

```bash
export CLINICAL_RECORDS_BACKEND=sqlite
export CLINICAL_RECORDS_SQLITE_PATH=/absolute/path/to/database.sqlite
./install.sh
```

or load them from a `.env` file:

```bash
./install.sh --env-file ../../.env
```

For local development against a checkout instead of the pinned release:

```bash
MEDCP_SOURCE=/path/to/MedCP ./install.sh --env-file ../../.env
```

Verify: `codex mcp get medcp`.

### Option B — manual

Copy the block in [`config.snippet.toml`](config.snippet.toml) into
`~/.codex/config.toml`, fill in the values for your backend, and restart Codex.

## Configuration

Same variables as every MedCP target — set `CLINICAL_RECORDS_BACKEND` to
`sqlite`, `mysql`, or `mssql` and supply the matching connection settings (see
[`config.snippet.toml`](config.snippet.toml)). `KNOWLEDGE_GRAPH_*` is optional.

## Use

Start Codex and ask, e.g. *"Use MedCP to list the clinical tables and count
patients by gender."* Codex will call the `list_clinical_tables` and
`query_clinical_records` tools (read-only `SELECT`/`WITH` only).

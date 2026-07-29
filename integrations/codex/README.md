# MedCP — Codex CLI MCP server

Registers MedCP as an MCP server for [Codex](https://developers.openai.com/codex/cli/),
exposing the read-only clinical-records and knowledge-graph tools. Codex runs the
shared `medcp` core with `uvx`, so it's the same engine as the
[Claude Code plugin](../claude-code/README.md) and the
[BioRouter extension](../biorouter/README.md).

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

MedCP implements sessionless MCP 2026-07-28 and retains the SDK's legacy
initialization fallback. A Codex release that still uses the legacy lifecycle
can validate interoperability with the upgraded server, but that smoke test is
not evidence that the modern protocol path ran. Keep the modern SDK tests and
raw-stdio tests in the release gate.

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
[`config.snippet.toml`](config.snippet.toml)). Leave `KNOWLEDGE_GRAPH_*` unset
to use the bundled read-only SPOKE production graph, set them only for your own
Neo4j graph, or set `MEDCP_DISABLE_KNOWLEDGE_GRAPH=1` for an EHR-only server.
The helper script forwards the opt-out variable when it is set; for a manual
configuration, add it to the server's `[mcp_servers.<name>.env]` table.

The installer passes selected environment values to `codex mcp add`, which
persists them in Codex's user configuration. That storage is not an OS keyring.
Treat `~/.codex/config.toml` and any sourced `.env` as plaintext credential
files. The helper also passes values to the registration command as process
arguments. Restrict file permissions and do not commit, log, or paste live
credentials into a prompt.

The normal `uvx` launch uses the published package. For a local checkout, use
`uv run --locked` so a stale or missing lock fails instead of silently resolving
a different dependency set.

## Safe side-by-side canary

Use a separate registration and namespace, with the sham SQLite database rather
than production credentials:

```bash
codex mcp add medcp-next \
  --env CLINICAL_RECORDS_BACKEND=sqlite \
  --env CLINICAL_RECORDS_SQLITE_PATH=/path/to/MedCP-next/benchmarks/sham-dataset/sqlite/sham_mimic_omop.sqlite \
  --env MEDCP_DISABLE_KNOWLEDGE_GRAPH=1 \
  --env MEDCP_NAMESPACE=MedCPNext \
  -- uv run --directory /path/to/MedCP-next --locked medcp

codex mcp get medcp-next
```

Alternatively, set `MEDCP_NAME=medcp-next`, `MEDCP_SOURCE=/path/to/MedCP-next`,
and `MEDCP_NAMESPACE=MedCPNext` before running `install.sh`. The explicit
`codex mcp add` form above uses the checkout lock and is preferred for release
validation.

Restart Codex and ask it to use only tools whose names contain `MedCPNext`.
Remove the canary with `codex mcp remove medcp-next`. Omit
`MEDCP_DISABLE_KNOWLEDGE_GRAPH=1` only when the test is intended to exercise the
default SPOKE connection. The separate registration name prevents overwriting
`medcp`; the separate namespace prevents ambiguous tool names.

## Use

Start Codex and ask, e.g. *"Use MedCP to list the clinical tables and count
patients by gender."* Codex will call the `MedCP-list_clinical_tables` and
`MedCP-query_clinical_records` tools (read-only `SELECT`/`WITH` only). Tool names
carry the `MEDCP_NAMESPACE` prefix (default `MedCP`).

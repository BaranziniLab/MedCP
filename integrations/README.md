# MedCP integrations

MedCP ships one **shared core** — the `medcp` Python package in
[`../src/medcp`](../src/medcp) — plus several thin, cleanly separated
**integrations** that expose that same core to different AI agents. Nothing in
this directory reimplements the server; each target only carries the *external
glue* (manifest, launch config, docs) specific to its host.

```text
              ┌──────────────────────────────┐
              │   shared core:  src/medcp/    │  ← tools + mssql/mysql/sqlite backends
              │   console script:  medcp      │
              └──────────────┬───────────────┘
                             │ (same stdio MCP server, launched differently)
   ┌───────────────┬─────────┼──────────────┬─────────────────────┐
   ▼               ▼         ▼              ▼                     ▼
Claude Code    Codex     BioRouter     Claude Desktop        uvx / CLI
(plugin)     (mcp server) (.brxt ext)   (.mcpb, repo root)   (universal)
```

| Target | Directory | How it launches the core | Artifact |
|---|---|---|---|
| **Claude Code** | [`claude-code/`](claude-code) | plugin `.mcp.json` → `uvx … medcp` | `medcp-claude-code-plugin.zip` |
| **Codex CLI** | [`codex/`](codex) | `~/.codex/config.toml` `[mcp_servers.medcp]` → `uvx … medcp` | `medcp-codex.zip` |
| **BioRouter** | [`biorouter/`](biorouter) | `.brxt` bundle, `uv run medcp` | `MedCP.brxt` |
| **Claude Desktop** | [`../manifest.json`](../manifest.json) + [`../server/`](../server) | bundled Python runs `server/main.py` | `MedCP.mcpb` |

## Shared core = single source of truth

The BioRouter extension needs a self-contained copy of the Python package, so
[`../scripts/build_releases.py`](../scripts/build_releases.py) **copies**
`src/medcp/` into [`biorouter/src/`](biorouter) at build time (generated and
git-ignored — never edit it by hand). The same script also regenerates the Claude
Desktop bundle's standalone [`../server/main.py`](../server/main.py) from
`src/medcp/server.py`; that `.mcpb` is then packaged separately with `mcpb pack`.
Claude Code and Codex need no copy — they run the published or local package
directly with `uvx`.

Change behaviour in exactly one place — `src/medcp/` — then rebuild.

## Configuration (all targets)

Every target reads the same environment variables. **Both databases are
optional** — with no configuration at all, MedCP connects to the bundled SPOKE
production knowledge graph and exposes only the knowledge-graph tools.

**Knowledge graph (`KNOWLEDGE_GRAPH_*`) — optional.** Left unset, MedCP uses the
bundled SPOKE production graph automatically (no credentials needed). Set
`KNOWLEDGE_GRAPH_URI` / `_USERNAME` / `_PASSWORD` / `_DATABASE` to use your own
Neo4j graph instead, or `MEDCP_DISABLE_KNOWLEDGE_GRAPH=1` to turn it off.

**Clinical records (`CLINICAL_RECORDS_*`) — optional**, selected with
`CLINICAL_RECORDS_BACKEND`. The credentials are for *your* EHR database:

- `sqlite` — set `CLINICAL_RECORDS_SQLITE_PATH` to a local `.sqlite` file (no credentials)
- `mysql` — set `CLINICAL_RECORDS_SERVER` / `_DATABASE` / `_USERNAME` / `_PASSWORD` (+ optional `_PORT`) for your MySQL server
- `mssql` — the same four for your SQL Server

See [`../releases`](../releases) for the built artifacts and per-OS install
instructions.

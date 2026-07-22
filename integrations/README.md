# MedCP integrations

MedCP ships one **shared core** — the `medcp` Python package in
[`../src/medcp`](../src/medcp) — and several thin, cleanly separated
**integration layers** that expose that same core to different AI coding agents.
Nothing in this directory reimplements the server; each target only carries the
*external glue* (manifest, launch config, docs) specific to its host.

```
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
| **Claude Code** | [`claude-code/`](claude-code) | plugin `.mcp.json` → `uvx … medcp` | plugin folder / zip |
| **Codex CLI** | [`codex/`](codex) | `~/.codex/config.toml` `[mcp_servers.medcp]` → `uvx … medcp` | config snippet + installer |
| **BioRouter** | [`biorouter/`](biorouter) | `.brxt` bundle, `uv run medcp` | `MedCP.brxt` |
| **Claude Desktop** | `../manifest.json` + `../server/` | bundled Python runs `server/main.py` | `MedCP.mcpb` |

## Shared core = single source of truth

The BioRouter extension and the Claude Desktop bundle need a self-contained copy
of the Python package, so [`../scripts/build_releases.py`](../scripts/build_releases.py)
**copies** `src/medcp/` into them at build time. Those copies are generated (and
git-ignored) — never edit them by hand. Claude Code and Codex don't need a copy:
they run the published/local package directly with `uvx`.

Edit behaviour in exactly one place: `src/medcp/`. Then rebuild.

## Configuration (all targets)

Every target reads the same environment variables. The clinical-records backend
is selected with `CLINICAL_RECORDS_BACKEND`:

- `sqlite` — set `CLINICAL_RECORDS_SQLITE_PATH` to a local `.sqlite` file
- `mysql` — set `CLINICAL_RECORDS_SERVER` / `_DATABASE` / `_USERNAME` / `_PASSWORD` (+ optional `_PORT`)
- `mssql` — same four (SQL Server; default backend)

The Neo4j knowledge-graph variables (`KNOWLEDGE_GRAPH_*`) are optional; configure
at least one of {knowledge graph, clinical records}.

See [`../releases`](../releases) for the built artifacts and per-OS install
instructions.

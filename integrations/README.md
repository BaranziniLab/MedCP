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

## MCP protocol compatibility

The shared server is pinned to the official Python MCP SDK and implements the
sessionless **MCP 2026-07-28** protocol, including `server/discover` and private
tool-catalog cache hints. The SDK also keeps the legacy initialization path for
hosts that have not upgraded yet. A successful smoke test in an older host
therefore proves legacy interoperability; it does not by itself prove that the
host exercised the 2026-07-28 wire path. The modern in-process and raw-stdio
tests remain release gates. The official conformance runner currently targets
HTTP servers, while MedCP intentionally exposes only stdio.

For a checkout, use the repository lock rather than resolving dependencies at
test time:

```bash
uv run --directory /path/to/MedCP --locked medcp
```

The BioRouter artifact bundles its own `uv.lock`. Claude Code and Codex release
configs use `uvx` against the published package, so their reproducibility comes
from that release's exact dependency pins, not from the lock in your checkout.

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

The sham-dataset provisioning and test harness additionally use
backend-specific variables. These are benchmark inputs, not server settings:

| Backend | Preferred benchmark variables | Legacy benchmark fallbacks |
|---|---|---|
| MySQL | `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE` | `DB_USER`, `DB_PASSWORD`, `DB_NAME` |
| SQL Server | `MSSQL_HOST`, `MSSQL_PORT`, `MSSQL_USER`, `MSSQL_PASSWORD`, `MSSQL_DATABASE` | `DB_USER`, `DB_PASSWORD`, `DB_NAME` |

Backend-specific values take precedence. Map them to `CLINICAL_RECORDS_*` when
launching MedCP directly.

Credential handling differs by host. BioRouter's `--secret` values are stored
in the OS keyring; ordinary `--env` values are not secret. Codex MCP environment
values are persisted in its user configuration, and Claude Code either inherits
values from the launching shell or persists literal `-e` registration values.
Plain `.env`, TOML, JSON, YAML, and generated `.dbenv` files are not encrypted:
restrict their permissions and never commit, log, or paste live credentials into
prompts.

See the [current release directory](../releases/MedCP%20v0.10.0) for the built
artifacts and per-OS install instructions. The [`releases/`](../releases) index
documents how superseded artifacts are retained in Git history.

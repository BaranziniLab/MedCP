# MedCP v0.8 — install guide

Official MedCP integration artifacts for AI coding agents. All three launch the
**same** `medcp` core (read-only clinical records over SQL Server / MySQL /
SQLite, plus the optional SPOKE knowledge graph).

| Artifact | Agent | Install section |
|---|---|---|
| `MedCP.brxt` | BioRouter | [BioRouter](#biorouter) |
| `medcp-claude-code-plugin.zip` | Claude Code | [Claude Code](#claude-code) |
| `medcp-codex.zip` | Codex CLI | [Codex CLI](#codex-cli) |

Verify downloads against [`checksums.txt`](checksums.txt).

## Prerequisites (all agents / all OSes)

- **[uv](https://docs.astral.sh/uv/)** — provides `uvx` / `uv`, and builds the
  BioRouter virtualenv on install.
  - macOS / Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
  - Windows (PowerShell): `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`
- The agent itself (BioRouter, Claude Code, or Codex CLI) already installed.
- Your EHR connection details, or a local `.sqlite` file for the `sqlite` backend.

### Backend selection (identical everywhere)

Set `CLINICAL_RECORDS_BACKEND` to one of:

- `sqlite` → also set `CLINICAL_RECORDS_SQLITE_PATH` (absolute path to the file)
- `mysql`  → set `CLINICAL_RECORDS_SERVER` / `_DATABASE` / `_USERNAME` / `_PASSWORD` (+ optional `_PORT`)
- `mssql`  → same four (SQL Server; default)

Optionally add `KNOWLEDGE_GRAPH_URI` / `_USERNAME` / `_PASSWORD` / `_DATABASE`
for SPOKE. Configure at least one of {clinical records, knowledge graph}.

---

## BioRouter

`MedCP.brxt` is a ZIP bundle; BioRouter unzips it, runs `uv sync`, and registers
a stdio MCP server. Works on macOS, Linux, and Windows.

```bash
# SQLite (e.g. the sham OMOP dataset shipped in benchmarks/)
biorouter extension install "MedCP.brxt" \
  --env CLINICAL_RECORDS_BACKEND=sqlite \
  --env CLINICAL_RECORDS_SQLITE_PATH=/absolute/path/to/database.sqlite

# MySQL / SQL Server (store the password in the OS keyring via --secret)
biorouter extension install "MedCP.brxt" \
  --env CLINICAL_RECORDS_BACKEND=mssql \
  --env CLINICAL_RECORDS_SERVER=ehr.hospital.org \
  --env CLINICAL_RECORDS_DATABASE=OMOP_DEID \
  --env CLINICAL_RECORDS_USERNAME=reader \
  --secret CLINICAL_RECORDS_PASSWORD='••••••'
```

- List / remove: `biorouter extension list` · `biorouter extension remove medcp`
- Windows paths: use the full path, e.g.
  `--env CLINICAL_RECORDS_SQLITE_PATH=C:\data\omop.sqlite`
- Then start a session and ask MedCP to list tables or summarize patients.

---

## Claude Code

`medcp-claude-code-plugin.zip` is a Claude Code plugin. Its `.mcp.json` launches
`uvx … medcp`, so no server is bundled.

**Option A — plugin (recommended).** Unzip it and add it via the bundled
marketplace, or point Claude Code at the repo's `integrations/` directory:

```bash
# in a Claude Code session
/plugin marketplace add /path/to/MedCP/integrations
/plugin install medcp@medcp-integrations
```

**Option B — register the MCP server directly** (any OS):

```bash
claude mcp add medcp -- uvx --from git+https://github.com/BaranziniLab/MedCP@v0.8.0 medcp
```

Set the backend variables in your shell before starting `claude` (macOS/Linux
`export NAME=value`; Windows PowerShell `$env:NAME="value"`). For a local core
build instead of the release, `export MEDCP_SOURCE=/path/to/MedCP`.

Then run `/medcp-explore` or just ask Claude to query the clinical tables.

---

## Codex CLI

`medcp-codex.zip` contains a config snippet and an installer that runs
`codex mcp add`.

```bash
unzip medcp-codex.zip -d medcp-codex && cd medcp-codex
chmod +x install.sh

export CLINICAL_RECORDS_BACKEND=sqlite
export CLINICAL_RECORDS_SQLITE_PATH=/absolute/path/to/database.sqlite
./install.sh                      # or: ./install.sh --env-file /path/to/.env
```

This writes an `[mcp_servers.medcp]` block to `~/.codex/config.toml`. Verify with
`codex mcp get medcp`. On Windows, add the block from `config.snippet.toml` to
`%USERPROFILE%\.codex\config.toml` manually (or run `install.sh` under WSL/Git
Bash). Restart Codex and ask it to use MedCP.

---

## Rebuild from source

```bash
python3 scripts/build_releases.py          # regenerates every artifact here
```

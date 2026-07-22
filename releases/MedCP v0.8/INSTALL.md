# MedCP v0.8 — install guide

Per-OS install instructions for the four official MedCP integration artifacts.
Every artifact wraps the **same** shared `medcp` core: read-only clinical
records over SQL Server / MySQL / SQLite, plus the optional SPOKE knowledge
graph.

| Artifact | Agent | Install section |
|---|---|---|
| `MedCP.brxt` | BioRouter | [BioRouter](#biorouter) |
| `medcp-claude-code-plugin.zip` | Claude Code | [Claude Code](#claude-code) |
| `medcp-codex.zip` | Codex CLI | [Codex CLI](#codex-cli) |
| `MedCP.mcpb` | Claude Desktop | [Claude Desktop](#claude-desktop) |

Verify downloads against [`checksums.txt`](checksums.txt).

## Prerequisites

- **[uv](https://docs.astral.sh/uv/)** — provides `uvx` / `uv`. Required by the
  three uvx-based integrations (BioRouter, Claude Code, Codex CLI); BioRouter
  also runs `uv sync` on install. **Claude Desktop does not need it** — the
  `.mcpb` bundles its own Python runtime and database drivers.
  - macOS / Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
  - Windows (PowerShell): `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`
- The target agent (BioRouter, Claude Code, Codex CLI, or Claude Desktop)
  already installed.
- Your EHR connection details, or a local `.sqlite` file for the `sqlite`
  backend.

### Backend selection (identical for every integration)

Set `CLINICAL_RECORDS_BACKEND` to one of:

- `sqlite` → also set `CLINICAL_RECORDS_SQLITE_PATH` (absolute path to the file)
- `mysql`  → set `CLINICAL_RECORDS_SERVER` / `_DATABASE` / `_USERNAME` / `_PASSWORD` (+ optional `_PORT`)
- `mssql`  → same four (SQL Server; the core default)

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

- `--env` sets a plain variable; `--secret` stores the value in the OS keyring.
- List / remove: `biorouter extension list` · `biorouter extension remove medcp`
- Windows paths: use the full path, e.g.
  `--env CLINICAL_RECORDS_SQLITE_PATH=C:\data\omop.sqlite`
- Start a session and ask MedCP to list tables or summarize patients. BioRouter
  auto-loads the bundled `medcp-clinical-records` skill.

---

## Claude Code

`medcp-claude-code-plugin.zip` is a Claude Code plugin. Its `.mcp.json` launches
`uvx … medcp`, so no server is bundled. Works on any OS with `uvx`.

**Option A — plugin (recommended).** Unzip it and add it via the bundled
marketplace, or point Claude Code at the repo's `integrations/` directory:

```bash
# in a Claude Code session
/plugin marketplace add /path/to/MedCP/integrations
/plugin install medcp@medcp-integrations
```

**Option B — register the MCP server directly:**

```bash
claude mcp add medcp -- uvx --from git+https://github.com/BaranziniLab/MedCP@v0.8.0 medcp
```

Set the backend variables in your shell before starting `claude` (macOS/Linux
`export NAME=value`; Windows PowerShell `$env:NAME="value"`). For a local core
build instead of the release, `export MEDCP_SOURCE=/path/to/MedCP`.

Then run `/medcp-explore`, or just ask Claude to query the clinical tables.

---

## Codex CLI

`medcp-codex.zip` contains a config snippet and an installer that runs
`codex mcp add`. The installer (`install.sh`) is a Bash script, so it runs on
macOS and Linux natively, and on Windows under WSL or Git Bash.

```bash
unzip medcp-codex.zip -d medcp-codex && cd medcp-codex
chmod +x install.sh

export CLINICAL_RECORDS_BACKEND=sqlite
export CLINICAL_RECORDS_SQLITE_PATH=/absolute/path/to/database.sqlite
./install.sh                      # or: ./install.sh --env-file /path/to/.env
```

This writes an `[mcp_servers.medcp]` block to `~/.codex/config.toml`. Verify with
`codex mcp get medcp`. For a local core build instead of the release, set
`MEDCP_SOURCE=/path/to/MedCP` before running `install.sh`.

On Windows without WSL/Git Bash, add the block from `config.snippet.toml` to
`%USERPROFILE%\.codex\config.toml` manually. Restart Codex and ask it to use
MedCP.

---

## Claude Desktop

`MedCP.mcpb` is a Claude Desktop extension (MCPB bundle) with a self-contained
Python runtime and the SQL Server / MySQL / SQLite drivers built in — no `uv`
required. Runs on macOS 11+ and Windows 10+ (Claude Desktop 1.0.0+ with MCPB
support).

1. **Install** — double-click `MedCP.mcpb`. Claude Desktop opens an install
   dialog; click **Install**.
2. **Configure** — complete the configuration wizard, or open
   **Settings → Extensions → MedCP** later. The wizard exposes the same settings
   as labeled fields: pick the `CLINICAL_RECORDS_BACKEND`, then fill in the
   matching backend fields (SQLite path, or server/database/username/password)
   and optional SPOKE knowledge-graph fields.
3. Credentials marked sensitive (e.g. `CLINICAL_RECORDS_PASSWORD`) are stored in
   the OS keychain. Restart Claude Desktop after changing configuration, then
   ask it to list the clinical tables or summarize patients.

---

## Rebuild from source

```bash
python3 scripts/build_releases.py    # regenerates MedCP.brxt, both .zip artifacts, INSTALL.md, checksums.txt
```

`MedCP.mcpb` is packaged separately with `mcpb pack` from the repository root.

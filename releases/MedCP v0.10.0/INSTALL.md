# MedCP v0.10.0 install guide

These four artifacts all launch the same MCP 2026-07-28-compatible MedCP core:

| Artifact | Host | Runtime |
| --- | --- | --- |
| `MedCP.brxt` | BioRouter | `uv` resolves the locked extension |
| `medcp-claude-code-plugin.zip` | Claude Code | `uvx` |
| `medcp-codex.zip` | Codex CLI | `uvx` |
| `MedCP.mcpb` | Claude Desktop | bundled macOS arm64 Python |

Verify downloads against `checksums.txt`:

```bash
shasum -a 256 -c checksums.txt
```

## Configuration

No configuration is required for knowledge-graph-only use: MedCP connects to its
bundled read-only SPOKE endpoint. Set `MEDCP_DISABLE_KNOWLEDGE_GRAPH=1` for
EHR-only use.

For EHR access, choose one backend:

- SQLite: set `CLINICAL_RECORDS_BACKEND=sqlite` and
  `CLINICAL_RECORDS_SQLITE_PATH=/absolute/path/database.sqlite`.
- MySQL: set `CLINICAL_RECORDS_BACKEND=mysql` plus
  `CLINICAL_RECORDS_SERVER`, `CLINICAL_RECORDS_DATABASE`,
  `CLINICAL_RECORDS_USERNAME`, `CLINICAL_RECORDS_PASSWORD`, and optionally
  `CLINICAL_RECORDS_PORT`.
- SQL Server: use the same variables with
  `CLINICAL_RECORDS_BACKEND=mssql`.

MedCP validates EHR queries before execution, opens SQLite read-only, starts
MySQL queries in a read-only transaction, and rolls remote connections back.
For defense in depth, configure MySQL and SQL Server with a dedicated account
that has `SELECT` and no write-capable grants; never use an administrator
credential for an agent-facing server.

## BioRouter

```bash
biorouter extension install MedCP.brxt \
  --env CLINICAL_RECORDS_BACKEND=sqlite \
  --env CLINICAL_RECORDS_SQLITE_PATH=/absolute/path/database.sqlite
```

Use BioRouter's `--secret` option for passwords so BioRouter can place them in
its configured credential store.

## Claude Code

Unzip `medcp-claude-code-plugin.zip`, add its parent as a local marketplace, and
install `medcp@medcp-integrations`. The plugin inherits MedCP configuration from
the environment used to start Claude Code.

## Codex CLI

```bash
unzip medcp-codex.zip -d medcp-codex
cd medcp-codex
./install.sh
codex mcp get medcp
```

Export MedCP variables before running the installer, or pass
`--env-file /absolute/path/to/file`. Use `MEDCP_NAME=medcp-next` for a
side-by-side canary registration.

## Claude Desktop

Double-click `MedCP.mcpb`, approve the installation, and configure it under
**Settings -> Extensions -> MedCP**. This release's embedded runtime is for
macOS on Apple silicon; do not relabel it as a Windows, Linux, or Intel-macOS
bundle. Values marked sensitive in the manifest are stored by Claude Desktop
using its protected configuration mechanism.

For complete configuration, source-build, protocol, and validation details, see
the repository `README.md`.

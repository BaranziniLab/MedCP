# MedCP — Claude Code plugin

Adds MedCP's MCP tools (`list_clinical_tables`, `query_clinical_records`,
`query_knowledge_graph`, `get_knowledge_graph_schema`) to
[Claude Code](https://claude.com/claude-code). The plugin does not bundle the
server — its [`.mcp.json`](.mcp.json) launches the shared `medcp` core with
`uvx`, so you always run the same engine as every other MedCP target.

## What's in here

```
claude-code/
├── .claude-plugin/plugin.json   # plugin metadata
├── .mcp.json                    # launches `uvx … medcp` as an MCP server
├── commands/medcp-explore.md    # /medcp-explore slash command
└── README.md
```

## Requirements

- Claude Code (`claude`) 2.x+
- [`uv`](https://docs.astral.sh/uv/) on your PATH (provides `uvx`)

## Configuration

The plugin passes MedCP's environment variables through to the server. Set the
ones you need in your shell (or a project `.env` you `source`) before starting
Claude Code:

```bash
# Local SQLite EHR (e.g. the bundled sham OMOP dataset)
export CLINICAL_RECORDS_BACKEND=sqlite
export CLINICAL_RECORDS_SQLITE_PATH=/absolute/path/to/database.sqlite

# — or MySQL —
export CLINICAL_RECORDS_BACKEND=mysql
export CLINICAL_RECORDS_SERVER=db.example.org
export CLINICAL_RECORDS_DATABASE=omop
export CLINICAL_RECORDS_USERNAME=reader
export CLINICAL_RECORDS_PASSWORD=•••••

# — or SQL Server —
export CLINICAL_RECORDS_BACKEND=mssql
export CLINICAL_RECORDS_SERVER=ehr.hospital.org
export CLINICAL_RECORDS_DATABASE=OMOP_DEID
export CLINICAL_RECORDS_USERNAME=reader
export CLINICAL_RECORDS_PASSWORD=•••••
```

`MEDCP_SOURCE` controls which build of the core is launched. It defaults to the
pinned GitHub release; point it at a local checkout for development:

```bash
export MEDCP_SOURCE=/path/to/MedCP     # run your local core instead of the release
```

## Install

### As a local plugin (development)

```bash
# From a Claude Code session, add this marketplace directory, then install:
/plugin marketplace add /path/to/MedCP/integrations
/plugin install medcp@medcp-integrations
```

> The marketplace manifest is [`../.claude-plugin/marketplace.json`](../.claude-plugin/marketplace.json).

### Quick, without the plugin system

You can also register the same server directly:

```bash
claude mcp add medcp -- uvx --from git+https://github.com/BaranziniLab/MedCP@v0.8.0 medcp
```

## Use

```
/medcp-explore
```

or just ask, e.g. *"List the clinical tables, then count patients by gender."*
Claude will call the read-only MedCP tools.

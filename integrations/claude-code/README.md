# MedCP — Claude Code plugin

Adds MedCP's read-only MCP tools to [Claude Code](https://claude.com/claude-code):

- `MedCP-list_clinical_tables`, `MedCP-query_clinical_records`
- `MedCP-query_knowledge_graph`, `MedCP-get_knowledge_graph_schema` — registered only when a knowledge graph is configured

Tool names are namespaced with the `MEDCP_NAMESPACE` prefix (default `MedCP`). The plugin does not bundle the server — its [`.mcp.json`](.mcp.json) launches the shared `medcp` core with `uvx`, so you always run the same engine as every other MedCP integration.

Sections: [What's in here](#whats-in-here) · [Requirements](#requirements) · [Configuration](#configuration) · [Install](#install) · [Use](#use)

## What's in here

```text
claude-code/
├── .claude-plugin/plugin.json   # plugin metadata
├── .mcp.json                    # launches `uvx … medcp` as an MCP server
├── commands/medcp-explore.md    # /medcp-explore slash command
└── README.md
```

## Requirements

- Claude Code (`claude`) 2.x or newer
- [`uv`](https://docs.astral.sh/uv/) on your `PATH` (provides `uvx`)

## Configuration

The plugin passes MedCP's environment variables through to the server. Set the
ones you need in your shell (or a project `.env` you `source`) before starting
Claude Code.

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

For the MySQL and SQL Server backends, `CLINICAL_RECORDS_PORT` is optional. The
clinical database itself is optional too — omit every `CLINICAL_RECORDS_*`
variable to run MedCP as a SPOKE-only tool.

The knowledge graph defaults to the bundled **SPOKE production graph** with no
credentials. Set `KNOWLEDGE_GRAPH_URI` / `_USERNAME` / `_PASSWORD` / `_DATABASE`
only to use your own Neo4j graph instead (or `MEDCP_DISABLE_KNOWLEDGE_GRAPH=1` to
turn it off).

`MEDCP_SOURCE` controls which build of the core is launched. It defaults to the
pinned GitHub release; point it at a local checkout for development:

```bash
export MEDCP_SOURCE=/path/to/MedCP     # run your local core instead of the release
```

## Install

### As a local plugin (development)

From a Claude Code session, add this marketplace directory, then install the
plugin:

```text
/plugin marketplace add /path/to/MedCP/integrations
/plugin install medcp@medcp-integrations
```

The marketplace manifest is [`../.claude-plugin/marketplace.json`](../.claude-plugin/marketplace.json).

### Quick, without the plugin system

You can also register the same server directly:

```bash
claude mcp add medcp -- uvx --from git+https://github.com/BaranziniLab/MedCP@v0.8.0 medcp
```

## Use

Run the bundled slash command:

```text
/medcp-explore
```

Or just ask, e.g. *"List the clinical tables, then count patients by gender."*
Claude will call the read-only MedCP tools.

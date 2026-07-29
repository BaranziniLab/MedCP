# MedCP: Medical Model Context Protocol <img src="assets/logo.png" align="right" alt="MedCP Logo" width="100"/>

<br>

**Contents:** [Overview](#overview) · [MCP compatibility](#mcp-compatibility) · [Integrations](#integrations) · [Installation](#installation) · [Configuration](#configuration) · [Usage](#usage-examples) · [Testing](#testing) · [Release build](#release-build) · [Troubleshooting](#troubleshooting) · [Legal](#data-privacy-and-legal-disclaimer)

## Overview

**MedCP** gives an AI agent read-only tools for electronic health records and
biomedical knowledge graphs. The MCP server runs on your machine; database
queries execute against the local file or remote database endpoints you
configure, and tool results are returned to the host agent. One shared core is
packaged for **Claude Code**, **Codex CLI**, **BioRouter**, and **Claude
Desktop**. If a plain Python function-calling version is of interest, see
[fMedCP](https://github.com/BaranziniLab/fMedCP).

![MedCP architecture schematic](assets/schematics.png)

### Key Features

- **Local MCP server** - The tool process runs on your machine over stdio
- **EHR Integration** - Query electronic health records with natural language
- **Pluggable SQL backend** - Point MedCP at **SQL Server**, **MySQL/MariaDB**, or a **local SQLite** file
- **Runs in your agent** - One shared core, packaged for **Claude Code**, **Codex CLI**, **BioRouter**, and **Claude Desktop**
- **Biomedical Knowledge** - Access comprehensive drug-disease associations and protein interactions
- **Real-time Analysis** - Instant clinical decision support
- **Read-only guards** - SQLite is opened read-only, and SQL/Cypher mutation statements are rejected

## MCP compatibility

MedCP v0.10.0 uses the official Python SDK `mcp==2.0.0` and implements the
[MCP 2026-07-28 revision](https://blog.modelcontextprotocol.io/posts/2026-07-28/).
The release supports:

- sessionless modern requests with `server/discover`;
- required modern request metadata and protocol-version validation;
- `resultType` on complete modern results;
- private five-minute cache hints on `server/discover` and `tools/list`;
- snake-case tool annotations from the 2026 schema; and
- the SDK's legacy initialization path for current hosts that still negotiate an
  older MCP revision.

The production entry point is deliberately **stdio-only**. HTTP deployment of
clinical-data tools requires a separate authentication, origin-validation, and
data-governance review. Optional 2026 capabilities such as tasks, elicitation,
and extension-specific transports are not advertised.

Current Codex and BioRouter releases may still use legacy `initialize` /
`notifications/initialized`. Their host smoke tests therefore prove backward
interoperability; the modern sessionless path is covered separately by raw-wire
tests that exercise `server/discover`, discovery metadata, caching fields, tool
calls, error codes, and stdout purity.

### What changed in v0.10.0

- Replaced the FastMCP compatibility layer with the official `MCPServer` API
  from `mcp==2.0.0`.
- Converted tool returns to typed `CallToolResult` / `TextContent` responses and
  updated annotations to the 2026 snake-case schema.
- Added modern discovery and caching metadata while retaining the SDK's
  legacy-client path for currently released hosts.
- Kept the deployable server stdio-only and removed dormant network-listener
  arguments.
- Added modern/legacy raw-wire tests, cross-platform CI, namespace validation,
  version-consistency gates, a locked embedded runtime, reproducible MCPB
  packaging, and full-patch release directories.
- Added backend-specific MySQL and SQL Server benchmark variables so both AWS
  fixtures can be validated in the same run.
- Hardened clinical SQL validation against comments, stacked statements, and
  read-prefixed write forms; MySQL calls also run in an explicit read-only
  transaction and every remote connection is rolled back before close.
- Changed AWS fixture provisioning to retain the RDS administrator only for
  setup and load, create a dedicated SELECT-only reader for MedCP, and verify
  effective reader permissions in the live backend gate.

### Integrations

The MedCP server is exposed to several AI coding agents through thin, cleanly
separated layers in [`integrations/`](integrations/README.md) — all launching the
same shared core in [`src/medcp/`](src/medcp):

| Agent | Integration | Prebuilt artifact |
| --- | --- | --- |
| **Claude Code** | [`integrations/claude-code`](integrations/claude-code) (plugin) | `medcp-claude-code-plugin.zip` |
| **Codex CLI** | [`integrations/codex`](integrations/codex) (MCP server) | `medcp-codex.zip` |
| **BioRouter** | [`integrations/biorouter`](integrations/biorouter) (`.brxt` extension) | `MedCP.brxt` |
| **Claude Desktop** | root [`manifest.json`](manifest.json) (`.mcpb`) | `MedCP.mcpb` |

Built artifacts and install steps live in the
[current release directory](releases/MedCP%20v0.10.0). The
[`releases/`](releases) index explains the current-tree retention policy.
Rebuild the Claude Code, Codex, BioRouter, and Claude Desktop artifacts with
`python3 scripts/build_releases.py`.

## Prerequisites

Requirements depend on how you run MedCP.

### For the Claude Desktop extension

- **Claude Desktop** 1.0.0+ with MCPB extension support
- **Operating system**: macOS on Apple silicon for the bundled v0.10.0 runtime
- **Python**: included (standalone runtime bundled with the extension)
- **Memory**: 8 GB RAM minimum, 16 GB recommended

Python and all dependencies ship inside the extension. Windows, Linux, and
Intel-macOS MCPB artifacts require separately built native runtimes; the v0.10.0
bundle does not claim compatibility with those platforms.

### For uvx and the agent integrations

- **[uv](https://docs.astral.sh/uv/)** — provides `uvx`/`uv`, used to launch the shared core for [Option 2](#option-2-run-with-uvx-universal) and for the Claude Code, Codex CLI, and BioRouter [integrations](#integrations).

## Installation

### Option 1: Quick Install (Claude Desktop Extension)

1. **Download the Extension**
   - Go to the [current release directory](releases/MedCP%20v0.10.0)
   - Download the latest `MedCP.mcpb` file

2. **Install in Claude Desktop**
   - Double-click the `MedCP.mcpb` file
   - Claude Desktop will open the installation dialog
   - Click **"Install"**

3. **Configure MedCP**
   - Complete the configuration wizard that appears
   - Leave all database fields blank for the bundled read-only SPOKE graph, or
     configure one EHR backend as described below

That's it!

### Option 2: Run with uvx (Universal)

Run MedCP from the pinned release using `uvx`. No configuration is required for
knowledge-graph-only use because the bundled read-only SPOKE connection is the
default.

```bash
# Knowledge graph only: no environment variables needed
uvx --from git+https://github.com/BaranziniLab/MedCP@v0.10.0 medcp
```

To add a local SQLite EHR:

```bash
export CLINICAL_RECORDS_BACKEND=sqlite
export CLINICAL_RECORDS_SQLITE_PATH=/absolute/path/to/database.sqlite
uvx --from git+https://github.com/BaranziniLab/MedCP@v0.10.0 medcp
```

For MySQL or SQL Server, set `CLINICAL_RECORDS_BACKEND` to `mysql` or
`mssql`, then provide the server, database, username, password, and optional
port variables from the [configuration table](#electronic-health-records-optional).

Tool names are prefixed with `MEDCP_NAMESPACE` (default `MedCP`).

- If only Knowledge Graph is configured, you'll have access to:
  - `MedCP-get_knowledge_graph_schema` - List all biomedical entities and relationships
  - `MedCP-query_knowledge_graph` - Query drug-disease associations, protein interactions, etc.

- If only Clinical Records is configured, you'll have access to:
  - `MedCP-list_clinical_tables` - List available EHR tables
  - `MedCP-query_clinical_records` - Query patient records with SQL

- If both are configured, you'll have access to all tools for integrated analysis

Or run the exact locked environment from a local clone:

```bash
git clone https://github.com/BaranziniLab/MedCP.git
cd MedCP
uv sync --locked
uv run --locked medcp
```


## Configuration

After installation, you'll need to configure your database connections in Claude Desktop:

**Settings → Extensions → MedCP**

### Biomedical Knowledge Graph (optional)

**MedCP connects to the SPOKE knowledge graph by default — no credentials
required.** SPOKE ([Morris et al., 2023](https://academic.oup.com/bioinformatics/article/39/2/btad080/7033465))
contains comprehensive biomedical relationships including drug-disease
associations, protein interactions, and biological pathways, and its read-only
production connection ships built in. Leave every `KNOWLEDGE_GRAPH_*` variable
unset to use it.

To use **your own** Neo4j / compatible knowledge graph instead, set the following
(these credentials are for *your* graph, not SPOKE). To turn the knowledge graph
off entirely, set `MEDCP_DISABLE_KNOWLEDGE_GRAPH=1`.

| Parameter | Description | Example |
|-----------|-------------|---------|
| **`KNOWLEDGE_GRAPH_URI`** | Your Neo4j connection URI | `bolt://your-neo4j-server:7687` |
| **`KNOWLEDGE_GRAPH_USERNAME`** | Your Neo4j username | `neo4j` |
| **`KNOWLEDGE_GRAPH_PASSWORD`** | Your Neo4j password | `your_secure_password` |
| **`KNOWLEDGE_GRAPH_DATABASE`** | Your Neo4j database name | `neo4j` |

### Electronic Health Records (optional)

Configuring an EHR database is **optional** — omit every `CLINICAL_RECORDS_*`
variable and MedCP runs as a SPOKE-only knowledge-graph tool. To connect clinical
records, MedCP supports three SQL backends, selected with
**`CLINICAL_RECORDS_BACKEND`**. Fill in only the settings for the backend you
choose (the credentials below are for *your* database). For UCSF users, see the
[UCSF Research Data](https://data.ucsf.edu/research/ucsf-data) portal for access
information.

**`mssql` (SQL Server, default) / `mysql` (MySQL / MariaDB):**

| Parameter | Description | Example |
|-----------|-------------|---------|
| **`CLINICAL_RECORDS_BACKEND`** | `mssql` or `mysql` | `mssql` |
| **`CLINICAL_RECORDS_SERVER`** | Database hostname | `your-ehr-server.hospital.org` |
| **`CLINICAL_RECORDS_DATABASE`** | Clinical database name | `OMOP_DEID` |
| **`CLINICAL_RECORDS_USERNAME`** | Database username | `clinical_user` |
| **`CLINICAL_RECORDS_PASSWORD`** | Database password | `secure_clinical_password` |
| **`CLINICAL_RECORDS_PORT`** | TCP port (optional) | `1433` / `3306` |

**`sqlite` (local file):**

| Parameter | Description | Example |
|-----------|-------------|---------|
| **`CLINICAL_RECORDS_BACKEND`** | `sqlite` | `sqlite` |
| **`CLINICAL_RECORDS_SQLITE_PATH`** | Absolute path to the `.sqlite` file | `/data/omop.sqlite` |

The SQLite backend opens the file **read-only** and needs no server or
credentials — ideal for local testing (e.g. the OMOP dataset in
[`benchmarks/sham-dataset`](benchmarks/sham-dataset)).

### Optional Settings

| Parameter | Description | Default |
|-----------|-------------|---------|
| **`MEDCP_DISABLE_KNOWLEDGE_GRAPH`** | Set to `1` for EHR-only mode | `0` |
| **`MEDCP_NAMESPACE`** | Tool-name prefix | `MedCP` |
| **`MEDCP_LOG_LEVEL`** | `DEBUG`, `INFO`, `WARNING`, or `ERROR` | `INFO` |

### Credential handling

Credential storage is controlled by the host, not by the MedCP server:

- Claude Desktop stores manifest fields marked sensitive using its protected
  configuration mechanism.
- BioRouter can store values supplied with its secret-setting flow in its
  configured keyring.
- Codex, Claude Code, and direct shell launches pass configuration through the
  process environment or host configuration. A `.env` file or TOML entry is
  plaintext at rest unless you protect it separately.

Never commit credentials, paste them into agent prompts, or include literal
passwords in reusable shell commands. Restrict any local environment file to
its owner (for example, `chmod 600 file`) and use institution-approved,
least-privilege, read-only database accounts.

## Usage Examples

### Query Patient Records
```text
"Find all patients diagnosed with diabetes in the last 6 months and summarize their HbA1c trends"
```

### Drug Interaction Analysis
```text
"Check for interactions between metformin, lisinopril, and atorvastatin for a 65-year-old patient with CKD stage 3"
```

### Clinical Guidelines
```text
"What are the current evidence-based guidelines for treating community-acquired pneumonia in elderly patients?"
```

### Biomedical Research
```text
"Find protein targets associated with Alzheimer's disease and identify potential drug compounds that interact with these proteins"
```

## Testing

The network-free protocol and SQLite suite covers modern and legacy MCP modes,
tool discovery metadata, cache hints, version errors, namespace validation,
read-only enforcement, real stdio framing, and stdout purity:

```bash
uv sync --locked
uv run --locked pytest tests
```

A synthetic OMOP dataset and the live backend harness live in
[`benchmarks/sham-dataset`](benchmarks/sham-dataset); they contain no real
patient data. SQLite needs no setup:

```bash
uv run --locked python benchmarks/sham-dataset/test_backends.py
```

The live harness expects 32 tables and 100 people, verifies that the MedCP
validator rejects a forbidden statement, checks that hosted identities have
SELECT but no write-capable database grants, and queries the default SPOKE
graph. It discovers hosted backends from backend-specific variables:

| Backend | Variables |
| --- | --- |
| MySQL | `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE` |
| SQL Server | `MSSQL_HOST`, `MSSQL_PORT`, `MSSQL_USER`, `MSSQL_PASSWORD`, `MSSQL_DATABASE` |

Backend-specific names take precedence over the deprecated shared `DB_*`
fallbacks, so both hosted databases can be tested in one process:

```bash
source benchmarks/sham-dataset/mysql/.dbenv
source benchmarks/sham-dataset/mssql/.dbenv
uv run --locked python benchmarks/sham-dataset/test_backends.py
```

The `mysql/` and `mssql/` directories include provisioning and teardown scripts
for disposable AWS RDS fixtures. Provisioning loads data with the administrator,
then creates a dedicated SELECT-only `medcpreader`. The git-ignored, mode-0600
`.dbenv` contains only that reader's **plaintext** benchmark credential, never
the administrator password. Use short-lived test credentials, do not reuse
production secrets, and delete fixtures you created when validation is
complete:

```bash
cd benchmarks/sham-dataset/mysql
read -rsp 'Temporary RDS admin password: ' DB_ADMIN_PASSWORD
export DB_ADMIN_PASSWORD
./provision.sh
unset DB_ADMIN_PASSWORD
source ./.dbenv
uv run --directory ../../.. --locked python benchmarks/sham-dataset/test_backends.py
./teardown.sh
```

Do not run a teardown script against a shared or pre-existing database. See the
[benchmark README](benchmarks/sham-dataset/README.md) for the full AWS workflow.

### Host MCP smoke tests

Use a temporary registration name and namespace so validation does not replace
an existing MedCP integration. Pass `CLINICAL_RECORDS_*`,
`KNOWLEDGE_GRAPH_*`, and `MEDCP_NAMESPACE` explicitly through the host's MCP
configuration or a mode-0700 launcher; do not assume the host forwards its
parent shell environment.

For Codex, create the `medcp-next` checkout registration described in
[`integrations/codex`](integrations/codex), then run an ephemeral, read-only
turn:

```bash
codex exec --ephemeral --json -C /absolute/path/to/MedCP -s read-only \
  'Use only medcp-next. List clinical tables, run SELECT COUNT(*) AS n FROM person, and query MATCH (d:Disease) RETURN count(d) AS n with empty parameters. Return exact tool names and raw outputs.'
```

For BioRouter, follow the isolated-workflow canary in
[`integrations/biorouter`](integrations/biorouter). BioRouter 1.88.6 can
otherwise route an ephemeral `medcp`-prefixed tool to an already enabled
`medcp` extension even when the MCP namespaces differ.

For AWS MySQL or SQL Server, map the corresponding backend-specific values from
the protected `.dbenv` into `CLINICAL_RECORDS_*` before starting the host. Do
not put literal passwords in the command line or prompt.

### Verified release matrix

The v0.10.0 release candidate was verified on 2026-07-29 with synthetic OMOP
data and aggregate read-only queries:

| Client path | SQLite EHR | AWS MySQL EHR | AWS SQL Server EHR | SPOKE knowledge graph |
| --- | --- | --- | --- | --- |
| Direct MCP harness | 32 tables; 100 people; file and validator read-only | 32 tables; 100 people; validator and SELECT-only grants verified | 32 tables; 100 people; validator and SELECT-only grants verified | 117 schema entities; 12,275 Disease nodes |
| Codex CLI 0.145.0 | 32 tables; 100 people | 32 tables; 100 people via SELECT-only reader | 32 tables; 100 people via SELECT-only reader | 12,275 Disease nodes |
| BioRouter 1.88.6 | 32 tables; 100 people | 32 tables; 100 people via SELECT-only reader | 32 tables; 100 people via SELECT-only reader | 12,275 Disease nodes |

Codex called `MedCPNext-list_clinical_tables`,
`MedCPNext-query_clinical_records`, and
`MedCPNext-query_knowledge_graph`. BioRouter called the same MCP tools through
its `medcp__MedCPNext-*` host prefix. Both released hosts negotiated the legacy
MCP initialization fallback; raw-stdio tests separately verified the modern
2026-07-28 `server/discover` path.

After the final release build, both hosts repeated the EHR and knowledge-graph
queries by launching the exact source and lock extracted from the generated
`MedCP.brxt`, rather than an older installed extension.

The existing `medcp-mysql` and `medcp-mssql` fixtures were confirmed
`available` in AWS `us-west-2`, migrated from administrator-bearing test
configuration to generated SELECT-only readers, and reused for this validation.
They were not created or torn down by the release test.

## Release build

The release builder verifies every version-bearing manifest, regenerates the
standalone server mirror, resolves BioRouter's lock, synchronizes the MCPB
runtime from the root production lock, validates and inspects the MCPB, writes
the install guide, and hashes every artifact:

```bash
python3 scripts/build_releases.py
```

Artifacts are written to `releases/MedCP v0.10.0/`. The MCPB build requires
`uv`, `mcpb`, and macOS on Apple silicon. Targeted rebuilds are available with
`--only biorouter`, `--only claude-code`, `--only codex`, or `--only mcpb`;
checksums for existing artifacts are preserved during a targeted rebuild.

Before publishing a release, run:

```bash
uv run --locked pytest tests
mcpb validate manifest.json
mcpb info 'releases/MedCP v0.10.0/MedCP.mcpb'
```

The repository CI repeats the network-free test suite on Python 3.11, 3.12, and
3.13 across Linux, macOS, and Windows.

## Troubleshooting

### Extension Not Loading
1. Verify Claude Desktop supports MCPB extensions
2. Check that all required configuration fields are completed
3. Restart Claude Desktop after configuration changes

### Database Connection Issues
1. Verify server URLs are accessible from your network
2. Check that credentials are valid and not expired
3. Ensure firewall allows database connections
4. Test connectivity outside Claude Desktop if possible

### Performance Issues
1. Limit query result sizes for large datasets
2. Use specific date ranges in clinical queries
3. Check available system memory

### Need Help?
- **Documentation**: Check the configuration examples above
- **Bug Reports**: [Create an issue](../../issues)
- **Security Issues**: Contact the development team privately

## Data Privacy and Legal Disclaimer

**IMPORTANT NOTICE — DATA PRIVACY, COMPLIANCE, AND LIMITATION OF LIABILITY**

MedCP is a software tool designed to facilitate access to electronic health records and biomedical data through local, institution-controlled infrastructure. By installing, configuring, or using MedCP in any capacity, you acknowledge and agree to the following:

1. **Institutional Compliance Responsibility.** It is the sole responsibility of the user to ensure that all use of this tool complies with the data governance policies, privacy regulations, and data use agreements applicable to their institution, including but not limited to the Health Insurance Portability and Accountability Act (HIPAA), the General Data Protection Regulation (GDPR), the California Consumer Privacy Act (CCPA), and any other applicable federal, state, local, or international laws and regulations governing the collection, storage, access, and use of personal health information or sensitive data.

2. **No Warranty of Regulatory Compliance.** MedCP is provided "as is," without warranty of any kind, express or implied. The authors, developers, and affiliated institutions make no representations or warranties that the use of this tool will satisfy any specific regulatory, legal, or institutional data privacy requirement. Users are solely responsible for obtaining any necessary institutional review board (IRB) approvals, data use agreements, or other authorizations required before accessing or processing any patient data.

3. **Limitation of Liability.** To the fullest extent permitted by applicable law, the authors, contributors, and affiliated institutions (including the Baranzini Lab and the University of California, San Francisco) shall not be liable for any direct, indirect, incidental, special, consequential, or punitive damages arising out of or related to the use, misuse, or inability to use this tool, including but not limited to any unauthorized access to or disclosure of protected health information, any violation of applicable privacy laws or institutional data use policies, or any other improper or unlawful use of this software or the data accessed through it.

4. **User Accountability.** Any misuse, unauthorized sharing, or improper handling of data accessed through MedCP is the exclusive responsibility of the user. The authors disclaim all liability for actions taken by users that violate applicable laws, regulations, or institutional policies.

5. **No Clinical Advice.** MedCP is intended solely as a research and informational tool. It does not constitute medical advice, clinical decision support approved for patient care, or a validated clinical diagnostic system. It must not be used as the sole basis for any clinical or medical decisions.

By using this software, you confirm that you have read, understood, and agreed to this disclaimer, and that you will use MedCP in full accordance with all applicable legal and institutional requirements.

---

## License

MedCP is released under the [MIT License](LICENSE).

## Authors and Maintainers

**MedCP** is developed and maintained by the [Baranzini Lab](https://baranzinilab.ucsf.edu/) at UCSF.

- **Wanjun Gu** - [wanjun.gu@ucsf.edu](mailto:wanjun.gu@ucsf.edu)
- **Gianmarco Bellucci** - [gianmarco.bellucci@ucsf.edu](mailto:gianmarco.bellucci@ucsf.edu)

## Acknowledgments

- **SPOKE Knowledge Graph**: [Morris et al., 2023](https://academic.oup.com/bioinformatics/article/39/2/btad080/7033465)
- **UCSF Clinical Data**: [UCSF Research Data Portal](https://data.ucsf.edu/research/ucsf-data)
- **Desktop Extensions**: Built using Model Context Protocol Bundle (MCPB) format
- **Model Context Protocol**: Enables secure local AI integration

<div align="center">
  <p><a href="../../releases">Download MedCP Extension</a> | <a href="../../issues">Report Issues</a> | <a href="mailto:wanjun.gu@ucsf.edu">Contact</a></p>
</div>

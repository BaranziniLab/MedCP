# MedCP: Medical Model Context Protocol <img src="assets/logo.png" align="right" alt="MedCP Logo" width="100"/>

<br>

**Contents:** [Overview](#overview) · [Integrations](#integrations) · [Installation](#installation) · [Configuration](#configuration) · [Usage](#usage-examples) · [Testing](#testing) · [Troubleshooting](#troubleshooting) · [Legal](#data-privacy-and-legal-disclaimer)

## Overview

**MedCP** gives your AI agent **secure, local access** to electronic health records and biomedical knowledge graphs. Sensitive health data is processed entirely on your machine, and one shared core is packaged for **Claude Code**, **Codex CLI**, **BioRouter**, and **Claude Desktop**. If a plain Python function-calling version of this software is of interest, please check out [fMedCP](https://github.com/BaranziniLab/fMedCP), which can be run directly from the terminal.

![MedCP architecture schematic](assets/schematics.png)

### Key Features

- **Local Processing** - All data processing happens on your machine
- **EHR Integration** - Query electronic health records with natural language
- **Pluggable SQL backend** - Point MedCP at **SQL Server**, **MySQL/MariaDB**, or a **local SQLite** file
- **Runs in your agent** - One shared core, packaged for **Claude Code**, **Codex CLI**, **BioRouter**, and **Claude Desktop**
- **Biomedical Knowledge** - Access comprehensive drug-disease associations and protein interactions
- **Real-time Analysis** - Instant clinical decision support
- **Secure Storage** - Credentials encrypted in OS keychain

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

Built artifacts and per-OS install steps live in the latest
[`releases/`](releases) folder (see `INSTALL.md` there). Rebuild the Claude Code,
Codex, and BioRouter artifacts with `python3 scripts/build_releases.py`; the
Claude Desktop `MedCP.mcpb` is packaged separately with `mcpb pack`.

## Prerequisites

Requirements depend on how you run MedCP.

### For the Claude Desktop extension

- **Claude Desktop** 1.0.0+ with MCPB extension support
- **Operating system**: macOS 11+ or Windows 10+
- **Python**: included (standalone runtime bundled with the extension)
- **Memory**: 8 GB RAM minimum, 16 GB recommended

Python and all dependencies ship inside the extension — just install Claude Desktop from [claude.ai/download](https://claude.ai/download).

### For uvx and the agent integrations

- **[uv](https://docs.astral.sh/uv/)** — provides `uvx`/`uv`, used to launch the shared core for [Option 2](#option-2-run-with-uvx-universal) and for the Claude Code, Codex CLI, and BioRouter [integrations](#integrations).

## Installation

### Option 1: Quick Install (Claude Desktop Extension)

1. **Download the Extension**
   - Go to [Releases](../../releases)
   - Download the latest `MedCP.mcpb` file

2. **Install in Claude Desktop**
   - Double-click the `MedCP.mcpb` file
   - Claude Desktop will open the installation dialog
   - Click **"Install"**

3. **Configure Databases**
   - Complete the configuration wizard that appears
   - Enter your database credentials (details below)

That's it!

### Option 2: Run with uvx (Universal)

Run MedCP directly from the repository using `uvx` without installation:

```bash
# Required: Set your credentials as environment variables
# At least ONE of the following database configurations must be provided:

# Option A: Knowledge Graph only (biomedical knowledge inference)
export KNOWLEDGE_GRAPH_URI="bolt://your-neo4j-server:7687"
export KNOWLEDGE_GRAPH_USERNAME="your_username"
export KNOWLEDGE_GRAPH_PASSWORD="your_password"
export KNOWLEDGE_GRAPH_DATABASE="neo4j"

# Option B: Clinical Records only (EHR queries)
export CLINICAL_RECORDS_SERVER="your-server.hospital.org"
export CLINICAL_RECORDS_DATABASE="your_database"
export CLINICAL_RECORDS_USERNAME="your_username"
export CLINICAL_RECORDS_PASSWORD="your_password"

# Option C: Both (for integrated medical analysis)
# Set all environment variables above

# Run from GitHub (pinned to the v0.9.0 release)
uvx --from git+https://github.com/BaranziniLab/MedCP@v0.9.0 medcp
```

**Important Notes:** tool names are prefixed with the `MEDCP_NAMESPACE` (default `MedCP`).

- If only Knowledge Graph is configured, you'll have access to:
  - `MedCP-get_knowledge_graph_schema` - List all biomedical entities and relationships
  - `MedCP-query_knowledge_graph` - Query drug-disease associations, protein interactions, etc.

- If only Clinical Records is configured, you'll have access to:
  - `MedCP-list_clinical_tables` - List available EHR tables
  - `MedCP-query_clinical_records` - Query patient records with SQL

- If both are configured, you'll have access to all tools for integrated analysis

Or run from a local clone:

```bash
# Clone the repository
git clone https://github.com/BaranziniLab/MedCP.git
cd MedCP

# Set environment variables (see .env.example)
export KNOWLEDGE_GRAPH_URI="bolt://localhost:7687"
# ... set other variables ...

# Run with uvx
uvx --from . medcp
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
| **MedCP Namespace** | Tool prefix for organization | `MedCP` |
| **Log Level** | Logging verbosity | `INFO` |

**Security Note**: All sensitive credentials are automatically encrypted and stored in your operating system's secure keychain.

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

A synthetic OMOP dataset and ready-to-run tests live in
[`benchmarks/sham-dataset`](benchmarks/sham-dataset) — no real patient data.

**SQLite only (no setup):**

```bash
uv run --with fastmcp --with neo4j python benchmarks/sham-dataset/test_backends.py
```

This verifies the SQLite backend (32 tables, 100 patients, writes blocked) and
the default SPOKE knowledge graph.

**Against hosted MySQL / SQL Server:** the dataset is organized into
[`sqlite/`](benchmarks/sham-dataset/sqlite),
[`mysql/`](benchmarks/sham-dataset/mysql), and
[`mssql/`](benchmarks/sham-dataset/mssql). The `mysql/` and `mssql/` folders each
ship a `provision.sh` that stands up an AWS RDS instance, loads the dataset, and
writes a git-ignored `.dbenv` you can `source` before running the tests:

```bash
cd benchmarks/sham-dataset/mysql
export DB_PASSWORD='SomeStrongPassword123'   # RDS master password
./provision.sh                                # create RDS MySQL + load ~468K rows
source ./.dbenv
python ../test_backends.py                     # sqlite + mysql + SPOKE
./teardown.sh                                  # delete the instance when done
```

`test_backends.py` includes MySQL and/or SQL Server automatically once their
connection variables are set. See
[`benchmarks/sham-dataset/README.md`](benchmarks/sham-dataset/README.md) for
details. All three backends have been verified to return identical results.

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
# MedCP: Medical Model Context Protocol <img src="assets/logo.png" align="right" alt="MedCP Logo" width="100"/>

<br>

## Overview

**MedCP** transforms Claude Desktop into a powerful medical AI assistant by providing **secure, local access** to electronic health records and biomedical knowledge graphs. Process sensitive health data entirely on your machine while delivering instant access to clinical insights. If a plain python function-calling version of this software is of interest, please check out [fMedCP](https://github.com/BaranziniLab/fMedCP), which can be run directly from the terminal.

![](assets/schematics.png)

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
separated layers in [`integrations/`](integrations) — all launching the same
core in [`src/medcp/`](src/medcp):

| Agent | Integration | Prebuilt artifact |
|---|---|---|
| **Claude Code** | [`integrations/claude-code`](integrations/claude-code) (plugin) | `medcp-claude-code-plugin.zip` |
| **Codex CLI** | [`integrations/codex`](integrations/codex) (MCP server) | `medcp-codex.zip` |
| **BioRouter** | [`integrations/biorouter`](integrations/biorouter) (`.brxt` extension) | `MedCP.brxt` |
| **Claude Desktop** | root [`manifest.json`](manifest.json) (`.mcpb`) | `MedCP.mcpb` |

Built artifacts and per-OS install steps live in the latest
[`releases/`](releases) folder (see `INSTALL.md` there). Rebuild everything with
`python3 scripts/build_releases.py`.

## Prerequisites

### System Requirements
- **Claude Desktop** 1.0.0+ with MCPB extension support
- **Operating System**: macOS 11+ or Windows 10+
- **Python** Included (standalone runtime bundled with extension)
- **Memory**: 8GB RAM minimum, 16GB recommended

### Install Required Software

**Download Claude Desktop**
Visit [claude.ai/download](https://claude.ai/download) and install the latest version.

That's all! Python and all dependencies are bundled with the extension.

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

# Run from GitHub
uvx --from git+https://github.com/BaranziniLab/MedCP medcp
```

**Important Notes:**
- If only Knowledge Graph is configured, you'll have access to:
  - `get_knowledge_graph_schema` - List all biomedical entities and relationships
  - `query_knowledge_graph` - Query drug-disease associations, protein interactions, etc.

- If only Clinical Records is configured, you'll have access to:
  - `list_clinical_tables` - List available EHR tables
  - `query_clinical_records` - Query patient records with SQL

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

### Biomedical Knowledge Graph

MedCP uses the SPOKE knowledge graph by default ([Morris et al., 2023](https://academic.oup.com/bioinformatics/article/39/2/btad080/7033465)), which contains comprehensive biomedical relationships including drug-disease associations, protein interactions, and biological pathways.

| Parameter | Description | Example |
|-----------|-------------|---------|
| **Knowledge Graph URI** | Neo4j connection URI | `bolt://your-neo4j-server:7687` |
| **Username** | Neo4j database username | `your_username` |
| **Password** | Neo4j database password | `your_secure_password` |
| **Database Name** | Neo4j database name | `spoke` (default) |

### Electronic Health Records

Configure access to your clinical database. MedCP supports three SQL backends,
selected with **`CLINICAL_RECORDS_BACKEND`**. For UCSF users, see the
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
```
"Find all patients diagnosed with diabetes in the last 6 months and summarize their HbA1c trends"
```

### Drug Interaction Analysis
```
"Check for interactions between metformin, lisinopril, and atorvastatin for a 65-year-old patient with CKD stage 3"
```

### Clinical Guidelines
```
"What are the current evidence-based guidelines for treating community-acquired pneumonia in elderly patients?"
```

### Biomedical Research
```
"Find protein targets associated with Alzheimer's disease and identify potential drug compounds that interact with these proteins"
```

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
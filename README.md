# MedCP: Medical Model Context Protocol <img src="assets/logo.png" align="right" alt="MedCP Logo" width="100"/>

<br>

## Overview

**MedCP** transforms Claude Desktop into a powerful medical AI assistant by providing **secure, local access** to electronic health records and biomedical knowledge graphs. Process sensitive health data entirely on your machine while delivering instant access to clinical insights.

![](assets/schematics.png)

### Key Features

- **Local Processing** - All data processing happens on your machine
- **EHR Integration** - Query electronic health records with natural language
- **Biomedical Knowledge** - Access comprehensive drug-disease associations and protein interactions
- **Real-time Analysis** - Instant clinical decision support
- **Secure Storage** - Credentials encrypted in OS keychain

## Prerequisites

### System Requirements
- **Claude Desktop** 1.0.0+ with DXT support
- **Operating System**: macOS 11+ or Windows 10+
- **Python** 3.11+ with [uv package manager](https://docs.astral.sh/uv/)
- **Memory**: 8GB RAM minimum, 16GB recommended

### Install Required Software

**1. Download Claude Desktop**
Visit [claude.ai/download](https://claude.ai/download) and install the latest version.

**2. Install UV Package Manager**

**macOS:**

First install [homebrew](https://brew.sh) if not installed already.
Then install the uv package manager via homebrew:

``` bash
brew install uv
```

**Windows:**

Install uv via powershell:

``` powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Linux:**

Install uv via bash script:

``` bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Installation

### Quick Install

1. **Download the Extension**
   - Go to [Releases](../../releases)
   - Download the latest `MedCP.dxt` file

2. **Install in Claude Desktop**
   - Double-click the `MedCP.dxt` file
   - Claude Desktop will open the installation dialog
   - Click **"Install"**

3. **Configure Databases**
   - Complete the configuration wizard that appears
   - Enter your database credentials (details below)

That's it!


## Configuration

After installation, you'll need to configure your database connections in Claude Desktop:

**Settings → Extensions → MedCP**

### Biomedical Knowledge Graph

MedCP uses the SPOKE knowledge graph by default ([Himmelstein et al., 2023](https://academic.oup.com/bioinformatics/article/39/2/btad080/7033465)), which contains comprehensive biomedical relationships including drug-disease associations, protein interactions, and biological pathways.

| Parameter | Description | Example |
|-----------|-------------|---------|
| **Knowledge Graph URI** | Neo4j connection URI | `bolt://your-neo4j-server:7687` |
| **Username** | Neo4j database username | `your_username` |
| **Password** | Neo4j database password | `your_secure_password` |
| **Database Name** | Neo4j database name | `spoke` (default) |

### Electronic Health Records

Configure access to your clinical database. For UCSF users, see the [UCSF Research Data](https://data.ucsf.edu/research/ucsf-data) portal for access information.

| Parameter | Description | Example |
|-----------|-------------|---------|
| **Clinical Records Server** | SQL Server hostname | `your-ehr-server.hospital.org` |
| **Database Name** | Clinical database name | `OMOP_DEID` |
| **Username** | Database username | `clinical_user` |
| **Password** | Database password | `secure_clinical_password` |

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
1. Verify Claude Desktop supports DXT extensions
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

## License

MedCP is released under the [MIT License](LICENSE).

## Authors and Maintainers

**MedCP** is developed and maintained by the [Baranzini Lab](https://baranzinilab.ucsf.edu/) at UCSF.

- **Wanjun Gu** - [wanjun.gu@ucsf.edu](mailto:wanjun.gu@ucsf.edu)
- **Gianmarco Bellucci** - [gianmarco.bellucci@ucsf.edu](mailto:gianmarco.bellucci@ucsf.edu)

## Acknowledgments

- **SPOKE Knowledge Graph**: [Himmelstein et al., 2023](https://academic.oup.com/bioinformatics/article/39/2/btad080/7033465)
- **UCSF Clinical Data**: [UCSF Research Data Portal](https://data.ucsf.edu/research/ucsf-data)
- **Desktop Extensions**: Built on Anthropic's DXT specification
- **Model Context Protocol**: Enables secure local AI integration

<div align="center">
  <p><a href="../../releases">Download MedCP Extension</a> | <a href="../../issues">Report Issues</a> | <a href="mailto:wanjun.gu@ucsf.edu">Contact</a></p>
</div>
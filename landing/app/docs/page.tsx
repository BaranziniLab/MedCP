import type { Metadata } from "next";
import { IntegrationChooser } from "../components/IntegrationChooser";
import { ProductLink } from "../components/ProductLink";
import { SiteFooter } from "../components/SiteFooter";
import { SiteHeader } from "../components/SiteHeader";
import {
  bioRouterUrl,
  claudeCodeUrl,
  claudeDesktopUrl,
  codexCliUrl,
  repositoryUrl,
  releasesUrl,
  sitePath,
} from "../site-config";

export const metadata: Metadata = {
  title: "Documentation",
  description:
    "Install, configure, test, and use MedCP with BioRouter, Codex CLI, Claude Code, Claude Desktop, or a direct source checkout.",
};

const envRows = [
  ["CLINICAL_RECORDS_BACKEND", "sqlite, mysql, or mssql", "No EHR backend"],
  ["CLINICAL_RECORDS_SQLITE_PATH", "Absolute path to a SQLite file", "Unset"],
  ["CLINICAL_RECORDS_SERVER", "MySQL or SQL Server host", "Unset"],
  ["CLINICAL_RECORDS_DATABASE", "Clinical database name", "Unset"],
  ["CLINICAL_RECORDS_USERNAME", "Dedicated read-only account", "Unset"],
  ["CLINICAL_RECORDS_PASSWORD", "Password for the read-only account", "Unset"],
  ["CLINICAL_RECORDS_PORT", "Optional remote database port", "Driver default"],
  ["MEDCP_DISABLE_KNOWLEDGE_GRAPH", "Set to 1 for EHR-only mode", "0"],
  ["MEDCP_NAMESPACE", "Prefix used for MCP tool names", "MedCP"],
  ["MEDCP_LOG_LEVEL", "DEBUG, INFO, WARNING, or ERROR", "INFO"],
];

export default function DocsPage() {
  return (
    <>
      <SiteHeader current="docs" />
      <main className="docs-main">
        <div className="docs-shell">
          <aside className="docs-sidebar">
            <p className="eyebrow">Documentation</p>
            <nav aria-label="Documentation sections">
              <a href="#start">Start here</a>
              <a href="#compatibility">Compatibility</a>
              <a href="#install">Install</a>
              <a href="#configure">Configure</a>
              <a href="#use">Use</a>
              <a href="#testing">Testing</a>
              <a href="#privacy">Privacy</a>
              <a href="#downloads">Downloads</a>
              <a href="#license">License</a>
            </nav>
          </aside>

          <article className="docs-content">
            <header className="docs-hero">
              <p className="eyebrow">MedCP docs</p>
              <h1>Connect an MCP host to MedCP.</h1>
              <p>
                Start with SPOKE only, add one OMOP backend when you need clinical
                evidence, and validate the path with aggregate queries before using
                institution-approved data.
              </p>
              <div className="hero-actions">
                <a className="button button-primary" href="#install">
                  Choose an integration
                </a>
                <a className="button button-secondary" href={sitePath("/llms.txt")}>
                  Agent setup file
                </a>
              </div>
            </header>

            <section id="start" className="docs-section">
              <p className="eyebrow">01 · Start here</p>
              <h2>Install from source</h2>
              <p>
                The current source tree is version 0.10.0. Its matching Git tag is not
                yet published, so tag-based <code>uvx</code> commands are not presented
                as working installs here. <code>uv sync --locked</code> uses the
                committed dependency lock. SPOKE-only use needs no database credentials.
              </p>
              <div className="code-card">
                <div className="code-label">Terminal</div>
                <pre tabIndex={0}>
                  <code>{`git clone https://github.com/BaranziniLab/MedCP.git
cd MedCP
uv sync --locked
uv run --locked medcp`}</code>
                </pre>
              </div>
              <div className="callout callout-neutral">
                <strong>What starts by default</strong>
                <p>
                  The bundled read-only SPOKE connection. Leave every{" "}
                  <code>CLINICAL_RECORDS_*</code> variable unset for knowledge-graph-only
                  use.
                </p>
              </div>
            </section>

            <section id="compatibility" className="docs-section">
              <p className="eyebrow">02 · Compatibility</p>
              <h2>Supported clients and backends</h2>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Path</th>
                      <th>Requirement</th>
                      <th>Current verification</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td>Direct core</td>
                      <td>Python 3.11+ and uv</td>
                      <td>Python 3.11-3.13 on Linux, macOS, and Windows</td>
                    </tr>
                    <tr>
                      <td>
                        <ProductLink href={bioRouterUrl}>BioRouter</ProductLink>
                      </td>
                      <td>
                        <ProductLink href={bioRouterUrl}>BioRouter</ProductLink> and uv
                      </td>
                      <td>
                        1.88.6 across SQLite, Amazon RDS for MySQL, Amazon RDS for SQL
                        Server, and SPOKE
                      </td>
                    </tr>
                    <tr>
                      <td>
                        <ProductLink href={codexCliUrl}>Codex CLI</ProductLink>
                      </td>
                      <td>
                        <ProductLink href={codexCliUrl}>Codex CLI</ProductLink> with MCP
                        support and uv
                      </td>
                      <td>0.145.0 across the same release matrix</td>
                    </tr>
                    <tr>
                      <td>
                        <ProductLink href={claudeCodeUrl}>Claude Code</ProductLink>
                      </td>
                      <td>
                        <ProductLink href={claudeCodeUrl}>Claude Code</ProductLink> 2.x+
                        and uv
                      </td>
                      <td>Integration provided; not in the v0.10.0 verified host matrix</td>
                    </tr>
                    <tr>
                      <td>
                        <ProductLink href={claudeDesktopUrl}>Claude Desktop</ProductLink>
                      </td>
                      <td>
                        <ProductLink href={claudeDesktopUrl}>Claude Desktop</ProductLink>{" "}
                        with MCPB support
                      </td>
                      <td>Current bundled runtime is macOS Apple silicon only</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <p className="fine-print">
                MedCP targets sessionless MCP 2026-07-28 and retains legacy
                initialization for hosts that have not moved to the modern lifecycle.
                Production transport is stdio only.
              </p>
            </section>

            <section id="install" className="docs-section docs-wide">
              <p className="eyebrow">03 · Install</p>
              <h2>Pick a host</h2>
              <p>
                Select an integration for exact setup steps, package status, and the
                data-handling boundary that applies to that host.
              </p>
              <IntegrationChooser />
            </section>

            <section id="configure" className="docs-section">
              <p className="eyebrow">04 · Configure</p>
              <h2>Add one clinical backend</h2>
              <p>
                SQLite is the simplest test path. For MySQL or SQL Server, use a
                dedicated account with SELECT and no write-capable grants. Never give an
                agent-facing server an administrator credential.
              </p>
              <div className="config-modes">
                <div>
                  <span className="tool-index">Local SQLite</span>
                  <pre tabIndex={0}>
                    <code>{`export CLINICAL_RECORDS_BACKEND=sqlite
export CLINICAL_RECORDS_SQLITE_PATH=/absolute/path/database.sqlite`}</code>
                  </pre>
                </div>
                <div>
                  <span className="tool-index">Remote SQL</span>
                  <pre tabIndex={0}>
                    <code>{`export CLINICAL_RECORDS_BACKEND=mysql  # or mssql
export CLINICAL_RECORDS_SERVER=db.example.org
export CLINICAL_RECORDS_DATABASE=omop
export CLINICAL_RECORDS_USERNAME=reader
export CLINICAL_RECORDS_PASSWORD='use-a-secret-store'`}</code>
                  </pre>
                </div>
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Variable</th>
                      <th>Purpose</th>
                      <th>Default</th>
                    </tr>
                  </thead>
                  <tbody>
                    {envRows.map(([name, purpose, fallback]) => (
                      <tr key={name}>
                        <td><code>{name}</code></td>
                        <td>{purpose}</td>
                        <td>{fallback}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="fine-print">
                Set <code>KNOWLEDGE_GRAPH_URI</code>, username, password, and database
                only when replacing the bundled SPOKE connection with your own Neo4j
                graph.
              </p>
            </section>

            <section id="use" className="docs-section">
              <p className="eyebrow">05 · Use</p>
              <h2>Begin with a small aggregate query</h2>
              <div className="prompt-card">
                <span>Smoke-test prompt</span>
                <blockquote>
                  Use only MedCP. List the clinical tables, count rows in the person
                  table, and report the exact tool names and raw aggregate outputs. Do
                  not return patient-level records.
                </blockquote>
              </div>
              <ol className="numbered-steps">
                <li>
                  <strong>Discover</strong>
                  <span>List tables or inspect the SPOKE schema.</span>
                </li>
                <li>
                  <strong>Query</strong>
                  <span>Use SELECT or read-only Cypher with a narrow result.</span>
                </li>
                <li>
                  <strong>Check</strong>
                  <span>Review the tool call and source result before interpretation.</span>
                </li>
                <li>
                  <strong>Report</strong>
                  <span>Return aggregate evidence, limitations, and follow-up questions.</span>
                </li>
              </ol>
            </section>

            <section id="testing" className="docs-section docs-wide">
              <p className="eyebrow">06 · Testing</p>
              <h2>Four different kinds of evidence</h2>
              <div className="test-grid">
                <div>
                  <span>Core suite</span>
                  <strong>40 cases</strong>
                  <p>
                    Modern and legacy MCP, namespaces, read-only SQL, stdio purity,
                    provisioning logic, and repository hygiene.
                  </p>
                </div>
                <div>
                  <span>Cross-platform CI</span>
                  <strong>9 jobs</strong>
                  <p>
                    Python 3.11, 3.12, and 3.13 on Linux, macOS, and Windows.
                  </p>
                </div>
                <div>
                  <span>Live backend gate</span>
                  <strong>3 SQL backends</strong>
                  <p>
                    One de-identified 100-patient MIMIC-IV OMOP demo in SQLite, Amazon
                    RDS for MySQL, and Amazon RDS for SQL Server.
                  </p>
                </div>
                <div>
                  <span>Clinical evaluation</span>
                  <strong>100 questions</strong>
                  <p>
                    Ten complexity tiers, two current models, and MedCP with SPOKE
                    compared with MedCP EHR-only through{" "}
                    <ProductLink href={bioRouterUrl}>BioRouter</ProductLink>.
                  </p>
                </div>
              </div>

              <h3>What the live backend gate proves</h3>
              <div className="pipeline-list">
                <span>Load the same 32-table fixture</span>
                <span>Create a SELECT-only reader</span>
                <span>Confirm 100 people</span>
                <span>Reject a DELETE statement</span>
                <span>Compare backend results</span>
                <span>Query the live SPOKE graph</span>
              </div>
              <div className="callout callout-warning">
                <strong>AWS test boundary</strong>
                <p>
                  The scripts create disposable Amazon RDS database fixtures. The
                  Amazon EC2 API is used only for VPC and security-group operations; the
                  scripts do not create EC2 instances. These fixtures are
                  compatibility tests, not a HIPAA-compliant deployment reference.
                </p>
              </div>

              <h3>Research evaluations are separate</h3>
              <p>
                The clinical-question benchmark uses UCSF OMOP_DEID through{" "}
                <ProductLink href={bioRouterUrl}>BioRouter</ProductLink>, not the AWS
                demo fixture. The reported benchmark contains 399 completed evaluations
                across GPT-5.5 and Claude Opus 4.8. BiomixQA separately evaluates 617
                gene-disease items. Literature replication turns a published study into
                an auditable cohort, analysis, and comparison report.
              </p>
              <div className="code-card">
                <div className="code-label">Run the network-free suite</div>
                <pre tabIndex={0}>
                  <code>{`uv sync --locked
uv run --locked pytest tests`}</code>
                </pre>
              </div>
            </section>

            <section id="privacy" className="docs-section">
              <p className="eyebrow">07 · Privacy and HIPAA</p>
              <h2>Approve the complete data path</h2>
              <p className="lead">
                MedCP alone does not establish HIPAA compliance. It runs locally over
                stdio, but databases may be remote and query results return to the host.
              </p>
              <p>
                A private deployment can pair MedCP with{" "}
                <ProductLink href={bioRouterUrl}>BioRouter</ProductLink> or another
                approved harness, a local or institution-hosted model, and on-premises
                data systems. Review the complete host, model, network, logging,
                retention, access-control, and contractual path.
              </p>
              <div className="privacy-checklist">
                <div>
                  <strong>Private deployment pattern</strong>
                  <p>
                    Keep the host, model, MedCP process, database endpoint, logs, and
                    exports inside the institutional boundary. Enforce identity, role
                    permissions, small-cell limits, disclosure budgets, and audit
                    review in the surrounding environment.
                  </p>
                </div>
                <div>
                  <strong>
                    <ProductLink href={codexCliUrl}>Codex CLI</ProductLink>,{" "}
                    <ProductLink href={claudeCodeUrl}>Claude Code</ProductLink>,{" "}
                    <ProductLink href={claudeDesktopUrl}>Claude Desktop</ProductLink>
                  </strong>
                  <p>
                    Use non-PHI or appropriately de-identified data unless your
                    institution has approved the host, model provider, network, logging,
                    retention, access controls, and contracts.
                  </p>
                </div>
                <div>
                  <strong>
                    <ProductLink href={bioRouterUrl}>BioRouter</ProductLink>
                  </strong>
                  <p>
                    <ProductLink href={bioRouterUrl}>BioRouter</ProductLink> can store
                    values entered through its secret-setting flow in the configured OS
                    keyring. In the evaluated benchmark harness, limited
                    prompt-injection and PHI patterns were annotated for review, not
                    blocked.
                  </p>
                </div>
                <div>
                  <strong>Every host</strong>
                  <p>
                    Read-only controls prevent mutation. They do not prevent disclosure
                    of returned rows to the agent or model. Core MedCP does not enforce
                    row limits, PHI redaction, or small-cell suppression.
                  </p>
                </div>
              </div>
              <p className="fine-print">
                Keep credentials out of prompts and commits.{" "}
                <ProductLink href={codexCliUrl}>Codex CLI</ProductLink> and{" "}
                <ProductLink href={claudeCodeUrl}>Claude Code</ProductLink> settings can
                be plaintext.{" "}
                <ProductLink href={claudeDesktopUrl}>Claude Desktop</ProductLink>{" "}
                protects sensitive manifest fields.{" "}
                <ProductLink href={bioRouterUrl}>BioRouter</ProductLink> can store
                secrets in its configured OS keyring.
              </p>
            </section>

            <section id="downloads" className="docs-section docs-wide">
              <p className="eyebrow">08 · Downloads</p>
              <h2>Staged source-tree packages</h2>
              <p>
                All four v0.10.0 files pass the checked-in SHA-256 checksums. They are
                staged in the repository, but v0.10.0 is not yet a published Git tag or
                GitHub release. The{" "}
                <ProductLink href={codexCliUrl}>Codex CLI</ProductLink> and{" "}
                <ProductLink href={claudeCodeUrl}>Claude Code</ProductLink> packages
                still default to that missing tag, so use the source setup above for
                those two hosts.
              </p>
              <div className="download-grid">
                <a href="https://raw.githubusercontent.com/BaranziniLab/MedCP/main/releases/MedCP%20v0.10.0/MedCP.brxt">
                  <span>BioRouter</span>
                  <strong>MedCP.brxt</strong>
                  <small>Staged package · checksum verified</small>
                </a>
                <a href="https://raw.githubusercontent.com/BaranziniLab/MedCP/main/releases/MedCP%20v0.10.0/MedCP.mcpb">
                  <span>Claude Desktop</span>
                  <strong>MedCP.mcpb</strong>
                  <small>Staged package · macOS Apple silicon</small>
                </a>
                <a href="https://raw.githubusercontent.com/BaranziniLab/MedCP/main/releases/MedCP%20v0.10.0/medcp-codex.zip">
                  <span>Codex CLI</span>
                  <strong>medcp-codex.zip</strong>
                  <small>Staged package · source setup recommended</small>
                </a>
                <a href="https://raw.githubusercontent.com/BaranziniLab/MedCP/main/releases/MedCP%20v0.10.0/medcp-claude-code-plugin.zip">
                  <span>Claude Code</span>
                  <strong>medcp-claude-code-plugin.zip</strong>
                  <small>Staged package · source plugin recommended</small>
                </a>
              </div>
              <div className="inline-links">
                <ProductLink href={bioRouterUrl}>BioRouter website ↗</ProductLink>
                <ProductLink href={codexCliUrl}>Codex CLI documentation ↗</ProductLink>
                <ProductLink href={claudeCodeUrl}>Claude Code website ↗</ProductLink>
                <ProductLink href={claudeDesktopUrl}>Claude Desktop download ↗</ProductLink>
                <a href={`${repositoryUrl}/tree/main/releases/MedCP%20v0.10.0`}>
                  Checksums and install notes ↗
                </a>
                <a href={releasesUrl}>Published GitHub releases ↗</a>
              </div>
            </section>

            <section id="license" className="docs-section">
              <p className="eyebrow">09 · License and legal</p>
              <h2>Open source research software</h2>
              <p>
                MedCP software is released under the MIT License. It is provided without
                warranty. It is research software only and is not for patient-care
                decisions.
              </p>
              <p>
                The MIMIC-IV OMOP demo has separate provenance and license terms. Review
                the included dataset license and PhysioNet documentation before reuse.
              </p>
              <div className="inline-links">
                <a href={`${repositoryUrl}/blob/main/LICENSE`}>Software license ↗</a>
                <a href={`${repositoryUrl}/tree/main/benchmarks/sham-dataset/sqlite`}>
                  Dataset provenance ↗
                </a>
              </div>
            </section>
          </article>
        </div>
      </main>
      <SiteFooter />
    </>
  );
}

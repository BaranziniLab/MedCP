import type { Metadata } from "next";
import Image from "next/image";
import { SiteFooter } from "./components/SiteFooter";
import { SiteHeader } from "./components/SiteHeader";
import { IntegrationChooser } from "./components/IntegrationChooser";
import {
  ArchitectureDemo,
  BenchmarkDemo,
  NetworkDemo,
  ReplicationDemo,
} from "./components/ResearchDemos";
import { repositoryUrl, sitePath } from "./site-config";

export const metadata: Metadata = {
  title: "The private data port for medical AI",
  description:
    "MedCP gives MCP-compatible hosts read-only tools for OMOP clinical records and biomedical knowledge graphs.",
};

export default function Home() {
  return (
    <>
      <SiteHeader current="about" />
      <main>
        <section className="hero section-shell">
          <Image
            className="hero-mark"
            src={sitePath("/media/medcp-mark.png")}
            alt="MedCP stethoscope and knowledge graph mark"
            width="112"
            height="94"
            unoptimized
          />
          <p className="eyebrow">A standard port for clinical and biological evidence</p>
          <h1>The private data port for medical AI.</h1>
          <p className="hero-copy">
            MedCP gives MCP-compatible hosts up to four read-only tools for OMOP
            clinical records and biomedical knowledge graphs. Databases can be local
            or remote. Pair it with a local or institution-hosted model when the
            workflow must remain inside an approved environment.
          </p>
          <div className="hero-actions">
            <a className="button button-primary" href={sitePath("/docs/#install")}>
              Install MedCP
            </a>
            <a className="button button-secondary" href={repositoryUrl}>
              View on GitHub <span aria-hidden="true">↗</span>
            </a>
          </div>
          <div className="hero-facts" aria-label="MedCP highlights">
            <div>
              <span>01</span>
              <strong>Read-only by design</strong>
              <p>SQL and Cypher mutations are rejected before execution.</p>
            </div>
            <div>
              <span>02</span>
              <strong>Local stdio server</strong>
              <p>Choose the host, model, database endpoint, and network path.</p>
            </div>
            <div>
              <span>03</span>
              <strong>Clinical + biological</strong>
              <p>Connect OMOP evidence with genes, pathways, drugs, and disease biology.</p>
            </div>
          </div>
          <div className="port-analogy">
            <span aria-hidden="true">USB-C</span>
            <p>
              MCP standardizes how clients connect, negotiate features, and discover
              tools. MedCP applies it to clinical and biological data.
            </p>
          </div>
        </section>

        <section id="overview" className="section section-tinted">
          <div className="content-shell overview-grid">
            <div className="section-heading">
              <p className="eyebrow">Overview</p>
              <h2>One interface for two evidence systems.</h2>
            </div>
            <div className="prose">
              <p className="lead">
                MedCP runs on your machine and exposes up to four tools. The databases
                can be local or remote. Results return to the host agent that you choose.
              </p>
              <div className="tool-grid">
                <div>
                  <span className="tool-index">EHR 01</span>
                  <code>MedCP-list_clinical_tables</code>
                  <p>Inspect the available OMOP tables before writing a query.</p>
                </div>
                <div>
                  <span className="tool-index">EHR 02</span>
                  <code>MedCP-query_clinical_records</code>
                  <p>Run validated read-only SQL against SQLite, MySQL, or SQL Server.</p>
                </div>
                <div>
                  <span className="tool-index">KG 01</span>
                  <code>MedCP-get_knowledge_graph_schema</code>
                  <p>Discover the node labels, properties, and relationships.</p>
                </div>
                <div>
                  <span className="tool-index">KG 02</span>
                  <code>MedCP-query_knowledge_graph</code>
                  <p>Run read-only Cypher against SPOKE or another Neo4j graph.</p>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section id="architecture" className="section">
          <div className="content-shell">
            <div className="section-heading split-heading">
              <div>
                <p className="eyebrow">System architecture</p>
                <h2>A local bridge, with explicit data boundaries.</h2>
              </div>
              <p>
                Follow one research question from the person, through the agent host and
                MedCP, to the configured databases and back.
              </p>
            </div>
            <ArchitectureDemo />
            <details className="architecture-figure">
              <summary>View the complete clinical and biological workflow</summary>
              <a
                href={sitePath("/media/figure-1.webp")}
                aria-label="Open the full MedCP infrastructure figure"
              >
                <Image
                  src={sitePath("/media/figure-1.webp")}
                  alt="MedCP infrastructure diagram connecting an agent host, local stdio server, clinical records, and a biomedical knowledge graph"
                  width="1100"
                  height="1271"
                  loading="lazy"
                  unoptimized
                />
              </a>
              <p>
                The architecture separates the researcher, host agent, local MedCP
                process, and the clinical and biological databases that may be local or
                remote.
              </p>
            </details>
          </div>
        </section>

        <section id="privacy-design" className="section private-section">
          <div className="content-shell">
            <div className="section-heading split-heading">
              <div>
                <p className="eyebrow">Privacy-focused design</p>
                <h2>Control the full data path.</h2>
              </div>
              <p>
                Pair MedCP with a local or institution-hosted model and an approved
                harness to build a private research environment.
              </p>
            </div>
            <div className="privacy-stack">
              <article>
                <span>01</span>
                <h3>MedCP adapter</h3>
                <p>
                  A local stdio process exposes only the configured tools and rejects
                  write-capable SQL and Cypher.
                </p>
              </article>
              <article>
                <span>02</span>
                <h3>Approved host and model</h3>
                <p>
                  BioRouter can orchestrate local or institution-approved models.
                  Codex and Claude integrations are suitable only when their complete
                  data paths are approved for the dataset.
                </p>
              </article>
              <article>
                <span>03</span>
                <h3>Institutional controls</h3>
                <p>
                  Your institution must still manage identity, database permissions,
                  small-cell rules, logging, retention, and exports.
                </p>
              </article>
            </div>
            <div className="boundary-note">
              <strong>Compliance boundary</strong>
              <p>
                MedCP supplies the read-only adapter. HIPAA compliance depends on the
                approved end-to-end environment and is not certified by MedCP alone.
              </p>
            </div>
          </div>
        </section>

        <section id="evidence" className="section section-tinted">
          <div className="content-shell">
            <div className="section-heading split-heading">
              <div>
                <p className="eyebrow">Measured evidence</p>
                <h2>Benchmark and replication results.</h2>
              </div>
              <p>
                Compare cohort-grounded answers, explore clinical and biological
                associations, and review local estimates beside published results.
              </p>
            </div>
            <BenchmarkDemo />
            <NetworkDemo />
            <ReplicationDemo />
          </div>
        </section>

        <section id="integrations" className="section">
          <div className="content-shell">
            <div className="section-heading split-heading">
              <div>
                <p className="eyebrow">Integrations</p>
                <h2>Choose the host you already use.</h2>
              </div>
              <p>
                Every integration launches the same MedCP core. BioRouter is the
                canonical benchmark harness.
              </p>
            </div>
            <IntegrationChooser compact />
            <div className="section-cta">
              <a className="text-link" href={sitePath("/docs/#install")}>
                Open the complete installation guide <span aria-hidden="true">→</span>
              </a>
            </div>
          </div>
        </section>

        <section className="privacy-band">
          <div className="content-shell privacy-grid">
            <div>
              <p className="eyebrow">Data boundary</p>
              <h2>Read-only is not the same as HIPAA compliant.</h2>
            </div>
            <div>
              <p>
                MedCP does not make an AI host or model provider HIPAA compliant. Do not
                use PHI with Codex CLI, Claude Code, Claude Desktop, BioRouter, or another
                host unless your institution has approved the full database, host, model,
                network, logging, credential, and governance path.
              </p>
              <p>
                A local or on-premises deployment can keep the research loop inside an
                institutional boundary when the complete environment is approved and
                governed.
              </p>
              <a className="text-link on-dark" href={sitePath("/docs/#privacy")}>
                Read the privacy guidance <span aria-hidden="true">→</span>
              </a>
            </div>
          </div>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}

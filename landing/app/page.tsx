import type { Metadata } from "next";
import Image from "next/image";
import { SiteFooter } from "./components/SiteFooter";
import { SiteHeader } from "./components/SiteHeader";
import { IntegrationChooser } from "./components/IntegrationChooser";
import { ProductLink } from "./components/ProductLink";
import {
  ArchitectureDemo,
  BenchmarkDemo,
  NetworkDemo,
  ReplicationDemo,
} from "./components/ResearchDemos";
import {
  bioRouterUrl,
  claudeCodeUrl,
  claudeDesktopUrl,
  codexCliUrl,
  repositoryUrl,
  sitePath,
} from "./site-config";

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
              <h2>One interface. Two key components.</h2>
            </div>
            <div className="prose">
              <p className="lead">
                MedCP brings two key components into one local interface: an OMOP EHR
                queried with SQL and a biomedical knowledge graph queried with Cypher.
                Results return to the host agent that you choose.
              </p>
              <div className="evidence-grid">
                <article className="evidence-card evidence-card-ehr">
                  <span className="component-index">Key component 01</span>
                  <div className="evidence-title">
                    <strong>EHR</strong>
                    <span>SQL</span>
                  </div>
                  <h3>Clinical records</h3>
                  <p>
                    Query OMOP-format health records with validated, read-only SQL.
                  </p>
                  <small>Preconfigured for OMOP EHRs on SQLite, MySQL, and SQL Server</small>
                </article>
                <article className="evidence-card evidence-card-kg">
                  <span className="component-index">Key component 02</span>
                  <div className="evidence-title">
                    <strong>Knowledge graph</strong>
                    <span>Cypher</span>
                  </div>
                  <h3>Biomedical context</h3>
                  <p>
                    Connect diseases with genes, pathways, drugs, and other biological
                    relationships through read-only graph queries.
                  </p>
                  <small>Preconfigured for the SPOKE knowledge graph</small>
                </article>
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
                  <ProductLink href={bioRouterUrl}>BioRouter</ProductLink> can
                  orchestrate local or institution-approved models.{" "}
                  <ProductLink href={codexCliUrl}>Codex CLI</ProductLink> and{" "}
                  <ProductLink href={claudeCodeUrl}>Claude Code</ProductLink>{" "}
                  integrations are suitable only when their complete data paths are
                  approved for the dataset.
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

        <section id="integrations" className="section">
          <div className="content-shell">
            <div className="section-heading split-heading">
              <div>
                <p className="eyebrow">Integrations</p>
                <h2>Choose the host you already use.</h2>
              </div>
              <p>
                Every integration launches the same MedCP core.{" "}
                <ProductLink href={bioRouterUrl}>BioRouter</ProductLink> is the
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

        <section className="privacy-band">
          <div className="content-shell privacy-grid">
            <div>
              <p className="eyebrow">Data boundary</p>
              <h2>Read-only is not the same as HIPAA compliant.</h2>
            </div>
            <div>
              <p>
                MedCP does not make an AI host or model provider HIPAA compliant. Do not
                use PHI with <ProductLink href={codexCliUrl}>Codex CLI</ProductLink>,{" "}
                <ProductLink href={claudeCodeUrl}>Claude Code</ProductLink>,{" "}
                <ProductLink href={claudeDesktopUrl}>Claude Desktop</ProductLink>,{" "}
                <ProductLink href={bioRouterUrl}>BioRouter</ProductLink>, or another host
                unless your institution has approved the full database, host, model,
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

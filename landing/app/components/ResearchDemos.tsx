"use client";

import { useState } from "react";

type ArchitectureStep = "question" | "host" | "medcp" | "ehr" | "kg";

const architectureCopy: Record<ArchitectureStep, { title: string; body: string }> = {
  question: {
    title: "1. A researcher asks",
    body:
      "The host receives a research question, such as an aggregate medication trend or a disease-mechanism lookup.",
  },
  host: {
    title: "2. The approved host plans",
    body:
      "BioRouter, Codex CLI, Claude Code, Claude Desktop, or another MCP client decides which advertised tool to call.",
  },
  medcp: {
    title: "3. MedCP validates",
    body:
      "The local stdio server advertises the configured tools and rejects write-capable SQL and Cypher before execution.",
  },
  ehr: {
    title: "4a. OMOP returns clinical evidence",
    body:
      "MedCP opens SQLite read-only or connects to MySQL or SQL Server with a dedicated read-only account. Results return to the host.",
  },
  kg: {
    title: "4b. SPOKE returns biological context",
    body:
      "Read-only Cypher connects diseases with genes, pathways, drugs, phenotypes, and other biomedical entities.",
  },
};

export function ArchitectureDemo() {
  const [active, setActive] = useState<ArchitectureStep>("medcp");
  const detail = architectureCopy[active];

  return (
    <figure className="architecture-demo">
      <div className="architecture-canvas" aria-label="Interactive MedCP data flow">
        <div className="boundary-label">Approved research environment</div>
        <div className="architecture-flow">
          <FlowNode
            id="question"
            label="Researcher"
            detail="Research question"
            active={active === "question"}
            setActive={setActive}
          />
          <FlowArrow />
          <FlowNode
            id="host"
            label="Agent host"
            detail="Plans tool calls"
            active={active === "host"}
            setActive={setActive}
          />
          <FlowArrow />
          <FlowNode
            id="medcp"
            label="MedCP"
            detail="Local stdio + read-only gate"
            active={active === "medcp"}
            setActive={setActive}
            accent
          />
          <FlowArrow />
          <div className="data-nodes">
            <FlowNode
              id="ehr"
              label="OMOP EHR"
              detail="SQLite · MySQL · SQL Server"
              active={active === "ehr"}
              setActive={setActive}
            />
            <FlowNode
              id="kg"
              label="SPOKE"
              detail="Biomedical knowledge graph"
              active={active === "kg"}
              setActive={setActive}
            />
          </div>
        </div>
      </div>
      <figcaption className="figure-caption">
        <span>Selected path</span>
        <strong>{detail.title}</strong>
        <p>{detail.body}</p>
      </figcaption>
    </figure>
  );
}

function FlowNode({
  id,
  label,
  detail,
  active,
  accent = false,
  setActive,
}: {
  id: ArchitectureStep;
  label: string;
  detail: string;
  active: boolean;
  accent?: boolean;
  setActive: (value: ArchitectureStep) => void;
}) {
  return (
    <button
      className={`flow-node${active ? " is-active" : ""}${accent ? " is-accent" : ""}`}
      type="button"
      aria-pressed={active}
      onClick={() => setActive(id)}
      onPointerEnter={() => setActive(id)}
      onFocus={() => setActive(id)}
    >
      <strong>{label}</strong>
      <span>{detail}</span>
    </button>
  );
}

function FlowArrow() {
  return (
    <span className="flow-arrow" aria-hidden="true">
      <i />
      <b>›</b>
    </span>
  );
}

type BenchmarkModel = "gpt" | "opus";

const benchmarkModels = {
  gpt: {
    name: "GPT-5.5",
    withKg: 1.19,
    ehrOnly: 1.045,
    difference: "+0.145",
    runtime: "30.1% lower runtime",
    calls: "SPOKE used in 37 of 100 questions",
    note: "Raw paired p=.030; BH-adjusted p=.091",
  },
  opus: {
    name: "Claude Opus 4.8",
    withKg: 0.925,
    ehrOnly: 0.835,
    difference: "+0.090",
    runtime: "41.0% lower runtime",
    calls: "SPOKE used in 32 of 100 questions",
    note: "Raw paired p=.118",
  },
};

export function BenchmarkDemo() {
  const [model, setModel] = useState<BenchmarkModel>("gpt");
  const selected = benchmarkModels[model];
  const scale = 1.3;

  return (
    <article className="research-demo benchmark-demo">
      <div className="demo-kicker">
        <span>Figure 2 adaptation</span>
        <strong>Illustrative answer comparison</strong>
      </div>
      <div className="answer-comparison">
        <div className="answer-panel">
          <span className="comparison-label">Without database access, illustrative</span>
          <h3>A general explanation</h3>
          <p>
            Immunosuppressant use may have changed in 2020. Several therapies could
            contribute, but the answer has no direct cohort counts or database trace.
          </p>
          <ul>
            <li>Broad medical context</li>
            <li>No queried cohort</li>
            <li>No source-linked trend</li>
          </ul>
        </div>
        <div className="answer-panel answer-panel-accent">
          <span className="comparison-label">MedCP manuscript example</span>
          <h3>A measured cohort answer</h3>
          <p>
            The manuscript example found 184,356 prescriptions in 2019 and 199,432 in
            2020, an 8.2% increase across the queried OMOP cohort.
          </p>
          <ul>
            <li>9,522 to 10,399 unique patients</li>
            <li>Methotrexate: +21.3%</li>
            <li>Quarterly change exposed for review</li>
          </ul>
        </div>
      </div>
      <p className="comparison-note">
        The left panel illustrates an answer without database access. It is not a
        benchmark result.
      </p>

      <div className="performance-panel">
        <div className="performance-head">
          <div>
            <span className="comparison-label">Current clinical benchmark</span>
            <h3>MedCP + SPOKE compared with MedCP EHR-only</h3>
          </div>
          <div className="segmented-control" role="group" aria-label="Benchmark model">
            {(
              [
                ["gpt", "GPT-5.5"],
                ["opus", "Claude Opus 4.8"],
              ] as const
            ).map(([key, label]) => (
              <button
                key={key}
                type="button"
                aria-pressed={model === key}
                onClick={() => setModel(key)}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        <div className="score-chart" aria-label={`${selected.name} mean answer score`}>
          <ScoreBar
            label="MedCP + SPOKE"
            value={selected.withKg}
            width={(selected.withKg / scale) * 100}
            accent
          />
          <ScoreBar
            label="MedCP EHR-only"
            value={selected.ehrOnly}
            width={(selected.ehrOnly / scale) * 100}
          />
        </div>
        <div className="performance-facts">
          <div>
            <span>Mean expert score difference, 0-2</span>
            <strong>{selected.difference}</strong>
          </div>
          <div>
            <span>Runtime versus EHR-only</span>
            <strong>{selected.runtime}</strong>
          </div>
          <div>
            <span>Graph retrieval</span>
            <strong>{selected.calls}</strong>
          </div>
        </div>
        <p className="figure-note">
          {selected.note}. Results are model and deployment specific. Score bars use a
          common 0 to 1.3 scale and do not compare against an unaided model.
        </p>
      </div>
    </article>
  );
}

function ScoreBar({
  label,
  value,
  width,
  accent = false,
}: {
  label: string;
  value: number;
  width: number;
  accent?: boolean;
}) {
  return (
    <div className="score-row">
      <span>{label}</span>
      <div className="bar-track" aria-hidden="true">
        <i className={accent ? "bar-accent" : ""} style={{ width: `${width}%` }} />
      </div>
      <strong>{value.toFixed(3)}</strong>
    </div>
  );
}

type NetworkNode = "disease" | "gene" | "drug" | "pathway" | "ehr";

const networkDetails: Record<NetworkNode, { label: string; body: string }> = {
  disease: {
    label: "Disease",
    body: "The common anchor used to compare clinical co-occurrence with graph connectivity.",
  },
  gene: {
    label: "Genes",
    body: "Known disease-gene relationships help organize mechanistic hypotheses.",
  },
  drug: {
    label: "Drugs",
    body: "Drug and target relationships add pharmacologic context to cohort patterns.",
  },
  pathway: {
    label: "Pathways",
    body: "Pathway links place individual genes into broader biological processes.",
  },
  ehr: {
    label: "EHR co-occurrence",
    body: "Adjusted clinical co-occurrence is compared with graph structure, not treated as causation.",
  },
};

export function NetworkDemo() {
  const [active, setActive] = useState<NetworkNode>("disease");
  const detail = networkDetails[active];

  return (
    <article className="research-demo network-demo">
      <div className="demo-kicker">
        <span>Figure 3 adaptation</span>
        <strong>Combine cohort patterns with biological structure</strong>
      </div>
      <div className="network-layout">
        <div className="network-canvas">
          <svg viewBox="0 0 680 360" role="img" aria-labelledby="network-title network-desc">
            <title id="network-title">Clinical and biological evidence network</title>
            <desc id="network-desc">
              A disease node connects to genes, drugs, pathways, and adjusted EHR
              co-occurrence. Select a node to read its role.
            </desc>
            <g className={`network-edges active-${active}`} aria-hidden="true">
              <line x1="340" y1="180" x2="116" y2="86" />
              <line x1="340" y1="180" x2="555" y2="72" />
              <line x1="340" y1="180" x2="566" y2="278" />
              <line x1="340" y1="180" x2="116" y2="276" />
              <line x1="116" y1="86" x2="116" y2="276" />
              <line x1="555" y1="72" x2="566" y2="278" />
            </g>
          </svg>
          <NetworkButton id="disease" label="Disease" x="50%" y="50%" active={active} setActive={setActive} />
          <NetworkButton id="gene" label="Genes" x="17%" y="24%" active={active} setActive={setActive} />
          <NetworkButton id="drug" label="Drugs" x="82%" y="20%" active={active} setActive={setActive} />
          <NetworkButton id="pathway" label="Pathways" x="83%" y="77%" active={active} setActive={setActive} />
          <NetworkButton id="ehr" label="EHR" x="17%" y="77%" active={active} setActive={setActive} />
        </div>
        <div className="network-detail" aria-live="polite">
          <span>Selected evidence layer</span>
          <strong>{detail.label}</strong>
          <p>{detail.body}</p>
          <div className="stat-lockup">
            <strong>ρ 0.580</strong>
            <span>
              Adjusted association across 208 co-occurrence patterns and seven
              biological dimensions
            </span>
          </div>
          <p className="figure-note">
            Hypothesis-generating association after adjustment for age, sex, follow-up,
            and visit days. It is not a causal estimate.
          </p>
        </div>
      </div>
    </article>
  );
}

function NetworkButton({
  id,
  label,
  x,
  y,
  active,
  setActive,
}: {
  id: NetworkNode;
  label: string;
  x: string;
  y: string;
  active: NetworkNode;
  setActive: (value: NetworkNode) => void;
}) {
  return (
    <button
      type="button"
      className={`network-node network-node-${id}${active === id ? " is-active" : ""}`}
      style={{ left: x, top: y }}
      aria-pressed={active === id}
      onClick={() => setActive(id)}
      onPointerEnter={() => setActive(id)}
      onFocus={() => setActive(id)}
    >
      {label}
    </button>
  );
}

type ReplicationStudy = "cerono" | "anagnostakis";

const replications = {
  cerono: {
    label: "Cerono et al.",
    endpoint: "Literature replication",
    originalN: "813",
    medcpN: "714",
    original: { hr: 2.27, low: 1.37, high: 3.75 },
    medcp: { hr: 1.94, low: 1.24, high: 3.05 },
    summary:
      "The MedCP estimate points in the same direction and its interval remains above the null.",
  },
  anagnostakis: {
    label: "Anagnostakis et al.",
    endpoint: "Matched comparison",
    originalN: "32,542",
    medcpN: "1,046",
    original: { hr: 1.01, low: 0.9, high: 1.13 },
    medcp: { hr: 0.71, low: 0.32, high: 1.56 },
    summary:
      "The smaller MedCP cohort is compatible with the reported null, but its wide interval makes this a feasibility result.",
  },
};

export function ReplicationDemo() {
  const [study, setStudy] = useState<ReplicationStudy>("cerono");
  const selected = replications[study];

  return (
    <article className="research-demo replication-demo">
      <div className="demo-kicker">
        <span>Figure 4 adaptation</span>
        <strong>Compare published and local estimates</strong>
      </div>
      <ol className="replication-pipeline" aria-label="Literature replication workflow">
        <li>
          <span>01</span>
          <strong>Specify</strong>
          <small>Population, exposure, outcome</small>
        </li>
        <li>
          <span>02</span>
          <strong>Map</strong>
          <small>OMOP concepts + SPOKE context</small>
        </li>
        <li>
          <span>03</span>
          <strong>Execute</strong>
          <small>Cohort and statistical model</small>
        </li>
        <li>
          <span>04</span>
          <strong>Compare</strong>
          <small>Published and local estimates</small>
        </li>
      </ol>

      <div className="forest-card">
        <div className="performance-head">
          <div>
            <span className="comparison-label">{selected.endpoint}</span>
            <h3>{selected.label}</h3>
          </div>
          <div className="segmented-control" role="group" aria-label="Replication study">
            <button
              type="button"
              aria-pressed={study === "cerono"}
              onClick={() => setStudy("cerono")}
            >
              Cerono
            </button>
            <button
              type="button"
              aria-pressed={study === "anagnostakis"}
              onClick={() => setStudy("anagnostakis")}
            >
              Anagnostakis
            </button>
          </div>
        </div>
        <div className="forest-plot" aria-label={`${selected.label} hazard ratio comparison`}>
          <ForestRow label="Published" n={selected.originalN} value={selected.original} />
          <ForestRow label="MedCP" n={selected.medcpN} value={selected.medcp} accent />
          <div className="forest-axis" aria-hidden="true">
            <span>0.25</span>
            <span>0.5</span>
            <span>1</span>
            <span>2</span>
            <span>4</span>
          </div>
        </div>
        <p className="replication-summary">{selected.summary}</p>
        <p className="figure-note">
          Adapted from the MedCP manuscript. Patient-level replication data are not
          included in the public repository.
        </p>
      </div>
    </article>
  );
}

function ForestRow({
  label,
  n,
  value,
  accent = false,
}: {
  label: string;
  n: string;
  value: { hr: number; low: number; high: number };
  accent?: boolean;
}) {
  const min = 0.25;
  const max = 4;
  const position = (value: number) =>
    ((Math.log(value) - Math.log(min)) / (Math.log(max) - Math.log(min))) * 100;
  const left = position(value.low);
  const right = position(value.high);
  const point = position(value.hr);

  return (
    <div className="forest-row">
      <div className="forest-label">
        <strong>{label}</strong>
        <span>n={n}</span>
      </div>
      <div className="forest-range">
        <span className="null-line" aria-hidden="true" />
        <span
          className={`confidence-line${accent ? " is-accent" : ""}`}
          style={{ left: `${left}%`, width: `${right - left}%` }}
          aria-hidden="true"
        />
        <span
          className={`estimate-point${accent ? " is-accent" : ""}`}
          style={{ left: `${point}%` }}
          aria-hidden="true"
        />
      </div>
      <span className="forest-value">
        {value.hr.toFixed(2)} ({value.low.toFixed(2)}-{value.high.toFixed(2)})
      </span>
    </div>
  );
}

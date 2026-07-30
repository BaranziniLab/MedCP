"use client";

import { useEffect, useState } from "react";
import { ProductLink } from "./ProductLink";

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
      "The selected MCP client decides which advertised tool to call for the research question.",
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
      <svg viewBox="0 0 48 16" focusable="false">
        <path d="M2 8H44M38 2L44 8L38 14" />
      </svg>
    </span>
  );
}

type BenchmarkModel = "gpt" | "opus";

const benchmarkModels = {
  gpt: {
    name: "GPT-5.5",
    withKg: 1.265,
    ehrOnly: 1.045,
    difference: "+0.220",
    runtime: "30.1% lower than EHR-only",
    calls: "SPOKE used in 37 of 100 questions",
    note: "Score comparison: paired t-test p=0.0026; signed-rank p=0.0040",
  },
  opus: {
    name: "Claude Opus 4.8",
    withKg: 1.015,
    ehrOnly: 0.835,
    difference: "+0.180",
    runtime: "41.0% lower than EHR-only",
    calls: "SPOKE used in 32 of 100 questions",
    note: "Score comparison: paired t-test p=0.0049; signed-rank p=0.0086",
  },
};

export function BenchmarkDemo() {
  const [model, setModel] = useState<BenchmarkModel>("gpt");
  const selected = benchmarkModels[model];
  const scale = 2;

  return (
    <article className="research-demo benchmark-demo">
      <div className="demo-kicker">
        <span>Paired benchmark example</span>
        <strong>One real question, with and without SPOKE</strong>
      </div>
      <div className="benchmark-question">
        <span>GPT-5.5 · Q6.10</span>
        <p>
          In sickle cell disease, which infection diagnoses occur most frequently,
          and what immune or hemolysis processes might explain susceptibility?
        </p>
      </div>
      <div className="answer-comparison">
        <div className="answer-panel">
          <span className="comparison-label">MedCP EHR-only</span>
          <h3>Ad hoc filters missed the target</h3>
          <p>
            The EHR-only run used diagnosis-name filters on 1,226 patients. It ranked
            acute chest syndrome (386) and fever (367) first, although neither is an
            infection diagnosis.
          </p>
          <ul>
            <li>Name-filtered cohort and phenotypes</li>
            <li>10 EHR calls in 766 seconds</li>
            <li>Mean expert score: 0 of 2</li>
          </ul>
        </div>
        <div className="answer-panel answer-panel-accent">
          <span className="comparison-label">MedCP EHR + SPOKE</span>
          <h3>A hierarchy-grounded answer</h3>
          <p>
            The fully enabled run defined 1,783 patients using standard descendants and
            excluded sickle cell trait. The leading infections were acute upper
            respiratory infection (327), pneumonia (322), viral disease (255), and
            urinary tract infection (239).
          </p>
          <ul>
            <li>8 SPOKE calls and 10 EHR calls</li>
            <li>Linked HBB, splenic dysfunction, hemolysis, and oxidative stress</li>
            <li>Mean expert score: 2 of 2</li>
          </ul>
        </div>
      </div>
      <p className="comparison-note">
        Observed paired GPT-5.5 benchmark example. Both panels used MedCP. This compares
        EHR-only with EHR + SPOKE, not an unaided model with MedCP.
      </p>

      <div className="performance-panel">
        <div className="performance-head">
          <div>
            <span className="comparison-label">Clinical question benchmark</span>
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
            <span>Mean elapsed time, descriptive</span>
            <strong>{selected.runtime}</strong>
          </div>
          <div>
            <span>Graph retrieval</span>
            <strong>{selected.calls}</strong>
          </div>
        </div>
        <p className="figure-note">
          {selected.note}. Each condition contains the same 100 questions. Scores are
          the mean of physician and bioinformatician ratings on the 0 to 2 scale.
          Results are model and deployment specific.
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

const studySteps = [
  {
    label: "Ask",
    title: "Define the clinical question",
    short: "Comorbidity question",
    body:
      "A researcher asks MedCP to map comorbidity among common autoimmune and neurodegenerative diseases.",
    tags: ["Research protocol", "Disease set"],
  },
  {
    label: "EHR",
    title: "Measure disease pairs in the EHR",
    short: "Read-only SQL",
    body:
      "MedCP uses validated SQL to identify aggregate disease co-occurrence patterns in the OMOP clinical database.",
    tags: ["OMOP EHR", "SQL", "Aggregate results"],
  },
  {
    label: "SPOKE",
    title: "Map biological relationships",
    short: "Read-only Cypher",
    body:
      "MedCP uses Cypher to measure how the same diseases connect through genes, variants, symptoms, anatomy, compounds, pathways, and curated disease-disease relationships in SPOKE.",
    tags: ["SPOKE", "Cypher", "Seven dimensions"],
  },
  {
    label: "Align",
    title: "Join the two evidence systems",
    short: "Matched disease pairs",
    body:
      "Disease pairs from the EHR are matched to their biological similarity in the knowledge graph, creating one comparison table.",
    tags: ["Clinical patterns", "Biological similarity"],
  },
  {
    label: "Test",
    title: "Test the association",
    short: "Spearman rank correlation",
    body:
      "EHR co-occurrence was adjusted for age, sex, follow-up duration, and visit-days, then compared with SPOKE similarity using Spearman rank correlation.",
    tags: ["Adjusted model", "Auditable result"],
  },
] as const;

const biologicalDimensions = [
  "Genes",
  "Variants",
  "Symptoms",
  "Anatomy",
  "Compounds",
  "Pathways",
  "Curated disease relationships",
] as const;

export function NetworkDemo() {
  const [activeStep, setActiveStep] = useState(0);
  const [isPlaying, setIsPlaying] = useState(true);
  const [reducedMotion, setReducedMotion] = useState(false);
  const active = studySteps[activeStep];
  const progress = (activeStep / (studySteps.length - 1)) * 100;

  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const syncMotionPreference = () => {
      setReducedMotion(media.matches);
      if (media.matches) {
        setIsPlaying(false);
      }
    };

    syncMotionPreference();
    media.addEventListener("change", syncMotionPreference);
    return () => media.removeEventListener("change", syncMotionPreference);
  }, []);

  useEffect(() => {
    if (!isPlaying || reducedMotion) {
      return;
    }

    const timer = window.setInterval(() => {
      setActiveStep((current) => (current + 1) % studySteps.length);
    }, 2400);

    return () => window.clearInterval(timer);
  }, [isPlaying, reducedMotion]);

  return (
    <article id="study-walkthrough" className="research-demo study-demo">
      <div className="demo-kicker">
        <span>Study walkthrough</span>
        <strong>How MedCP links EHR comorbidity to SPOKE biology</strong>
      </div>
      <div className="study-walkthrough">
        <div className="study-intro">
          <p>
            The same disease pairs are measured in the EHR and SPOKE, then compared in
            an adjusted analysis.
          </p>
          <button
            type="button"
            className="study-playback"
            aria-label={
              reducedMotion
                ? "Motion disabled by system preference"
                : isPlaying
                  ? "Pause animation"
                  : "Play animation"
            }
            disabled={reducedMotion}
            onClick={() => setIsPlaying((current) => !current)}
          >
            <span aria-hidden="true">{reducedMotion ? "•" : isPlaying ? "Ⅱ" : "▶"}</span>
            {reducedMotion ? "Motion off" : isPlaying ? "Pause" : "Play"}
          </button>
        </div>

        <div className="study-flow">
          <svg
            className="study-flow-svg"
            viewBox="0 0 1000 72"
            preserveAspectRatio="xMidYMid meet"
            aria-hidden="true"
          >
            <path className="study-track" pathLength="100" d="M 100 36 H 900" />
            <path
              className="study-progress"
              pathLength="100"
              d="M 100 36 H 900"
              style={{ strokeDashoffset: 100 - progress }}
            />
            {[100, 300, 500, 700, 900].map((x, index) => (
              <circle
                key={x}
                className={index <= activeStep ? "is-reached" : ""}
                cx={x}
                cy="36"
                r={index === activeStep ? "9" : "6"}
              />
            ))}
            <circle
              className="study-pulse"
              cx={[100, 300, 500, 700, 900][activeStep]}
              cy="36"
              r="15"
            />
          </svg>
          <ol className="study-steps" aria-label="MedCP study workflow">
            {studySteps.map((step, index) => (
              <li key={step.label}>
                <button
                  type="button"
                  className={index === activeStep ? "is-active" : ""}
                  aria-current={index === activeStep ? "step" : undefined}
                  onClick={() => {
                    setActiveStep(index);
                    setIsPlaying(false);
                  }}
                  onFocus={() => {
                    setActiveStep(index);
                    setIsPlaying(false);
                  }}
                >
                  <span>{String(index + 1).padStart(2, "0")}</span>
                  <strong>{step.label}</strong>
                  <small>{step.short}</small>
                </button>
              </li>
            ))}
          </ol>
        </div>

        <div className="study-detail-grid">
          <div className="study-detail" aria-live={isPlaying ? "off" : "polite"}>
            <span>
              Step {String(activeStep + 1).padStart(2, "0")} of{" "}
              {String(studySteps.length).padStart(2, "0")}
            </span>
            <h3>{active.title}</h3>
            <p>{active.body}</p>
            <div className="study-tags" aria-label="Data and method">
              {active.tags.map((tag) => (
                <span key={tag}>{tag}</span>
              ))}
            </div>
          </div>
          <aside className="study-result">
            <span>What the study found</span>
            <h3>
              Disease pairs that were more biologically connected in SPOKE also tended
              to co-occur more often in the EHR.
            </h3>
            <dl className="study-result-stats" aria-label="Statistical summary">
              <div>
                <dt>Spearman correlation</dt>
                <dd>0.58</dd>
              </div>
              <div>
                <dt>p-value</dt>
                <dd>&lt; 0.0001</dd>
              </div>
            </dl>
            <small>
              This describes an association. It does not show cause and effect.
            </small>
          </aside>
        </div>

        <div className="study-dimensions">
          <span>Biological dimensions measured in SPOKE</span>
          <ul>
            {biologicalDimensions.map((dimension, index) => (
              <li
                key={dimension}
                className={
                  activeStep >= 2 && index <= (activeStep - 2) * 3 + 1
                    ? "is-highlighted"
                    : ""
                }
              >
                {dimension}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </article>
  );
}

type ReplicationStudy = "cerono" | "anagnostakis";

const replications = {
  cerono: {
    label: "Cerono et al.",
    paperUrl: "https://doi.org/10.1002/ana.78033",
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
    paperUrl: "https://doi.org/10.1111/dom.70336",
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
        <span>Literature replication evidence</span>
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
            <h3>
              <ProductLink href={selected.paperUrl}>{selected.label}</ProductLink>
            </h3>
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
          Aggregate estimates are shown for comparison. Patient-level replication data
          are not included in the public repository.
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

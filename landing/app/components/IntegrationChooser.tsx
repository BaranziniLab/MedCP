"use client";

import { useState } from "react";

type IntegrationKey =
  | "biorouter"
  | "codex"
  | "claude-code"
  | "claude-desktop"
  | "source";

type Integration = {
  key: IntegrationKey;
  label: string;
  status: string;
  summary: string;
  requirements: string;
  command: string;
  note: string;
  download?: {
    label: string;
    href: string;
  };
};

const integrations: Integration[] = [
  {
    key: "biorouter",
    label: "BioRouter",
    status: "Verified host",
    summary:
      "The canonical MedCP benchmark harness, with local orchestration and keyring-backed secret storage.",
    requirements: "BioRouter, uv, and an approved database path",
    command: `biorouter extension install MedCP.brxt \\
  --env CLINICAL_RECORDS_BACKEND=sqlite \\
  --env CLINICAL_RECORDS_SQLITE_PATH=/absolute/path/database.sqlite`,
    note:
      "Verified with BioRouter 1.88.6. Values entered through its secret-setting flow can use the configured OS keyring. The full model and data path still needs institutional approval.",
    download: {
      label: "Get staged MedCP.brxt",
      href: "https://raw.githubusercontent.com/BaranziniLab/MedCP/main/releases/MedCP%20v0.10.0/MedCP.brxt",
    },
  },
  {
    key: "codex",
    label: "Codex CLI",
    status: "Verified host",
    summary:
      "Register a locked source checkout with Codex, then inspect the MCP registration before querying data.",
    requirements: "Codex with MCP support, Git, and uv",
    command: `git clone https://github.com/BaranziniLab/MedCP.git
cd MedCP
uv sync --locked
MEDCP_SOURCE="$PWD" integrations/codex/install.sh
codex mcp get medcp`,
    note:
      "Codex CLI settings may retain environment values in plaintext. Use non-PHI or appropriately de-identified data unless the complete Codex path is institutionally approved.",
  },
  {
    key: "claude-code",
    label: "Claude Code",
    status: "Source setup",
    summary:
      "Install the MedCP plugin from a source checkout while the staged package awaits a matching release tag.",
    requirements: "Claude Code 2.x or newer, Git, and uv",
    command: `git clone https://github.com/BaranziniLab/MedCP.git
cd MedCP
/plugin marketplace add /absolute/path/to/MedCP/integrations
/plugin install medcp@medcp-integrations`,
    note:
      "Claude Code can inherit or persist configuration values. Use non-PHI or appropriately de-identified data unless the complete Claude path is institutionally approved.",
  },
  {
    key: "claude-desktop",
    label: "Claude Desktop",
    status: "macOS Apple silicon",
    summary:
      "Install the self-contained MCPB, approve its requested fields, and configure MedCP under Extensions.",
    requirements: "Claude Desktop with MCPB support on Apple silicon",
    command: `1. Download MedCP.mcpb
2. Double-click the package
3. Open Settings > Extensions > MedCP
4. Configure a read-only database account, or start with SPOKE only`,
    note:
      "Sensitive manifest fields are protected in Claude Desktop. That does not certify the model, network, retention, or data-governance path for PHI.",
    download: {
      label: "Get staged MedCP.mcpb",
      href: "https://raw.githubusercontent.com/BaranziniLab/MedCP/main/releases/MedCP%20v0.10.0/MedCP.mcpb",
    },
  },
  {
    key: "source",
    label: "Direct source",
    status: "Most portable",
    summary:
      "Run the locked Python core directly. With no clinical variables set, MedCP starts in SPOKE-only mode.",
    requirements: "Python 3.11 or newer, Git, and uv",
    command: `git clone https://github.com/BaranziniLab/MedCP.git
cd MedCP
uv sync --locked
uv run --locked medcp`,
    note:
      "The server runs locally over stdio. Database endpoints may still be remote, and results return to the host that launched MedCP.",
  },
];

export function IntegrationChooser({ compact = false }: { compact?: boolean }) {
  const [activeKey, setActiveKey] = useState<IntegrationKey>("biorouter");
  const [copied, setCopied] = useState(false);
  const active =
    integrations.find((integration) => integration.key === activeKey) ??
    integrations[0];

  async function copyCommand() {
    await navigator.clipboard.writeText(active.command);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  }

  function moveTab(
    event: React.KeyboardEvent<HTMLButtonElement>,
    currentIndex: number,
  ) {
    let nextIndex = currentIndex;

    if (event.key === "ArrowRight") {
      nextIndex = (currentIndex + 1) % integrations.length;
    } else if (event.key === "ArrowLeft") {
      nextIndex =
        (currentIndex - 1 + integrations.length) % integrations.length;
    } else if (event.key === "Home") {
      nextIndex = 0;
    } else if (event.key === "End") {
      nextIndex = integrations.length - 1;
    } else {
      return;
    }

    event.preventDefault();
    const next = integrations[nextIndex];
    setActiveKey(next.key);
    setCopied(false);
    window.requestAnimationFrame(() => {
      document.getElementById(`tab-${next.key}`)?.focus();
    });
  }

  return (
    <div className={`integration-chooser${compact ? " is-compact" : ""}`}>
      <div className="integration-tabs" role="tablist" aria-label="MedCP integrations">
        {integrations.map((integration, index) => (
          <button
            key={integration.key}
            id={`tab-${integration.key}`}
            role="tab"
            type="button"
            aria-selected={integration.key === activeKey}
            aria-controls="integration-panel"
            tabIndex={integration.key === activeKey ? 0 : -1}
            onClick={() => {
              setActiveKey(integration.key);
              setCopied(false);
            }}
            onKeyDown={(event) => moveTab(event, index)}
          >
            {integration.label}
          </button>
        ))}
      </div>

      <div
        className="integration-panel"
        id="integration-panel"
        role="tabpanel"
        aria-labelledby={`tab-${active.key}`}
      >
        <div className="integration-copy">
          <span className="status-pill">{active.status}</span>
          <h3>{active.label}</h3>
          <p>{active.summary}</p>
          <dl>
            <div>
              <dt>Needs</dt>
              <dd>{active.requirements}</dd>
            </div>
            <div>
              <dt>Data boundary</dt>
              <dd>{active.note}</dd>
            </div>
          </dl>
          {active.download ? (
            <a className="text-link" href={active.download.href}>
              {active.download.label} <span aria-hidden="true">↓</span>
            </a>
          ) : null}
        </div>

        <div className="install-code">
          <div className="code-label">
            <span>Setup</span>
            <button type="button" onClick={copyCommand}>
              {copied ? "Copied" : "Copy"}
            </button>
          </div>
          <pre tabIndex={0}>
            <code>{active.command}</code>
          </pre>
          <span className="sr-only" aria-live="polite">
            {copied ? `${active.label} setup copied to clipboard.` : ""}
          </span>
        </div>
      </div>
    </div>
  );
}

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

async function render(pathname = "/") {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}-${pathname}`);
  const { default: worker } = await import(workerUrl.href);

  return worker.fetch(
    new Request(`http://localhost${pathname}`, {
      headers: { accept: "text/html" },
    }),
    {
      ASSETS: {
        fetch: async () => new Response("Not found", { status: 404 }),
      },
    },
    {
      waitUntil() {},
      passThroughOnException() {},
    },
  );
}

test("server-renders the MedCP landing page", async () => {
  const response = await render("/");
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(html, /The private data port for medical AI/);
  assert.match(html, /One read-only port for OMOP records and biomedical knowledge graphs/);
  assert.match(html, /One interface\. Two key components\./);
  assert.match(html, /Preconfigured for the SPOKE knowledge graph/);
  assert.match(html, /MedCP \+ SPOKE compared with MedCP EHR-only/);
  assert.match(html, /In sickle cell disease, which infection diagnoses/);
  assert.match(html, /1,783 patients using standard descendants/);
  assert.match(html, /Mean expert score: 2 of 2/);
  assert.match(html, /1\.265/);
  assert.match(html, /Score comparison: paired t-test p=0\.0026/);
  assert.match(html, /How MedCP links EHR comorbidity to SPOKE biology/);
  assert.match(html, /Read-only Cypher/);
  assert.match(html, /What the study found/);
  assert.match(html, /It does not show cause and effect/);
  assert.match(html, /Control the full data path/);
  assert.match(html, /USB port/);
  assert.match(html, /BioRouter/);
  assert.match(html, /Codex CLI/);
  assert.match(html, /MedCP © 2025-2026/);
  assert.match(html, />Baranzini Lab<\/a>/);
  assert.match(html, /https:\/\/doi\.org\/10\.1002\/ana\.78033/);
  assert.match(html, /https:\/\/biorouter\.ucsf\.edu\//);
  assert.match(html, /https:\/\/learn\.chatgpt\.com\/docs\/codex\/cli/);
  assert.match(html, /https:\/\/claude\.com\/product\/claude-code/);
  assert.match(html, /https:\/\/claude\.com\/download/);
  assert.match(html, /https:\/\/baranzinilab\.ucsf\.edu\//);
  assert.match(html, /M2 8H44M38 2L44 8L38 14/);
  assert.ok(
    html.indexOf('id="integrations"') < html.indexOf('id="evidence"'),
    "integrations should appear before measured evidence",
  );
  assert.doesNotMatch(html, /MedCP-(?:list|query|get)_/);
  assert.doesNotMatch(html, /Cross-source association|Hypothesis-generating association/);
  assert.doesNotMatch(html, /184,356 prescriptions|Without database access, illustrative/);
  assert.doesNotMatch(html, /1\.19|0\.925|BH-adjusted p=\.091/);
  assert.doesNotMatch(html, /USB-C|Wanjun Gu|Gianmarco Bellucci/);
  assert.doesNotMatch(html, /react-loading-skeleton|Your site is taking shape/i);
  assert.doesNotMatch(html, /\u2014/);
});

test("links both literature replications to their papers", async () => {
  const source = await readFile(
    new URL("../app/components/ResearchDemos.tsx", import.meta.url),
    "utf8",
  );

  assert.match(source, /https:\/\/doi\.org\/10\.1002\/ana\.78033/);
  assert.match(source, /https:\/\/doi\.org\/10\.1111\/dom\.70336/);
  assert.match(source, /<ProductLink href=\{selected\.paperUrl\}>/);
});

test("server-renders complete documentation", async () => {
  const response = await render("/docs");
  assert.equal(response.status, 200);
  const html = await response.text();

  assert.match(html, /Supported clients and backends/);
  assert.match(html, /One de-identified 100-patient MIMIC-IV OMOP demo/);
  assert.match(html, /MedCP alone does not establish HIPAA compliance/);
  assert.match(html, /Staged source-tree packages/);
  assert.match(html, /Open source research software/);
  assert.match(html, /https:\/\/biorouter\.ucsf\.edu\//);
  assert.match(html, /https:\/\/learn\.chatgpt\.com\/docs\/codex\/cli/);
  assert.match(html, /https:\/\/claude\.com\/product\/claude-code/);
  assert.match(html, /https:\/\/claude\.com\/download/);
  assert.doesNotMatch(html, /\u2014/);
});

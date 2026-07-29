import assert from "node:assert/strict";
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
  assert.match(html, /MedCP \+ SPOKE compared with MedCP EHR-only/);
  assert.match(html, /Control the full data path/);
  assert.match(html, /BioRouter/);
  assert.match(html, /Codex CLI/);
  assert.doesNotMatch(html, /react-loading-skeleton|Your site is taking shape/i);
  assert.doesNotMatch(html, /\u2014/);
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
  assert.doesNotMatch(html, /\u2014/);
});

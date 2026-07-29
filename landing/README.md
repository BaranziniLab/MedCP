# MedCP website

The public landing page and documentation for
[BaranziniLab/MedCP](https://github.com/BaranziniLab/MedCP).

## Local preview

Requires Node.js 22.13 or newer.

```bash
npm install
npm run dev
```

Open `http://localhost:3000/`.

## Verification

```bash
npm run lint
npm test
npm run build:pages
```

`npm test` verifies the Vinext build used for the local and Sites runtime.
`npm run build:pages` creates the static GitHub Pages export in `out/` with the
`/MedCP` base path.

## Publishing

The repository workflow in `.github/workflows/pages.yml` publishes `out/` to:

https://baranzinilab.github.io/MedCP/

The `.openai/hosting.json`, Vite configuration, and worker entry point support
the parallel OpenAI Sites deployment.

## Content sources

- Product behavior, integrations, testing, and legal boundaries come from the
  main MedCP repository.
- Interactive evidence views use reported benchmark and literature-replication
  values from the project analyses.
- `public/llms.txt` gives agents a concise, source-safe setup path.

MedCP is research software. It does not certify an AI host, model provider, or
deployment as HIPAA compliant.

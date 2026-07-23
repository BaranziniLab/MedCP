# MedCP — BioRouter extension

A [BioRouter](https://biorouter.ucsf.edu) extension (`.brxt`) that exposes
MedCP's read-only clinical-records and knowledge-graph tools, plus a bundled
`medcp-clinical-records` skill. It packages the shared `medcp` core as a
self-contained Python MCP server. See [`../README.md`](../README.md) for how
this integration relates to the others.

## Layout

```text
biorouter/
├── manifest.json                         # BioRouter extension metadata + env vars
├── pyproject.toml                        # Python package (entry_point: medcp)
├── README.md
├── skills/medcp-clinical-records/SKILL.md
├── src/medcp/                            # GENERATED: copy of ../../src/medcp (git-ignored)
└── uv.lock                               # GENERATED: uv lockfile (git-ignored)
```

`src/medcp/` is **copied from the shared core** by
[`../../scripts/build_releases.py`](../../scripts/build_releases.py) at build
time — do not edit it here. That script also generates the `uv.lock`. Both
`src/` and `uv.lock` are git-ignored, but both are bundled into the `.brxt`.

## Build the .brxt

```bash
python3 ../../scripts/build_releases.py --only biorouter
# → releases/MedCP v0.9/MedCP.brxt
```

The script copies the core into `src/`, runs `uv lock` (verifying cross-platform
wheel resolution, including Intel macOS), and zips the required entries:
`manifest.json`, `README.md`, `pyproject.toml`, `src/`, `skills/`, and the
generated `uv.lock`.

## Install

Requires [`uv`](https://docs.astral.sh/uv/) — BioRouter runs `uv sync` on install.

```bash
# SQLite EHR (e.g. the sham OMOP dataset)
biorouter extension install "releases/MedCP v0.9/MedCP.brxt" \
  --env CLINICAL_RECORDS_BACKEND=sqlite \
  --env CLINICAL_RECORDS_SQLITE_PATH=/absolute/path/to/database.sqlite

# MySQL / SQL Server: pass server/database/username + a secret password
biorouter extension install "releases/MedCP v0.9/MedCP.brxt" \
  --env CLINICAL_RECORDS_BACKEND=mysql \
  --env CLINICAL_RECORDS_SERVER=db.example.org \
  --env CLINICAL_RECORDS_DATABASE=omop \
  --env CLINICAL_RECORDS_USERNAME=reader \
  --secret CLINICAL_RECORDS_PASSWORD=•••••
```

`--env` sets a plain variable; `--secret` stores the value in the OS keyring.
Remove the extension with `biorouter extension remove medcp`.

## Use

In a BioRouter session, ask e.g. *"List the clinical tables, then count patients
by gender."* BioRouter auto-loads the `medcp-clinical-records` skill and calls
the read-only MedCP tools.

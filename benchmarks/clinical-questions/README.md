# MedCP clinical-questions benchmark

Runs the 100 clinical questions in [`benchmarking_questions.csv`](benchmarking_questions.csv)
through the MedCP BioRouter extension (referenced in each prompt as `/ext:medcp`)
for several models and two tool conditions, and renders each answer to the
archived markdown format via [`format_response.py`](format_response.py).

## Models × conditions (6 runners)

| Runner | Model | Provider | Condition |
|---|---|---|---|
| `run_benchmark_gpt5.5_withkg.py` | GPT-5.5 | Versa Azure (`versa_azure`) | EHR **+** SPOKE KG |
| `run_benchmark_gpt5.5_withoutkg.py` | GPT-5.5 | Versa Azure | EHR only |
| `run_benchmark_opus4.8_withkg.py` | Claude Opus 4.8 | Versa Bedrock (`versa_bedrock`) | EHR **+** SPOKE KG |
| `run_benchmark_opus4.8_withoutkg.py` | Claude Opus 4.8 | Versa Bedrock | EHR only |
| `run_benchmark_qwen3.6_withkg.py` | Qwen3.6 35B (MoE) | Local Ollama (`ollama`) | EHR **+** SPOKE KG |
| `run_benchmark_qwen3.6_withoutkg.py` | Qwen3.6 35B (MoE) | Local Ollama | EHR only |

`withkg` = full tools (EHR + SPOKE knowledge graph); `withoutkg` = EHR only
(`MEDCP_DISABLE_KNOWLEDGE_GRAPH=1`).

## Prerequisites (already set up on this machine)

- **BioRouter** CLI on `PATH`, with the **`medcp` extension installed + enabled**
  (v0.9, async), configured against the UCSF EHR (`OMOP_DEID`, SQL Server).
- **Ollama** running with **qwen3.6** pulled (`ollama pull qwen3.6`) — for the
  local model only.
- A **clean tool environment**: `medcp` is the only enabled non-builtin
  extension; `code_execution` and other non-builtin extensions are disabled (so
  tools are called directly as `MedCP-*`); non-builtin KBs/skills disabled,
  built-ins kept. The medcp extension's per-tool-call timeout is set to **600s**.
- Recommended: **quit the BioRouter desktop app** during the runs — a running
  desktop app writes to the same `sessions.db` and can collide with the CLI
  ([BaranziniLab/biorouter#31](https://github.com/BaranziniLab/biorouter/issues/31)).
  The runners already use a unique `--name` per question to minimize this.

## How to launch

### 1. Warm the local model (once, before the qwen runs)

```bash
python3 warmup.py          # loads qwen3.6 into Ollama and keeps it resident
```

### 2. Run the benchmarks — **one at a time** (not in parallel)

```bash
# with knowledge graph (EHR + SPOKE)
python3 run_benchmark_gpt5.5_withkg.py
python3 run_benchmark_opus4.8_withkg.py
python3 run_benchmark_qwen3.6_withkg.py

# EHR only (knowledge-graph tools disabled)
python3 run_benchmark_gpt5.5_withoutkg.py
python3 run_benchmark_opus4.8_withoutkg.py
python3 run_benchmark_qwen3.6_withoutkg.py
```

Run them **sequentially** — concurrent `biorouter run` processes collide on the
shared `sessions.db` (#31).

**Knobs** (environment variables):
- `MAX_TURNS` (default `50`) — max agent turns per question.
- `SLEEP` (default `10`) — seconds between questions.

```bash
MAX_TURNS=80 SLEEP=5 python3 run_benchmark_opus4.8_withkg.py
```

Runners are **resume-friendly**: re-running skips any question whose `.md`
already exists, so an interrupted run continues where it left off.

## Outputs

```
responses/<model>/<condition>/<Qname>.md     # archived-format answer
responses/<model>/<condition>/<Qname>.json   # raw biorouter JSON transcript
responses/<model>/<condition>/<Qname>.log    # stderr
```

`<model>` ∈ {`gpt5.5`, `opus4.8`, `qwen3.6`}; `<condition>` ∈ {`withkg`,
`withoutkg`}.

## Files

| File | Purpose |
|---|---|
| `benchmarking_questions.csv` | the 100 questions (`question_name,question`) — single shared source |
| `run_benchmark_*.py` | one runner per model × condition; reads the CSV, calls `biorouter run`, formats the result |
| `format_response.py` | biorouter JSON → archived markdown (question, per-step reasoning + tools, metrics incl. elapsed time, tool inputs) |
| `warmup.py` | preload the local Ollama model (`keep_alive=-1`) |
| `pyproject.toml` / `uv.lock` | optional uv env (all scripts are stdlib-only, so `python3` works directly) |

## Notes

- Cloud models (GPT-5.5, Opus 4.8) finish a question in ~1–8 min; the local
  Qwen3.6 is slower. A single-question smoke test on Q1.1 (with KG) gave
  GPT-5.5 = 5,900, Opus 4.8 ≈ 5,900, Qwen3.6 = 6,228 patients (the small 8B
  Gemma 4 could not complete the SQL tool-use and was dropped).
- To reset a model/condition, delete its `responses/<model>/<condition>/` folder
  and re-run.

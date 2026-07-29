# BiomixQA with and without SPOKE knowledge-graph grounding — per-item responses

Per-item responses of two frontier large language models on the BiomixQA gene–disease benchmark.
Each model answered every question **twice**: once from parametric memory alone, and once as an agent with read-only access to the SPOKE biomedical knowledge graph through the Model Context Protocol (MCP) using MedCP. 

## Dataset

BiomixQA is the human-curated biomedical question set released with the KG-RAG framework [1]. We use
its gene–disease association items: **617 questions, 311 true/false (TF) and 306 five-option
multiple-choice (MCQ)**. Each MCQ presents a pair of diseases and five candidate genes, of which
exactly one carries the queried association.

| Subset          | n   | Chance | Reference baseline                              |
| --------------- | --- | ------ | ----------------------------------------------- |
| True/false      | 311 | 0.50   | **0.633** majority class (197 true / 114 false) |
| Multiple choice | 306 | 0.20   | 0.20                                            |

The true/false items are imbalanced, so 0.633 rather than 0.50 is the meaningful floor for TF.

## Models

- **Claude Opus 4.8**

- **GPT-5.5**

Serving backends and agent harnesses are intentionally not part of this release.

## The two configurations

Both arms saw identical items, identical prompt templates and an identical answer format. The arms
differ **only** in access to the knowledge graph, and every item was answered in both arms by both
models, so all comparisons are paired on the same items and each model acts as its own control.

**`without SPOKE`**** — parametric memory alone.** The model answered from its internal knowledge only:
no tools, no retrieval, no web access. Verified per item (`n_tool_calls = 0`).

**`with SPOKE`**** — knowledge-graph grounded.** The model answered as an agent with read-only access to
SPOKE [2] exposed over MCP. The model composed and issued its own Cypher queries against the graph,
capped at 10 queries per item, with no other tool available. Every query issued is recorded in the
data (`cypher_queries`), together with how many returned no rows (`empty_result_calls`).

Note that grounding here is *agentic retrieval*:  the model decides what to look for in the Graph,  and reformulates after an unhelpful result.

## File

`biomixqa_responses.csv` — 2468 rows, one per (item × model × arm): 617 items × 2 models × 2 arms.

| Column               | Description                                                     |
| -------------------- | --------------------------------------------------------------- |
| `item`               | Item identifier (`TF####` / `MC####`)                           |
| `type`               | `true_false` or `mcq`                                           |
| `subset`             | `True/False` or `Multiple choice`                               |
| `question`           | Question text as presented to the model                         |
| `options`            | Pipe-separated candidate genes (MCQ only; empty for true/false) |
| `gold`               | Reference answer                                                |
| `model`              | `Opus 4.8` or `GPT-5.5`                                         |
| `arm`                | `without SPOKE` or `with SPOKE`                                 |
| `raw_response`       | The model's response, verbatim                                  |
| `parsed_answer`      | Answer extracted from `raw_response`                            |
| `correct`            | 1 / 0, re-derived (see below)                                   |
| `parse_failure`      | 1 if no answer could be parsed; such rows are scored incorrect  |
| `n_tool_calls`       | Tool invocations for that item (0 in every `without SPOKE` row) |
| `n_cypher`           | Cypher queries issued (`with SPOKE` only)                       |
| `empty_result_calls` | Queries that returned no rows (`with SPOKE` only)               |
| `tool_error_calls`   | Queries that errored (`with SPOKE` only)                        |
| `cypher_queries`     | The queries themselves, joined by `;;` (`with SPOKE` only)      |

## References

1. Soman K, et al. Biomedical knowledge graph-optimized prompt generation for large language models. *Bioinformatics*. 2024;40(9):btae560.
doi:[10.1093/bioinformatics/btae560](https://doi.org/10.1093/bioinformatics/btae560)

2. Morris JH, et al. The scalable precision medicine open knowledge engine (SPOKE): a massive knowledge graph of biomedical information. *Bioinformatics*. 2023;39(2):btad080.
doi:[10.1093/bioinformatics/btad080](https://doi.org/10.1093/bioinformatics/btad080)

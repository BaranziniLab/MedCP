# Rerun status — final

Re-run on **biorouter 1.88.6** with all filesystem/traversal builtins disabled.

| model | withkg | withoutkg | total |
|---|---|---|---|
| opus4.8 | **100/100** | **100/100** | **200/200** |
| gpt5.5 | 99/100 | **100/100** | **199/200** |

**399/400.** qwen3.6 was discontinued at the maintainer's request; its answers
remain in git history at `d6c2a31` and were removed from the working tree in
`4b83f56`.

## Verification

* **Completeness** — all 100 question IDs present in each of the four conditions.
* **Failures** — one: `gpt5.5/withkg/Q10.10`.
* **Contamination** — 0 transcripts referenced previous-run answers. The
  `archive/` folder was moved out of the working directory for the whole run and
  restored afterwards.
* **Traversal** — 5 of 400 answers touched a file/shell tool (down from 76 of 539
  before the builtins were disabled; qwen3.6 accounted for 75 of those).
* **Timing** — opus4.8 mean 18.3 min / median 5.4; gpt5.5 mean 18.1 / median 8.1.

## The one unanswered question

`gpt5.5/withkg/Q10.10` — *"In older adults with multimorbidity, which
polypharmacy reduction pattern (deprescribing anticholinergics vs
sedative-hypnotics) is followed by a lower 90-day fall proportion..."*

Three attempts, each ~50-60 min, all ending the same way: the broad OMOP cohort
query times out, then narrower follow-ups fail because the SQL transport has
closed. The final attempt ran 8558 s over 15 tool calls.

This is **not** a harness defect and not a dead question: **opus4.8 answered the
same question successfully**. It is an interaction between gpt5.5's broader query
strategy and what the SQL Server will sustain. Connectivity was verified
independently while it was failing — VPN tunnel up, EHR resolving to its internal
address, and a live `medcp` query returning in 9 s.

The model's own answer states the limitation plainly rather than inventing
numbers, and then reasons mechanistically, so the file is usable as an honest
"could not compute from EHR" response if that is preferable to leaving it blank.

## What made the rerun work

1. **biorouter 1.88.6** — a tool error (e.g. the model sending `LIMIT` to SQL
   Server) no longer kills the run, and concurrent runs no longer collide on
   `msg_uid`. The former blocker, opus4.8 on Q3.1, died in ~15 s on every attempt
   before and answers in 93 s now.
2. **Parallelism** — up to 24 concurrent runs (13 opus + 11 gpt). Zero session
   collisions, zero provider failures, zero EHR connection errors throughout.
3. **A low-concurrency tail pass** for the stragglers. These resolve a cohort and
   then time out on a large `measurement`/`drug_era` rollup, so they need SQL
   Server headroom rather than more workers. Re-running them 3 at a time fixed
   three of four on the first attempt — including Q5.3, which had failed three
   times at ~92 min each under load and then completed in **221 s**.

## Operational note

Killing a lane's Python parent orphans its `biorouter` children, which keep their
`medcp` MCP subprocesses alive; those accumulate (106 medcp processes for 16 runs
at one point) and inflate load. Kill `biorouter` processes first, or sweep
`ppid=1` orphans afterwards. Tested separately: biorouter 1.88.6 cleans up its
MCP subprocess correctly on both normal exit and `SIGKILL`, so this is a
kill-ordering issue in the harness scripts, not a biorouter or medcp defect.

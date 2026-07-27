# opus4.8 — blocked runs, root cause, and the fix (handoff)

**Status when handed off (2026-07-25 ~02:00):** opus4.8 has **~122 good** answers of 200.
The remaining ~78 fail at ~86% and are NOT recoverable by retrying — they hit a
biorouter bug. gpt5.5 and qwen3.6 are unaffected and are being completed first.

## Root cause (verified, not inferred)

1. The model sends SQL Server a query with **`LIMIT n`** (Postgres/MySQL syntax):

   ```sql
   SELECT concept_id, concept_name, ... FROM omop.concept
   WHERE lower(concept_name) LIKE '%egfr%' ... ORDER BY ... LIMIT 50
   ```

2. SQL Server rejects it and medcp returns a tool error:

   ```
   [tool_error kind=tool_failure retryable=false] ... Electronic health records error:
   (102, b"Incorrect syntax near 'LIMIT'. DB-Lib error message 20018, severity 15: ...")
   ```

3. After such an error (often the 2nd in a row) biorouter aborts its tool loop:

   ```
   The tool calling loop was interrupted. How would you like to proceed?
     error: The error above was an exception we were not able to handle.
   We've removed the conversation up to the most recent user message
   ```

4. That recovery rewrites the persisted history and re-inserts duplicate ids:

   ```
   Error: error returned from database: (code: 2067)
   UNIQUE constraint failed: messages.session_id, messages.msg_uid
   ```

   The run dies: `(no text response)`, **0 tool calls**, and `--output-format json`
   emits prose before the JSON so it will not parse.

**Reproducible with a single run, its own `XDG_DATA_HOME`, an idle machine, and
with `--no-session`.** Dies in ~15 s. Filed upstream:
<https://github.com/BaranziniLab/biorouter/issues/41> (comment has the full reproducer).

**Not a CPU/concurrency problem** — earlier correlations with qwen/parallel lanes
were spurious and have been retracted in the issue.

**Not purely a model-capability gap either:** all three models emit `LIMIT`
sometimes (gpt5.5 in 140/189 transcripts, opus 87/130, qwen 71/78), and **84–96%
of successful runs contained SQL/tool errors and finished fine** — models
normally read the error and switch to `TOP`. The bug denies opus that chance.

## The fix (chosen: option A — fix medcp, re-run opus only)

`src/medcp/server.py`, in `_query_clinical_records_impl` (and the same pattern in
the knowledge-graph impls):

```python
            except ToolError:
                raise
            except Exception as e:
                raise ToolError(f"Electronic health records error: {e}")   # <-- current
```

Change the **query-execution** failure path to return the error as a NORMAL
`ToolResult` instead of raising, e.g.:

```python
            except Exception as e:
                logger.debug(...)
                return ToolResult(content=[TextContent(
                    type="text",
                    text=f"Electronic health records error: {e}")])
```

Rationale: a model writing malformed SQL is **expected, recoverable feedback**,
not a tool failure. The model still sees the identical error text and can correct
its query; biorouter never enters the exception/recovery path, so it cannot
collide. Keep raising `ToolError` for genuine failures (connection/config/auth)
and keep the read-only validator raising as it does today.

After the change, rebuild/reinstall the medcp extension so `biorouter` picks it
up (the installed copy lives at `~/.config/biorouter/extensions/medcp`).

**A ready-to-apply patch is saved next to this file** (verified to apply cleanly
against the committed `src/medcp/server.py`; the source itself is left unmodified
so the change is yours to make):

```bash
cd /Users/wgu/Desktop/MedCP
git apply benchmarks/clinical-questions/run_logs/opus_fix.patch
python3 -m py_compile src/medcp/server.py     # sanity check
# then reinstall the extension so biorouter picks it up
```

## Re-running opus afterwards

Purge + re-run only opus (runners skip completed questions, hold a singleton
lock, and use a fresh per-question `XDG_DATA_HOME`):

```bash
cd /Users/wgu/Desktop/MedCP/benchmarks/clinical-questions
python3 - <<'PY'
import sys, glob, os
sys.path.insert(0, "<scratchpad>")   # dir containing retry_failed.py
import retry_failed as R
for f in glob.glob('responses/opus4.8/*/*.md'):
    if R.is_bad(f):
        for e in ('.md','.json','.log'):
            try: os.remove(f[:-3]+e)
            except OSError: pass
PY
python3 run_benchmark_opus4.8_withkg.py
python3 run_benchmark_opus4.8_withoutkg.py
```

Run opus **alone** (no other `biorouter run` alongside) and expect ~12 questions/hr.

## Caveat to record in the manuscript

opus4.8's re-run happens under slightly different tool-error semantics than the
gpt5.5/qwen3.6 runs (error returned as a normal result vs. a protocol tool
error). The information shown to the model is the same; only the MCP-level flag
differs. Option B (re-run all 600 under the fixed medcp) is the fully symmetric
alternative if the comparison needs to be airtight.

---

## ⚠️ BEFORE you re-run opus: re-quarantine the previous answers

`benchmarks/clinical-questions/archive/` was temporarily moved out of the working
directory during this run because models were reading the previous answers from
it (7 gpt5.5 questions were contaminated and had to be redone — see
BENCHMARK_TECHNICAL_NOTES.md "Hiccup #5"). It has now been **restored** so the
repo is intact for this commit.

Because the `developer` builtin's shell/text_editor tools cannot actually be
disabled (biorouter#42), a model can still find and read those files. So before
re-running opus:

```bash
cd /Users/wgu/Desktop/MedCP/benchmarks/clinical-questions
mv archive /Users/wgu/Desktop/MedCP_previous_answers_QUARANTINED_archive
# ... run opus ...
mv /Users/wgu/Desktop/MedCP_previous_answers_QUARANTINED_archive archive
```

Verify nothing leaks (should print 0):

```bash
grep -RIl "Claude's Response" . | wc -l
```

Afterwards, audit the new opus transcripts the same way:

```bash
grep -l "Claude's Response\|archive/responses" responses/opus4.8/*/*.json
```

A copy of the same previous answers also exists at
`/Users/wgu/Desktop/medcp-manuscript/benchmarking/responses/` (never accessed by
any run so far, but reachable by absolute path).

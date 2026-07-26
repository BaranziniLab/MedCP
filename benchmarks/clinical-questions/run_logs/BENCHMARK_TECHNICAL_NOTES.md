# Benchmark run — technical notes / hiccups log

Run started 2026-07-22 19:02. Order: gpt5.5 → opus4.8 → qwen3.6, each withkg then withoutkg.

## Hiccup #1 — biorouter "sensitive system operation" stall (Q4.5, gpt5.5/withkg)

**Symptom.** Q4.5 (CKD/ACEi-ARB hyperkalemia trend) ran 1822s then failed:
- `.md`: "(no text response)", 0 tool calls, `Success = False`.
- `.log` (stderr): `Error: not connected`.
- `.json` (218 b, not valid JSON) contained a biorouter permission prompt:
  *"🔒 Sensitive system operation in Fully-Automatic mode. This tool call writes
  to /dev/null (a protected system directory). Approve it to continue…"*

**Root cause.** The model (gpt5.5) sometimes uses the biorouter builtin `shell`
tool, which can redirect to `/dev/null`. biorouter's permission layer treats a
write to a protected path (`/dev/null`) as a "sensitive system operation" and
prompts — even though `permission.yaml`'s `always_allow` lists `developer__shell`
etc. (that list does not cover the protected-path gate). In non-interactive
`--quiet` mode there is no one to approve, so the run stalls until it dies with
`Error: not connected`, producing no answer.

**Not a model-capability failure.** 0 tool calls, no reasoning — the model never
got to work; the harness blocked it. `/dev/null` writes also appear in Q1.2,
Q2.1, Q3.10 transcripts, all of which SUCCEEDED — so the stall is a
non-deterministic race, not a per-question deterministic failure (~1/36 ≈ 3%).

**Why not "fix" by changing the environment.** The builtins (shell, text_editor,
todo, plan, chart) were kept intentionally; the 36 already-completed answers ran
with them available. Disabling tools mid-run would make the benchmark
inconsistent across questions. So the environment is left unchanged.

**Handling.** Retry after the run: `scratchpad/retry_failed.py` finds any output
with a technical-failure signature (empty / Success=False / tiny / error marker),
deletes it, and re-runs the owning runner (which redoes only deleted questions).
Non-deterministic → retries almost always succeed. Anything still failing after
MAX_ATTEMPTS is documented here. Retries run only when the main driver is idle
(concurrent `biorouter run` collides on sessions.db, biorouter#31).

## Resolution applied 2026-07-23 00:50 (after Q5.2, 2nd stall)

The stall recurred (Q5.2, same `/dev/null` + `Error: not connected`, ~5% rate,
each wasting ~25-30 min), and both stalls were complex trend questions where the
model reaches for `shell` — so retries of those could keep stalling. Prevented at
the source instead of only retrying:

- `config.yaml`: set `enabled: false` for the **`developer`** (shell, text_editor)
  and **`computercontroller`** builtins. Rationale: these are arbitrary
  system-op tools — the same category as `code_execution`, which was ALREADY
  disabled. They are the only source of the protected-path writes, are used
  incidentally (~3/42), and never produce the actual clinical answers (those come
  from MedCP). Backup: `config.yaml.bak-before-devdisable`. Reversible.
- Applied atomically (temp + `os.replace`); each `biorouter run` re-reads config,
  so it takes effect on the NEXT question — no driver restart, no disruption.
- Benign builtins kept enabled: todo, plan/skills, autovisualiser (charts),
  memory, knowledge, extensionmanager, medcp.

**Consistency handling.** `retry_failed.py` now redoes not just technical
failures but any completed answer that CALLED a now-disabled tool, so no final
answer depends on a capability the later questions lacked. For gpt5.5/withkg that
is 5 redo's: Q4.5, Q5.2 (stalls) + Q1.2, Q2.1, Q3.10 (used shell/text_editor).
Only caveat: gpt5.5/withkg Q1-Q42 had those tools *available* (unused in 37/42);
"available-but-unused" == "unavailable" for the produced answer, so those 37
stand. Runners 2-6 run entirely under the clean environment.

## Hiccup #2 — UCSF Azure gpt-5.5 provider outage (2026-07-23 ~07:18–08:53)

**Symptom.** Starting ~Q8.2, gpt5.5 questions failed fast (~60s, `Success=False`),
stderr `Error: the turn did not complete: provider_failure`, answer text:
*"503 service unavailable … HTTP POST … mule-prod-openai-lb.ucsf.edu … gpt-5.5 …
Contact Mule support team."* By the 08:50 checkpoint ~30 withkg (Q8–Q10) and all
~26 started withoutkg questions had failed.

**Root cause.** Transient outage of UCSF's Azure OpenAI gateway (Mule LB) — an
upstream infra problem, NOT medcp/EHR/model-capability. Affected ONLY gpt5.5
(versa_azure); opus4.8 (Bedrock) and qwen3.6 (Ollama) use different providers.

**Actions.**
1. Stopped the driver at 08:53 to halt the failure churn.
2. Tested the endpoint (trivial gpt-5.5 call, no medcp) → succeeded → Azure had
   recovered.
3. Hardened the runners: `ask()` now detects a transient provider failure
   (stderr contains `provider_failure`/`did not complete`) and retries the
   question up to `PROVIDER_RETRIES=3` times with `PROVIDER_BACKOFF=60s` before
   giving up — so a short blip self-heals instead of churning ~100 failures.
   (Regenerated all 6 runners from the template; compile-checked.)
4. Deleted the 60 failed gpt5.5 outputs (34 withkg + 26 withoutkg), kept the 66
   good withkg answers, and relaunched the driver (08:56) — it skips the 66 and
   redoes the rest.

**Residual risk.** A *long* outage still exceeds the 3 retries; monitoring
(health scan for `Success=False` bursts) catches that and I pause/wait/relaunch.

**Update 09:37-09:42 — Azure still flapping → REORDERED.** After relaunch, the
gpt5.5 redos 503'd again (retry hit 3/3), while isolated tests of opus4.8
(Bedrock) and qwen3.6 (Ollama) succeeded cleanly. Azure is intermittently 5xx.
Decision: run the solid providers first and gpt5.5 LAST, to make guaranteed
progress and give Azure hours to stabilize. New order (`bench_driver2.sh`):
opus4.8 (withkg,withoutkg) -> qwen3.6 (warm, withkg,withoutkg) -> gpt5.5
(withkg,withoutkg). gpt5.5/withkg keeps its 66 good answers; the 34 deleted
failures are redone when gpt5.5 runs last. This deviates from the requested
model order (gpt5.5 first) purely to work around the outage; all 6
model×condition runs still complete.

## Hiccup #3 — biorouter#31 sessions.db collision (opus4.8, ~10:00-10:25)

**Symptom.** During opus4.8/withkg, ~half the questions failed fast (~15-18s),
tiny outputs, stderr `error returned from database: (code: 2067) UNIQUE
constraint failed: messages.session_id, messages.msg_uid`.

**Root cause.** biorouter#31: a SECOND biorouter instance was writing to the same
`~/.local/share/biorouter/sessions/sessions.db` concurrently — `ps` showed
`PID 705: biorouter acp` (the desktop/IDE app). The unique `--name` per question
was NOT enough. (The DB had also bloated to 215 MB.) Unrelated to the Azure
outage; would affect every provider.

**Fix — isolate the session store.** Set `XDG_DATA_HOME` to a benchmark dir so
each `biorouter run` uses its OWN `sessions.db`, making concurrent-write
collisions structurally impossible without touching the user's desktop app.
Verified: an isolated call created its own `bench_xdg/biorouter/sessions/
sessions.db`, left the main 215 MB DB untouched, and medcp still answered
(person rows = 7,168,332). Applied via `export XDG_DATA_HOME=…/bench_xdg` in
`bench_driver2.sh` (runners inherit it) and in `retry_failed.py`'s env.
Relaunched 10:26; biorouter confirmed running with the isolated DB, no UNIQUE
errors. opus4.8/withkg kept its 14 good answers; 16 collided ones redone.

**Summary of the morning's three independent infra issues:** (1) `/dev/null`
permission stall → disabled developer/computercontroller; (2) UCSF Azure gpt-5.5
5xx outage → provider-retry + reordered gpt5.5 last; (3) sessions.db #31 collision
→ isolated `XDG_DATA_HOME`. None are model-capability or medcp-code problems.

## Parallelization (2026-07-23 ~11:00) + Hiccup #4 — per-lane XDG insufficient under load

To speed up, switched to a PARALLEL driver (`bench_driver_par.sh`): cloud phase
runs opus4.8 (with/without KG) + gpt5.5 (with/without KG) as 4 concurrent lanes,
then qwen last (serial, local). First attempt gave each *lane* its own
`XDG_DATA_HOME`, but collisions returned (`UNIQUE constraint … messages.session_id`)
— NOT cross-lane (the 4 DB files were verified separate, main DB untouched) but
WITHIN each lane: ~100 questions shared one lane sessions.db, and under 4-wide CPU
load a biorouter run's lingering session-writer overlapped the *next* question in
the same lane. (Purely sequential it was fast enough to avoid this.)

**Fix — per-QUESTION XDG_DATA_HOME.** The runner now does
`tempfile.mkdtemp()` per `biorouter run` and points `XDG_DATA_HOME` at it (cleaned
up after), so every single invocation gets a pristine single-use sessions.db that
nothing else touches. Stress-verified: **6 concurrent opus runs, each fresh XDG →
0 collisions, 0 provider failures, 6/6 clean**, correct answers, 28 s. Regenerated
all 6 runners; relaunched 11:38 with 4 lanes each on its own `brxdg_*` DB.

This is the general fix for biorouter#31 in any concurrent/batch setting: isolate
per invocation, not per worker.

## Failure / redo ledger
- gpt5.5/withkg Q4.5  — sensitive-op stall (0 tools)         — redo
- gpt5.5/withkg Q5.2  — sensitive-op stall (0 tools)         — redo
- gpt5.5/withkg Q1.2  — used disabled shell/text_editor       — redo (consistency)
- gpt5.5/withkg Q2.1  — used disabled shell/text_editor       — redo (consistency)
- gpt5.5/withkg Q3.10 — used disabled shell/text_editor       — redo (consistency)

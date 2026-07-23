#!/usr/bin/env python3
"""MedCP clinical-questions benchmark - Versa (AWS Bedrock) Claude Opus 4.8 - withoutkg.

Runs each question from benchmarking_questions.csv through the MedCP biorouter
extension (referenced in the prompt as /ext:medcp) by calling the `biorouter run`
CLI via subprocess, then renders the archived markdown format with
format_response.py. Mirrors medcp-manuscript/benchmarking/benchmark.py.

  provider : versa_bedrock
  model    : us.anthropic.claude-opus-4-8
  Determined by testing: Opus 4.8 is served on Versa Bedrock via the us.anthropic.claude-opus-4-8 cross-region inference profile (the bare id and global.* profile are not authorized for UCSF's account).

Condition: EHR-only: knowledge-graph tools disabled via MEDCP_DISABLE_KNOWLEDGE_GRAPH=1.

Environment assumed (so medcp is the only non-builtin tool, called directly):
  * medcp extension installed + enabled; code_execution and all other non-builtin
    extensions disabled; non-builtin knowledge bases / skills disabled (built-ins kept).

Notes:
  * Uses a UNIQUE --name per question (not --no-session): --no-session still
    writes to the shared ~/.local/share/biorouter/sessions/sessions.db and
    collides (UNIQUE constraint messages.session_id, msg_uid) when another
    biorouter process - e.g. the desktop app - runs concurrently
    (BaranziniLab/biorouter#31). A unique --name avoids it.
  * MAX_TURNS default 50 (env-overridable) - generous headroom.
  * Responses -> responses/opus4.8/withoutkg/<Qname>.md  (+ .json raw, .log stderr).
  * Resumable: skips questions whose .md already exists.

NOTHING runs until you execute this file:  python3 run_benchmark_opus4.8_withoutkg.py
Tune with env vars, e.g.:  MAX_TURNS=80 SLEEP=5 python3 run_benchmark_opus4.8_withoutkg.py
"""
import csv
import datetime
import os
import random
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
QUESTIONS_CSV = os.path.join(HERE, "benchmarking_questions.csv")
FORMATTER = os.path.join(HERE, "format_response.py")
OUT = os.path.join(HERE, "responses", "opus4.8", "withoutkg")

PROVIDER = "versa_bedrock"
MODEL = "us.anthropic.claude-opus-4-8"
KG_STATE = "off"          # "on" | "off"
TAG = "opus4.8-withoutkg"
MAX_TURNS = os.environ.get("MAX_TURNS", "50")
SLEEP = float(os.environ.get("SLEEP", "10"))

# Make biorouter findable and set the knowledge-graph toggle for this condition.
ENV = dict(os.environ)
ENV["PATH"] = os.pathsep.join([
    os.path.expanduser("~/.local/bin"), "/opt/homebrew/bin", ENV.get("PATH", "")])
ENV["MEDCP_DISABLE_KNOWLEDGE_GRAPH"] = "1"  # EHR-only: drop the KG tools


def ask(qname, question):
    md = os.path.join(OUT, qname + ".md")
    raw = os.path.join(OUT, qname + ".json")
    log = os.path.join(OUT, qname + ".log")
    if os.path.exists(md) and os.path.getsize(md) > 0:
        print("skip " + qname + " (already done)")
        return
    print("==> " + qname)
    name = "medcp-bench-%s-%s-%d" % (TAG, qname, random.randint(0, 10 ** 9))
    start = time.time()
    with open(raw, "w") as jf, open(log, "w") as lf:
        subprocess.run(
            ["biorouter", "run", "--name", name, "--quiet", "--output-format", "json",
             "--provider", PROVIDER, "--model", MODEL, "--max-turns", str(MAX_TURNS),
             "-t", "/ext:medcp " + question],
            stdout=jf, stderr=lf, env=ENV, check=False)
    elapsed = int(time.time() - start)
    date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(md, "w") as mf:
        subprocess.run(
            [sys.executable, FORMATTER, "--qname", qname, "--question", question,
             "--elapsed", str(elapsed), "--date", date, "--model", MODEL,
             "--provider", PROVIDER, "--kg", KG_STATE, "--json", raw],
            stdout=mf, check=False)
    print("    %s done in %ds" % (qname, elapsed))
    time.sleep(SLEEP)


def main():
    os.makedirs(OUT, exist_ok=True)
    with open(QUESTIONS_CSV, encoding="utf-8") as f:
        rows = [((r.get("question_name") or "").strip(),
                 " ".join((r.get("question") or "").split()))
                for r in csv.DictReader(f)]
    rows = [(n, q) for n, q in rows if n]
    print("Loaded %d questions from %s" % (len(rows), QUESTIONS_CSV))
    for qname, question in rows:
        ask(qname, question)
    print("Done. Responses in " + OUT)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""MedCP clinical-questions benchmark - Versa (AWS Bedrock) Claude Opus 4.8 - withoutkg.

Runs each question from benchmarking_questions.csv through the MedCP biorouter
extension (referenced in the prompt as /ext:medcp) by calling the `biorouter run`
CLI via subprocess, then renders the archived markdown format with
format_response.py.

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
import shutil
import subprocess
import sys
import tempfile
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
PROVIDER_RETRIES = int(os.environ.get("PROVIDER_RETRIES", "3"))   # retries on transient provider outage
PROVIDER_BACKOFF = float(os.environ.get("PROVIDER_BACKOFF", "60"))

# Make biorouter findable and set the knowledge-graph toggle for this condition.
ENV = dict(os.environ)
ENV["PATH"] = os.pathsep.join([
    os.path.expanduser("~/.local/bin"), "/opt/homebrew/bin", ENV.get("PATH", "")])
ENV["MEDCP_DISABLE_KNOWLEDGE_GRAPH"] = "1"  # EHR-only: drop the KG tools


def _is_transient(log_path):
    """True if biorouter failed on a transient provider/infra error (e.g. the
    UCSF Azure/Bedrock gateway returning 5xx) rather than producing a real
    answer. These strings only appear in biorouter's stderr on provider errors."""
    try:
        s = open(log_path, encoding="utf-8", errors="replace").read().lower()
    except OSError:
        return False
    return (("provider_failure" in s) or ("did not complete" in s)
            # biorouter#31 sessions.db race (retry: a fresh run usually wins)
            or ("unique constraint" in s) or ("(code: 2067)" in s))


def _run_biorouter(name, question, raw, log):
    # Fresh, private XDG_DATA_HOME per invocation => a single-use sessions.db that
    # no other process (a concurrent lane, this lane's previous run's lingering
    # session-writer, or the desktop app) can touch. This eliminates the
    # biorouter#31 UNIQUE-constraint collision (messages.session_id, msg_uid)
    # completely, which is what makes safe parallelism possible.
    xdg = tempfile.mkdtemp(prefix="brxdg_")
    env = dict(ENV)
    env["XDG_DATA_HOME"] = xdg
    try:
        with open(raw, "w") as jf, open(log, "w") as lf:
            subprocess.run(
                ["biorouter", "run", "--name", name, "--quiet", "--output-format", "json",
                 "--provider", PROVIDER, "--model", MODEL, "--max-turns", str(MAX_TURNS),
                 "-t", "/ext:medcp " + question],
                stdout=jf, stderr=lf, env=env, check=False)
    finally:
        shutil.rmtree(xdg, ignore_errors=True)


def ask(qname, question):
    md = os.path.join(OUT, qname + ".md")
    raw = os.path.join(OUT, qname + ".json")
    log = os.path.join(OUT, qname + ".log")
    if os.path.exists(md) and os.path.getsize(md) > 0:
        print("skip " + qname + " (already done)")
        return
    print("==> " + qname)
    start = time.time()
    for attempt in range(1, PROVIDER_RETRIES + 1):
        name = "medcp-bench-%s-%s-%d" % (TAG, qname, random.randint(0, 10 ** 9))
        _run_biorouter(name, question, raw, log)
        if not _is_transient(log):
            break
        print("    %s transient provider failure (attempt %d/%d)"
              % (qname, attempt, PROVIDER_RETRIES))
        if attempt < PROVIDER_RETRIES:
            time.sleep(PROVIDER_BACKOFF)
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


def _acquire_singleton_lock():
    """Refuse to run if another instance of THIS runner is already active.

    Prevents a double-run (e.g. a supervisor lane and the phased driver both
    launching the same model+condition), which would race on the same output
    files. Stale locks (dead PID) are reclaimed.
    """
    lock = os.path.join(HERE, ".lock_%s_%s" % ("opus4.8", "withoutkg"))
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return lock
    except FileExistsError:
        pass
    try:
        pid = int(open(lock).read().strip() or 0)
    except (OSError, ValueError):
        pid = 0
    alive = False
    if pid:
        try:
            os.kill(pid, 0)
            alive = True
        except OSError:
            alive = False
    if alive:
        print("another instance of this runner is active (pid %d) - exiting" % pid)
        raise SystemExit(0)
    # stale lock -> reclaim
    try:
        os.remove(lock)
    except OSError:
        pass
    fd = os.open(lock, os.O_CREAT | os.O_WRONLY)
    os.write(fd, str(os.getpid()).encode())
    os.close(fd)
    return lock


def main():
    lock = _acquire_singleton_lock()
    import atexit
    atexit.register(lambda: os.path.exists(lock) and os.remove(lock))
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

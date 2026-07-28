#!/usr/bin/env python3
"""Parallel benchmark runner.

biorouter 1.88.6 fixed the msg_uid collision and the tool-error crash, so runs
can now execute concurrently (verified: 3 concurrent opus runs, 0 collisions).

Usage:
    python3 par_run.py <worklist.json> [THREADS]

worklist.json = [["opus4.8","withkg","Q3.1"], ...]

Each task gets its own private XDG_DATA_HOME (defence in depth against
biorouter#31) and writes responses/<model>/<cond>/<Q>.{md,json,log}.
Existing GOOD answers are skipped; only missing/failed ones are (re)run.
Progress is appended to par_run.log and a live counter to par_run_status.json.
"""
import csv
import concurrent.futures as cf
import datetime
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import threading
import time

HERE = "/Users/wgu/Desktop/MedCP/benchmarks/clinical-questions"
SD = "/private/tmp/claude-501/-Users-wgu-Desktop-MedCP/0542bef6-1d5e-4b20-b3f1-0a4370d30bdd/scratchpad"
sys.path.insert(0, SD)
import needs_rerun as NR                                   # noqa: E402

PROVIDER = {
    "gpt5.5":  ("versa_azure",   "gpt-5.5-2026-04-24"),
    "opus4.8": ("versa_bedrock", "us.anthropic.claude-opus-4-8"),
    "qwen3.6": ("ollama",        "qwen3.6:latest"),
}
MAX_TURNS = os.environ.get("MAX_TURNS", "50")
ATTEMPTS = int(os.environ.get("ATTEMPTS", "3"))
LOG = os.path.join(SD, "par_run.log")
STATUS = os.path.join(SD, "par_run_status.json")
_lk = threading.Lock()
_done = {"ok": 0, "fail": 0, "skip": 0, "total": 0, "started": time.time()}

QUESTIONS = {r["question_name"].strip(): " ".join((r["question"] or "").split())
             for r in csv.DictReader(open(os.path.join(HERE, "benchmarking_questions.csv"),
                                          encoding="utf-8"))
             if r.get("question_name", "").strip()}


def log(msg):
    line = "[%s] %s" % (time.strftime("%H:%M:%S"), msg)
    with _lk:
        with open(LOG, "a") as f:
            f.write(line + "\n")
        json.dump(_done, open(STATUS, "w"))
    print(line, flush=True)


def run_one(task):
    model, cond, q = task
    out = os.path.join(HERE, "responses", model, cond)
    os.makedirs(out, exist_ok=True)
    md, raw, lg = (os.path.join(out, q + e) for e in (".md", ".json", ".log"))

    if os.path.exists(md) and not NR.is_bad(md):
        with _lk:
            _done["skip"] += 1
        return ("skip", task)

    provider, model_id = PROVIDER[model]
    env = dict(os.environ)
    env["PATH"] = os.pathsep.join([os.path.expanduser("~/.local/bin"),
                                   os.path.expanduser("~/Desktop/BioRouter/target/release"),
                                   "/opt/homebrew/bin", "/usr/local/bin", env.get("PATH", "")])
    if cond == "withoutkg":
        env["MEDCP_DISABLE_KNOWLEDGE_GRAPH"] = "1"
    else:
        env.pop("MEDCP_DISABLE_KNOWLEDGE_GRAPH", None)

    question = QUESTIONS.get(q, "")
    start = time.time()
    for attempt in range(1, ATTEMPTS + 1):
        xdg = tempfile.mkdtemp(prefix="brxdg_")
        env["XDG_DATA_HOME"] = xdg
        name = "medcp-%s-%s-%s-%d" % (model, cond, q, random.randint(0, 10 ** 9))
        try:
            with open(raw, "w") as jf, open(lg, "w") as lf:
                subprocess.run(
                    ["biorouter", "run", "--name", name, "--quiet", "--output-format", "json",
                     "--provider", provider, "--model", model_id,
                     "--max-turns", str(MAX_TURNS), "-t", "/ext:medcp " + question],
                    stdout=jf, stderr=lf, env=env, check=False)
        finally:
            shutil.rmtree(xdg, ignore_errors=True)

        elapsed = int(time.time() - start)
        date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(md, "w") as mf:
            subprocess.run([sys.executable, os.path.join(HERE, "format_response.py"),
                            "--qname", q, "--question", question, "--elapsed", str(elapsed),
                            "--date", date, "--model", model_id, "--provider", provider,
                            "--kg", "on" if cond == "withkg" else "off", "--json", raw],
                           stdout=mf, check=False)
        reason = NR.classify(md)
        if reason is None:
            with _lk:
                _done["ok"] += 1
            log("OK   %s/%s/%s in %ds (attempt %d)" % (model, cond, q, elapsed, attempt))
            return ("ok", task)
        if attempt < ATTEMPTS:
            log("retry %s/%s/%s (%s) attempt %d/%d" % (model, cond, q, reason, attempt, ATTEMPTS))
            time.sleep(5)
    with _lk:
        _done["fail"] += 1
    log("FAIL %s/%s/%s (%s) after %d attempts" % (model, cond, q, NR.classify(md), ATTEMPTS))
    return ("fail", task)


def main():
    tasks = [tuple(t) for t in json.load(open(sys.argv[1]))]
    threads = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    _done["total"] = len(tasks)
    log("=== PAR RUN START: %d tasks, %d threads ===" % (len(tasks), threads))
    with cf.ThreadPoolExecutor(max_workers=threads) as ex:
        for _ in ex.map(run_one, tasks):
            pass
    log("=== PAR RUN DONE: ok=%d fail=%d skip=%d ===" % (_done["ok"], _done["fail"], _done["skip"]))


if __name__ == "__main__":
    main()

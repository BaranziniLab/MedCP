#!/usr/bin/env python3
"""Warm the local LLM(s) in Ollama before launching the benchmark.

The dominant cold-start cost for the local runs is loading the 20-24GB model
into memory. This preloads each model via the Ollama HTTP API with
keep_alive=-1, so it stays resident for the whole benchmark. (No EHR warmup.)

Uses only the Python standard library.

Usage (from benchmarks/clinical-questions/):
    python3 warmup.py                                  # warm the default model(s)
    python3 warmup.py --models qwen3.6:latest gemma4:latest
    python3 warmup.py --keep-alive 30m                 # or a duration instead of resident
    OLLAMA_HOST=127.0.0.1:11434 python3 warmup.py      # non-default host

The models must already be pulled into Ollama (e.g. `ollama pull qwen3.6`).
"""
import argparse
import json
import os
import sys
import time
import urllib.request

# The local benchmark models that run via the Ollama provider.
DEFAULT_MODELS = ["qwen3.6:latest"]


def ollama_base():
    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434").strip()
    if not host.startswith("http"):
        host = "http://" + host
    return host.rstrip("/")


def _keep_alive_value(s):
    return int(s) if s.lstrip("-").isdigit() else s


def list_models(base):
    try:
        with urllib.request.urlopen(base + "/api/tags", timeout=15) as r:
            return {m["name"] for m in json.load(r).get("models", [])}
    except Exception:
        return set()


def warm(model, base, keep_alive):
    payload = json.dumps({
        "model": model, "prompt": "warm up", "stream": False,
        "keep_alive": keep_alive,
    }).encode()
    req = urllib.request.Request(
        base + "/api/generate", data=payload,
        headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=1800) as r:
        json.load(r)
    return time.time() - t0


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", nargs="+", default=DEFAULT_MODELS,
                    help="Ollama model tags to preload (default: %(default)s)")
    ap.add_argument("--keep-alive", default="-1",
                    help="Ollama keep_alive: -1 = resident until stopped (default), "
                         "or a duration like 30m")
    args = ap.parse_args()

    base = ollama_base()
    keep_alive = _keep_alive_value(args.keep_alive)
    available = list_models(base)
    print(f"Warming Ollama LLM(s) at {base} (keep_alive={args.keep_alive}) ...")
    if not available:
        print("  WARNING: could not reach the Ollama API — is `ollama serve` running?",
              file=sys.stderr)

    failed = 0
    for model in args.models:
        if available and model not in available:
            print(f"  [llm] {model}: NOT pulled (available: {sorted(available)}). "
                  f"Run `ollama pull {model.split(':')[0]}`.", file=sys.stderr)
            failed += 1
            continue
        print(f"  [llm] loading {model} ... (first load of a 20-24GB model is slow)")
        try:
            dt = warm(model, base, keep_alive)
            print(f"  [llm] {model}: resident in {dt:.0f}s")
        except Exception as e:
            print(f"  [llm] {model}: FAILED: {str(e)[:160]}", file=sys.stderr)
            failed += 1

    print("Warmup complete." if not failed else f"Warmup finished with {failed} problem(s).")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Decide whether a benchmark answer must be re-run.

Two independent failure classes:

A) HARD failure - the run itself broke (empty output, Success=False, tiny file,
   biorouter/session/provider errors). These were caught during the original run.

B) EHR-ACCESS failure - the run "succeeded" (Success=True) but the model reports
   it could not answer because the clinical database timed out, refused the
   connection, or otherwise failed. `Success=True` is why the original detector
   missed these. Source of truth for the pattern: the 35 questions in
   QUERY_RERUN_FOR_TIMEOUT.csv, whose transcripts show:
       EHR QUERY TIMEOUT        16/35
       SQL SERVER GENERAL ERROR 15/35
       SQL SYNTAX ERROR         14/35
       EHR CONNECTION REFUSED    4/35
   and whose answers say "connection error" (18), "timeout" (15),
   "couldn't complete" (9), "blocked" (1).

NOTE on (B): a passing SQL error mid-transcript is NORMAL - models routinely hit
one and recover (84-96% of good runs contain one). So (B) keys off the FINAL
ANSWER admitting it could not produce the result, never off transcript errors.
"""
import os
import re

# ---------- A) hard failures ----------
HARD_ERR = re.compile(
    r"error executing tool|traceback|connection refused|not authorized|"
    r"UNIQUE constraint|not connected|no response (from|generated)|"
    r"Sensitive system operation", re.I)

# ---------- B) EHR-access failures, judged on the final answer ----------
_CANT = (r"(?:could ?n.?t|can ?not|can.?t|couldn.t|unable to|failed to|"
         r"was unable to|am unable to|blocked from|didn.?t manage to)")
_DELIVER = (r"(?:complete|determine|answer|compute|report|estimate|provide|produce|"
            r"calculate|retrieve|obtain|quantify|assess|return|finish|deliver)")
_DATA_REASON = (r"(?:connection|connect|timeout|timed out|too slow|unavailable|"
                r"backend|endpoint|database|sql|ehr|medcp|omop|server|transport closed|"
                r"data source|clinical (?:data|record))")

# Verbatim infrastructure-failure strings that only appear when the EHR broke.
INFRA_VERBATIM = re.compile(
    r"Adaptive Server (?:is unavailable|connection failed)|Transport closed|"
    r"Electronic health records error|connection (?:failed|refused|error)|"
    r"became unavailable|backend (?:is )?(?:unavailable|down|closed)", re.I)

ANSWER_FAIL = [
    re.compile(_CANT + r"\s+(?:\w+\s+){0,3}" + _DELIVER + r".{0,500}?" + _DATA_REASON,
               re.I | re.S),
    re.compile(_DATA_REASON + r".{0,400}?" + _CANT + r"\s+(?:\w+\s+){0,3}" + _DELIVER,
               re.I | re.S),
    re.compile(r"^\s*#*\s*(?:blocked|unable)\b", re.I | re.M),
    re.compile(r"\(no text response\)", re.I),
]

# The model never actually produced a result: it greeted the user, asked what to
# do, or announced its plan and then the response ended.
NON_ANSWER = [
    re.compile(r"what would you like (?:to|me to)", re.I),
    re.compile(r"how (?:can|may) I (?:help|assist)", re.I),
    re.compile(r"(?:reached (?:my|the) action limit|action limit for this turn)", re.I),
    re.compile(r"response (?:got|was) cut off", re.I),
]


def _answer(md_text):
    m = re.search(r"## Agent's Response\s*\n(.*?)\n---", md_text, re.S)
    a = m.group(1) if m else md_text
    # normalise smart quotes/dashes so plain-ASCII patterns match
    return (a.replace("’", "'").replace("‘", "'")
             .replace("“", '"').replace("”", '"'))


def _is_truncated(ans):
    """Model announced intent but the answer ends without delivering a result."""
    s = ans.strip()
    if len(s) > 1500:
        return False                     # long answers carry real content
    tail = s[-1:]
    intent = re.search(r"\b(?:let me|I(?:'| a)?ll|I will|first,? (?:let|I))\b", s, re.I)
    return bool(intent) and tail in (":", ",") or (bool(intent) and len(s) < 400)


def classify(md_path):
    """Return None if fine, else a short reason string."""
    try:
        size = os.path.getsize(md_path)
    except OSError:
        return "missing"
    if size < 900:
        return "hard:tiny"
    txt = open(md_path, encoding="utf-8", errors="replace").read()
    if "**Success** | False" in txt:
        return "hard:success-false"
    if "(no text response)" in txt:
        return "hard:empty"
    if HARD_ERR.search(txt):
        return "hard:error-marker"
    m = re.search(r"Tool Calls\*\* \| (\d+)", txt)
    if m and int(m.group(1)) == 0:
        return "hard:zero-tools"
    ans = _answer(txt)
    for rx in ANSWER_FAIL:
        if rx.search(ans):
            return "ehr:access-failure"
    # infra strings quoted verbatim in the answer, alongside an inability cue
    if INFRA_VERBATIM.search(ans) and re.search(_CANT + r"|\bblocked\b|\bno (?:cohort|data|counts)\b",
                                                ans, re.I):
        return "ehr:access-failure"
    for rx in NON_ANSWER:
        if rx.search(ans):
            return "nonanswer:no-result"
    if _is_truncated(ans):
        return "nonanswer:truncated"
    return None


def is_bad(md_path):
    return classify(md_path) is not None

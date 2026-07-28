#!/usr/bin/env python3
"""Study B — Atrial fibrillation and the anticoagulation gap.

Original observational study on the synthetic, date-shifted MIMIC-IV/OMOP demo
served through MedCP. Loads only the CSV/JSON files extracted via the harness
(data/*.csv, kg/*.json) and computes the descriptive + univariate statistics,
effect sizes with 95% CI, and the minimum detectable effect for the primary
contrast (in-hospital death, heparin vs no-heparin). No raw DB access here.

Run:
  uv run --with pandas --with scipy python study-B/analysis.py
"""
import json
import math
import os

import numpy as np
import pandas as pd
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
KG = os.path.join(HERE, "kg")
rng = np.random.default_rng(20260723)

# ----------------------------------------------------------------------------
# Load EHR extractions
# ----------------------------------------------------------------------------
cohort = pd.read_csv(os.path.join(DATA, "af_cohort.csv"))
hr = pd.read_csv(os.path.join(DATA, "af_heart_rate.csv"))

# Per-patient median heart rate (bpm), merged into the cohort
hr_med = hr.groupby("person_id")["value_as_number"].median().rename("hr_median")
cohort = cohort.merge(hr_med, on="person_id", how="left")

assert len(cohort) == 23, f"expected 23 AF patients, got {len(cohort)}"
grp = {1: cohort[cohort.heparin == 1], 0: cohort[cohort.heparin == 0]}
n_hep, n_no = len(grp[1]), len(grp[0])
print(f"AF patients: {len(cohort)}  |  on heparin: {n_hep}  |  no heparin (gap): {n_no}")
assert (n_hep, n_no) == (15, 8), "grounding mismatch"


def describe(col, g):
    s = g[col].dropna()
    return dict(n=int(s.size), median=float(s.median()),
                q1=float(s.quantile(.25)), q3=float(s.quantile(.75)),
                mean=float(s.mean()))


# ----------------------------------------------------------------------------
# Helpers: proportion CIs, effect sizes, power
# ----------------------------------------------------------------------------
def wilson(k, n, z=1.959964):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def newcombe_diff(k1, n1, k2, n2, z=1.959964):
    """Newcombe method 10 CI for p1 - p2."""
    p1, p2 = k1 / n1, k2 / n2
    l1, u1 = wilson(k1, n1, z)
    l2, u2 = wilson(k2, n2, z)
    lo = (p1 - p2) - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2)
    hi = (p1 - p2) + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)
    return (lo, hi)


def or_woolf(a, b, c, d):
    """Odds ratio with Haldane-Anscombe 0.5 correction + Woolf 95% CI.
    Table: exposed=heparin. a=hep&event, b=hep&noevent, c=nohep&event, d=nohep&noevent."""
    a2, b2, c2, d2 = a + .5, b + .5, c + .5, d + .5
    orr = (a2 * d2) / (b2 * c2)
    se = math.sqrt(1/a2 + 1/b2 + 1/c2 + 1/d2)
    lo = math.exp(math.log(orr) - 1.959964 * se)
    hi = math.exp(math.log(orr) + 1.959964 * se)
    return orr, lo, hi


def power_two_prop(p1, p2, n1, n2, alpha=0.05):
    """Two-sided normal-approx power for two independent proportions."""
    pbar = (p1 * n1 + p2 * n2) / (n1 + n2)
    za = stats.norm.ppf(1 - alpha / 2)
    se0 = math.sqrt(pbar * (1 - pbar) * (1 / n1 + 1 / n2))
    se1 = math.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
    if se1 == 0:
        return float("nan")
    z = (abs(p1 - p2) - za * se0) / se1
    return stats.norm.cdf(z)


def mde_two_prop(p_ref, n1, n2, alpha=0.05, target=0.80):
    """Smallest |p1 - p_ref| detectable at `target` power, searched both directions."""
    best = None
    for direction in (+1, -1):
        for step in np.linspace(0, 1, 2001):
            p1 = p_ref + direction * step
            if p1 < 0 or p1 > 1:
                break
            if power_two_prop(p1, p_ref, n1, n2, alpha) >= target:
                d = abs(p1 - p_ref)
                best = d if best is None else min(best, d)
                break
    return best


def rank_biserial(x, y):
    """Rank-biserial correlation from Mann-Whitney U (effect size)."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    U, p = stats.mannwhitneyu(x, y, alternative="two-sided")
    r = 1 - 2 * U / (len(x) * len(y))  # in [-1, 1]
    return U, p, r


def boot_median_diff(x, y, B=10000):
    x, y = np.asarray(x, float), np.asarray(y, float)
    diffs = np.empty(B)
    for i in range(B):
        diffs[i] = (np.median(rng.choice(x, x.size)) -
                    np.median(rng.choice(y, y.size)))
    return float(np.median(x) - np.median(y)), tuple(np.percentile(diffs, [2.5, 97.5]))


res = {}

# ----------------------------------------------------------------------------
# Baseline description
# ----------------------------------------------------------------------------
res["n"] = dict(total=len(cohort), heparin=n_hep, no_heparin=n_no,
                gap_pct=100 * n_no / len(cohort))

# Sex (female counts) -- Fisher
f_hep = int((grp[1].sex == "F").sum())
f_no = int((grp[0].sex == "F").sum())
sex_tab = [[f_hep, n_hep - f_hep], [f_no, n_no - f_no]]
_, sex_p = stats.fisher_exact(sex_tab)
res["sex"] = dict(hep_F=f_hep, hep_M=n_hep - f_hep, no_F=f_no, no_M=n_no - f_no,
                  hep_F_pct=100 * f_hep / n_hep, no_F_pct=100 * f_no / n_no,
                  fisher_p=sex_p)

# Age (Mann-Whitney)
age_hep, age_no = grp[1]["age_at_af"].dropna(), grp[0]["age_at_af"].dropna()
U_age, p_age, rb_age = rank_biserial(age_hep, age_no)
hl_age, ci_age = boot_median_diff(age_hep, age_no)
res["age"] = dict(hep=describe("age_at_af", grp[1]), no=describe("age_at_af", grp[0]),
                  U=U_age, p=p_age, rank_biserial=rb_age,
                  median_diff=hl_age, ci=ci_age)

# Heart rate (Mann-Whitney)
hr_hep, hr_no = grp[1]["hr_median"].dropna(), grp[0]["hr_median"].dropna()
U_hr, p_hr, rb_hr = rank_biserial(hr_hep, hr_no)
hl_hr, ci_hr = boot_median_diff(hr_hep, hr_no)
res["hr"] = dict(hep=describe("hr_median", grp[1]), no=describe("hr_median", grp[0]),
                 U=U_hr, p=p_hr, rank_biserial=rb_hr,
                 median_diff=hl_hr, ci=ci_hr)

# ----------------------------------------------------------------------------
# PRIMARY CONTRAST: in-hospital death, heparin vs no-heparin
# ----------------------------------------------------------------------------
d_hep = int(grp[1].died.sum())
d_no = int(grp[0].died.sum())
p_hep_d, p_no_d = d_hep / n_hep, d_no / n_no
# table for OR (exposed = heparin): a=hep died, b=hep survived, c=nohep died, d=nohep survived
a, b, c, d = d_hep, n_hep - d_hep, d_no, n_no - d_no
or_est, or_lo, or_hi = or_woolf(a, b, c, d)
_, fisher_p = stats.fisher_exact([[a, b], [c, d]])
rd = p_hep_d - p_no_d
rd_lo, rd_hi = newcombe_diff(d_hep, n_hep, d_no, n_no)
rr = p_hep_d / p_no_d if p_no_d > 0 else float("inf")
# MDE for primary contrast, anchoring reference at observed no-heparin risk
mde = mde_two_prop(p_no_d, n_hep, n_no)
obs_power = power_two_prop(p_hep_d, p_no_d, n_hep, n_no)
res["death"] = dict(
    hep_deaths=d_hep, hep_n=n_hep, hep_pct=100 * p_hep_d,
    no_deaths=d_no, no_n=n_no, no_pct=100 * p_no_d,
    hep_ci=[100 * x for x in wilson(d_hep, n_hep)],
    no_ci=[100 * x for x in wilson(d_no, n_no)],
    risk_diff=100 * rd, rd_ci=[100 * rd_lo, 100 * rd_hi],
    risk_ratio=rr, odds_ratio=or_est, or_ci=[or_lo, or_hi],
    fisher_p=fisher_p, mde_abs=100 * mde if mde else None,
    observed_power=obs_power)

# Overall AF mortality
res["overall_mortality"] = dict(deaths=int(cohort.died.sum()), n=len(cohort),
                                pct=100 * cohort.died.mean())

# ----------------------------------------------------------------------------
# SPOKE knowledge-graph layer
# ----------------------------------------------------------------------------
af_tx = [x["compound"] for x in json.load(open(os.path.join(KG, "af_treatments.json")))]
shared = json.load(open(os.path.join(KG, "af_stroke_shared_genes.json")))
gene_counts = json.load(open(os.path.join(KG, "gene_counts.json")))[0]
n_tx = json.load(open(os.path.join(KG, "af_treatment_count.json")))[0]["n_af_treatments"]

# Classify anticoagulants among AF treatments (by known ingredient names)
anticoag_map = {
    "Vitamin K antagonist (oral)": ["warfarin", "acenocoumarol", "tecarfarin"],
    "Direct oral anticoagulant / Xa/IIa inhibitor (oral)":
        ["apixaban", "rivaroxaban", "edoxaban", "betrixaban", "darexaban",
         "dabigatran", "ximelagatran", "atecegatran", "milvexian"],
    "Parenteral heparin / LMWH / pentasaccharide":
        ["heparin", "enoxaparin", "certoparin", "heparin pentasaccharide"],
    "Factor XI inhibitor (investigational)": ["abelacimab", "milvexian"],
}
low = [c.lower() for c in af_tx]
found = {}
for cls, keys in anticoag_map.items():
    hits = sorted({af_tx[i] for i, name in enumerate(low)
                   for k in keys if k in name})
    if hits:
        found[cls] = hits

# Which anticoagulant *classes* have any EHR representation? (only IV heparin)
ehr_anticoag = ["Unfractionated heparin (IV, parenteral)"]

res["spoke"] = dict(
    n_af_treatments=n_tx,
    af_genes=gene_counts["af_genes"], stroke_genes=gene_counts["stroke_genes"],
    shared_genes=[g["gene"] for g in shared],
    n_shared=len(shared),
    shared_pct_of_stroke=100 * len(shared) / gene_counts["stroke_genes"],
    anticoag_classes=found,
    n_anticoag_compounds=sum(len(v) for v in found.values()),
    ehr_anticoag=ehr_anticoag)

# ----------------------------------------------------------------------------
# Emit
# ----------------------------------------------------------------------------
out = os.path.join(DATA, "results.json")
json.dump(res, open(out, "w"), indent=2, default=float)
print(f"\nwrote {out}")
print("\n=== PRIMARY: in-hospital death (heparin vs no-heparin) ===")
print(f"  heparin : {d_hep}/{n_hep} = {100*p_hep_d:.1f}%  (95% CI {res['death']['hep_ci'][0]:.1f}-{res['death']['hep_ci'][1]:.1f})")
print(f"  no-hep  : {d_no}/{n_no} = {100*p_no_d:.1f}%  (95% CI {res['death']['no_ci'][0]:.1f}-{res['death']['no_ci'][1]:.1f})")
print(f"  risk diff = {100*rd:+.1f} pp  (95% CI {100*rd_lo:.1f} to {100*rd_hi:.1f})")
print(f"  odds ratio = {or_est:.2f}  (95% CI {or_lo:.2f}-{or_hi:.2f}); Fisher p={fisher_p:.3f}")
print(f"  MDE (abs risk diff, 80% power) = {100*mde:.1f} pp ; observed power = {obs_power:.2f}")
print("\n=== Age ===")
print(f"  hep median {res['age']['hep']['median']:.0f} [{res['age']['hep']['q1']:.0f}-{res['age']['hep']['q3']:.0f}] "
      f"vs no {res['age']['no']['median']:.0f} [{res['age']['no']['q1']:.0f}-{res['age']['no']['q3']:.0f}] ; MWU p={p_age:.3f}")
print("=== Heart rate ===")
print(f"  hep median {res['hr']['hep']['median']:.0f} [{res['hr']['hep']['q1']:.0f}-{res['hr']['hep']['q3']:.0f}] "
      f"vs no {res['hr']['no']['median']:.0f} [{res['hr']['no']['q1']:.0f}-{res['hr']['no']['q3']:.0f}] ; MWU p={p_hr:.3f}")
print("=== Sex (female) ===")
print(f"  hep {f_hep}/{n_hep} vs no {f_no}/{n_no} ; Fisher p={sex_p:.3f}")
print("\n=== SPOKE ===")
print(f"  AF-treatment compounds: {n_tx}; anticoagulant compounds identified: {res['spoke']['n_anticoag_compounds']}")
for cls, hits in found.items():
    print(f"    - {cls}: {len(hits)}")
print(f"  AF genes {gene_counts['af_genes']}, stroke genes {gene_counts['stroke_genes']}, shared {len(shared)}: "
      f"{', '.join(g['gene'] for g in shared)}")

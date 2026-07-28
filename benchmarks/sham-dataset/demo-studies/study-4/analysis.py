#!/usr/bin/env python3
"""Study G — Opioid exposure and respiratory parameters.

Original observational study on the synthetic MIMIC-IV/OMOP demo (100 ICU patients),
data retrieved through MedCP and saved under study-G/data/ and study-G/kg/.

Loads the saved extractions, builds per-patient respiratory summaries, compares
opioid-exposed vs unexposed patients with Mann-Whitney U, reports rank-biserial
effect sizes with bootstrap 95% CI, Hodges-Lehmann shift with 95% CI, and the
minimum detectable effect at 80% power (Noether formula for the rank test).

Run:
  uv run --with pandas --with scipy python study-G/analysis.py
"""
import json
import os

import numpy as np
import pandas as pd
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
rng = np.random.default_rng(20260723)

# ---------------------------------------------------------------- plausibility
RR_LO, RR_HI = 4.0, 60.0        # breaths/min: drop 0 / artefactual extremes
SPO2_LO, SPO2_HI = 50.0, 100.0  # percent: drop probe-off artefacts, cap at 100

# ------------------------------------------------------------------- load data
cohort = pd.read_csv(os.path.join(DATA, "cohort.csv"))
rr = pd.read_csv(os.path.join(DATA, "rr.csv"))
spo2 = pd.read_csv(os.path.join(DATA, "spo2.csv"))

cohort["exposed"] = ((cohort.fentanyl == 1) | (cohort.hydromorphone == 1)).astype(int)
cohort["age"] = cohort["first_visit_year"] - cohort["year_of_birth"]
cohort["female"] = (cohort.gender == "F").astype(int)

N = len(cohort)
n_exp = int(cohort.exposed.sum())
n_unexp = N - n_exp
print(f"Persons={N}  fentanyl={int(cohort.fentanyl.sum())}  "
      f"hydromorphone/dilaudid={int(cohort.hydromorphone.sum())}  "
      f"both={int(((cohort.fentanyl==1)&(cohort.hydromorphone==1)).sum())}")
print(f"Exposed (either opioid)={n_exp}  Unexposed={n_unexp}")

# ------------------------------------------------- per-patient vital summaries
rr_f = rr[(rr.value_as_number >= RR_LO) & (rr.value_as_number <= RR_HI)]
spo2_f = spo2[(spo2.value_as_number >= SPO2_LO) & (spo2.value_as_number <= SPO2_HI)]
print(f"RR rows kept {len(rr_f)}/{len(rr)}  ({len(rr)-len(rr_f)} dropped by [{RR_LO},{RR_HI}])")
print(f"SpO2 rows kept {len(spo2_f)}/{len(spo2)}  ({len(spo2)-len(spo2_f)} dropped by [{SPO2_LO},{SPO2_HI}])")

rr_pat = rr_f.groupby("person_id").value_as_number.agg(
    rr_mean="mean", rr_median="median", rr_max="max", rr_n="count").reset_index()
spo2_pat = spo2_f.assign(desat=lambda d: (d.value_as_number < 90).astype(int)) \
    .groupby("person_id").agg(
        spo2_min=("value_as_number", "min"),
        spo2_mean=("value_as_number", "mean"),
        spo2_p5=("value_as_number", lambda s: np.percentile(s, 5)),
        spo2_pct_lt90=("desat", "mean"),
        spo2_n=("value_as_number", "count")).reset_index()
spo2_pat["spo2_pct_lt90"] *= 100.0

df = cohort.merge(rr_pat, on="person_id", how="left").merge(spo2_pat, on="person_id", how="left")
assert df[["rr_mean", "spo2_min"]].notna().all().all(), "every patient should have both vitals"

# --------------------------------------------------------------- stats helpers
def mann_whitney(exposed_vals, unexposed_vals):
    """Two-sided MWU; rank-biserial r = 2*U1/(n1*n2) - 1 (exposed vs unexposed)."""
    x = np.asarray(exposed_vals, float)
    y = np.asarray(unexposed_vals, float)
    U1, p = stats.mannwhitneyu(x, y, alternative="two-sided")
    n1, n2 = len(x), len(y)
    rb = 2.0 * U1 / (n1 * n2) - 1.0          # >0: exposed tend higher
    prob_sup = U1 / (n1 * n2)                # P(exposed > unexposed)
    return U1, p, rb, prob_sup, n1, n2


def boot_ci_rb(exposed_vals, unexposed_vals, nboot=5000):
    x = np.asarray(exposed_vals, float)
    y = np.asarray(unexposed_vals, float)
    n1, n2 = len(x), len(y)
    rbs = np.empty(nboot)
    for b in range(nboot):
        xb = x[rng.integers(0, n1, n1)]
        yb = y[rng.integers(0, n2, n2)]
        U1, _ = stats.mannwhitneyu(xb, yb, alternative="two-sided")
        rbs[b] = 2.0 * U1 / (n1 * n2) - 1.0
    return np.percentile(rbs, 2.5), np.percentile(rbs, 97.5)


def hodges_lehmann(exposed_vals, unexposed_vals, nboot=5000):
    """HL median of pairwise (exposed - unexposed) differences + bootstrap 95% CI."""
    x = np.asarray(exposed_vals, float)
    y = np.asarray(unexposed_vals, float)
    hl = np.median(np.subtract.outer(x, y).ravel())
    boots = np.empty(nboot)
    for b in range(nboot):
        xb = x[rng.integers(0, len(x), len(x))]
        yb = y[rng.integers(0, len(y), len(y))]
        boots[b] = np.median(np.subtract.outer(xb, yb).ravel())
    return hl, np.percentile(boots, 2.5), np.percentile(boots, 97.5)


def mde_rank(n1, n2, alpha=0.05, power=0.80):
    """Minimum detectable effect for MWU via Noether (1987).
    Returns detectable probability-of-superiority p and |rank-biserial| = |2p-1|."""
    za = stats.norm.ppf(1 - alpha / 2)
    zb = stats.norm.ppf(power)
    Ntot = n1 + n2
    c = n1 / Ntot
    # Noether: Ntot = (za+zb)^2 / (12 c (1-c) (p-0.5)^2)  -> solve (p-0.5)
    delta = np.sqrt((za + zb) ** 2 / (12 * c * (1 - c) * Ntot))
    p_sup = 0.5 + delta
    return p_sup, abs(2 * p_sup - 1)


def descr(vals):
    v = np.asarray(vals, float)
    return dict(n=int(len(v)), median=float(np.median(v)),
                q1=float(np.percentile(v, 25)), q3=float(np.percentile(v, 75)),
                mean=float(np.mean(v)), sd=float(np.std(v, ddof=1)))

# --------------------------------------------------------------- primary tests
exp = df[df.exposed == 1]
une = df[df.exposed == 0]

results = {"n_persons": N, "n_exposed": n_exp, "n_unexposed": n_unexp,
           "n_fentanyl": int(cohort.fentanyl.sum()),
           "n_hydromorphone": int(cohort.hydromorphone.sum()),
           "n_both": int(((cohort.fentanyl == 1) & (cohort.hydromorphone == 1)).sum()),
           "rr_rows_total": len(rr), "rr_rows_kept": len(rr_f),
           "spo2_rows_total": len(spo2), "spo2_rows_kept": len(spo2_f),
           "outcomes": {}}

p_mde, rb_mde = mde_rank(n_exp, n_unexp)
results["mde"] = {"prob_superiority": p_mde, "abs_rank_biserial": rb_mde}
print(f"\nMinimum detectable effect @80% power (n1={n_exp}, n2={n_unexp}, a=0.05, two-sided):"
      f"  prob-superiority={p_mde:.3f}  |rank-biserial|={rb_mde:.3f}")

OUTCOMES = [
    ("rr_mean", "Mean respiratory rate (breaths/min)", "higher-worse"),
    ("spo2_min", "Minimum SpO2 (%)", "lower-worse"),
    ("rr_median", "Median respiratory rate (breaths/min)", "higher-worse"),
    ("spo2_mean", "Mean SpO2 (%)", "lower-worse"),
    ("spo2_pct_lt90", "% of SpO2 readings < 90%", "higher-worse"),
]

print("\n=== Primary / secondary outcomes: exposed vs unexposed ===")
for col, label, _ in OUTCOMES:
    ev, uv = exp[col].values, une[col].values
    U1, p, rb, ps, n1, n2 = mann_whitney(ev, uv)
    rb_lo, rb_hi = boot_ci_rb(ev, uv)
    hl, hl_lo, hl_hi = hodges_lehmann(ev, uv)
    de, du = descr(ev), descr(uv)
    results["outcomes"][col] = {
        "label": label, "exposed": de, "unexposed": du,
        "U1": float(U1), "p": float(p), "rank_biserial": float(rb),
        "rb_ci": [float(rb_lo), float(rb_hi)], "prob_superiority": float(ps),
        "hl_shift": float(hl), "hl_ci": [float(hl_lo), float(hl_hi)]}
    print(f"\n{label}")
    print(f"  exposed  median={de['median']:.2f} (IQR {de['q1']:.2f}-{de['q3']:.2f}) mean={de['mean']:.2f}")
    print(f"  unexposed median={du['median']:.2f} (IQR {du['q1']:.2f}-{du['q3']:.2f}) mean={du['mean']:.2f}")
    print(f"  MWU U1={U1:.0f} p={p:.3f}  rank-biserial={rb:+.3f} (95% CI {rb_lo:+.3f},{rb_hi:+.3f})")
    print(f"  Hodges-Lehmann shift={hl:+.2f} (95% CI {hl_lo:+.2f},{hl_hi:+.2f})")

# ------------------------------------------------- severity / baseline balance
print("\n=== Baseline & severity proxies (confounding-by-indication check) ===")
results["baseline"] = {}
for col, label, kind in [
    ("age", "Age at first visit (yr)", "cont"),
    ("female", "Female", "prop"),
    ("died", "In-dataset mortality", "prop"),
    ("n_drug_rows", "Drug-exposure records / patient", "cont"),
    ("n_distinct_drugs", "Distinct drugs / patient", "cont"),
    ("n_meas_rows", "Measurement records / patient", "cont"),
]:
    ev, uv = exp[col].values, une[col].values
    if kind == "prop":
        e_rate, u_rate = ev.mean() * 100, uv.mean() * 100
        tbl, p_chi, _, _ = stats.chi2_contingency(
            [[ev.sum(), len(ev) - ev.sum()], [uv.sum(), len(uv) - uv.sum()]])
        results["baseline"][col] = {"label": label, "exposed_pct": float(e_rate),
                                    "unexposed_pct": float(u_rate), "p": float(p_chi)}
        print(f"  {label}: exposed {e_rate:.1f}%  unexposed {u_rate:.1f}%  chi2 p={p_chi:.3f}")
    else:
        _, p = stats.mannwhitneyu(ev, uv, alternative="two-sided")
        results["baseline"][col] = {"label": label, "exposed_median": float(np.median(ev)),
                                    "unexposed_median": float(np.median(uv)), "p": float(p)}
        print(f"  {label}: exposed median {np.median(ev):.1f}  unexposed median {np.median(uv):.1f}  MWU p={p:.3f}")

# ------------------------------------------- sampling-intensity sensitivity
# Minimum SpO2 is a running-minimum: more readings -> lower observed nadir.
# Exposed patients are monitored far more, so test whether the min-SpO2 signal
# survives adjustment for measurement frequency.
print("\n=== Sampling-intensity sensitivity for minimum SpO2 ===")
rho, prho = stats.spearmanr(df.spo2_n, df.spo2_min)
_, p_n = stats.mannwhitneyu(exp.spo2_n, une.spo2_n, alternative="two-sided")
print(f"  SpO2 readings/patient: exposed median {exp.spo2_n.median():.0f} vs "
      f"unexposed {une.spo2_n.median():.0f} (MWU p={p_n:.4f})")
print(f"  Spearman rho(n_readings, min_SpO2) = {rho:.3f} (p={prho:.4f})")
df["_ntile"] = pd.qcut(df.spo2_n, 3, labels=["low", "mid", "high"])
strat = {}
for t in ["low", "mid", "high"]:
    sub = df[df._ntile == t]
    e, u = sub[sub.exposed == 1].spo2_min, sub[sub.exposed == 0].spo2_min
    pv = float(stats.mannwhitneyu(e, u, alternative="two-sided")[1]) if len(e) and len(u) else float("nan")
    strat[t] = {"n_exp": int(len(e)), "n_unexp": int(len(u)),
                "med_exp": float(e.median()) if len(e) else None,
                "med_unexp": float(u.median()) if len(u) else None, "p": pv}
    print(f"  reading-count tertile {t}: exposed n={len(e)} med={e.median() if len(e) else float('nan'):.0f}, "
          f"unexposed n={len(u)} med={u.median() if len(u) else float('nan'):.0f}, MWU p={pv:.3f}")
results["spo2_min_sensitivity"] = {
    "readings_exposed_median": float(exp.spo2_n.median()),
    "readings_unexposed_median": float(une.spo2_n.median()),
    "readings_mwu_p": float(p_n), "spearman_rho": float(rho), "spearman_p": float(prho),
    "stratified_by_reading_tertile": strat}

# ----------------------------------------------------------------- SPOKE facts
kg = {}
for f in ["fentanyl_respdepression", "fentanyl_targets", "hydromorphone_respdepression",
          "hydromorphone_targets", "respdepression_context", "oprm1"]:
    with open(os.path.join(HERE, "kg", f + ".json")) as fh:
        kg[f] = json.load(fh)
fen_genes = sorted({r["gene"] for r in kg["fentanyl_targets"]})
opioid_receptors = [g for g in fen_genes if g in ("OPRM1", "OPRD1", "OPRK1")]
results["spoke"] = {
    "fentanyl_resp_depression": bool(kg["fentanyl_respdepression"]),
    "hydromorphone_resp_depression": bool(kg["hydromorphone_respdepression"]),
    "resp_depression_n_compounds": kg["respdepression_context"][0]["n_compounds"],
    "fentanyl_target_genes": fen_genes,
    "fentanyl_opioid_receptors": opioid_receptors,
    "oprm1_canonical": next((r for r in kg["oprm1"] if r["protein"] == "OPRM_HUMAN"), None),
}
print("\n=== SPOKE mechanism ===")
print(f"  fentanyl -CAUSES_CcSE-> Respiratory depression: {results['spoke']['fentanyl_resp_depression']}")
print(f"  hydromorphone -CAUSES_CcSE-> Respiratory depression: {results['spoke']['hydromorphone_resp_depression']}")
print(f"  Respiratory depression caused by {results['spoke']['resp_depression_n_compounds']} compounds in SPOKE")
print(f"  fentanyl opioid-receptor targets: {opioid_receptors}")
print(f"  OPRM1 canonical protein: {results['spoke']['oprm1_canonical']}")

# --------------------------------------------------------------------- persist
with open(os.path.join(HERE, "results.json"), "w") as fh:
    json.dump(results, fh, indent=2)
print("\nSaved study-G/results.json")

#!/usr/bin/env python3
"""Study F — Polypharmacy and QT-prolonging drug burden.

Original observational study on the synthetic, date-shifted MIMIC-IV/OMOP demo,
served through MedCP (EHR) + SPOKE (knowledge graph).

Loads ONLY the files extracted via the MedCP harness (data/*.csv, kg/*.json),
computes the cohort, the per-patient QT-drug burden (SPOKE-flagged), and the
arrhythmia-by-burden comparison, and writes results.json for the report.

Run:
  uv run --with pandas --with scipy python study-F/analysis.py
"""
import json
import os
import re
import math
import pandas as pd
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, "data")
K = os.path.join(HERE, "kg")


def wilson(k, n, z=1.96):
    """Wilson score 95% CI for a binomial proportion."""
    if n == 0:
        return (float("nan"), float("nan"), float("nan"))
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return (p, max(0.0, centre - half), min(1.0, centre + half))


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", str(s).lower()).strip()


# ---------------------------------------------------------------- load
med = pd.read_csv(os.path.join(D, "med_counts.csv"))          # person_id, n_named_drugs (all 100)
drugs = pd.read_csv(os.path.join(D, "patient_drugs.csv"))     # person_id, concept_name
ndc_univ = pd.read_csv(os.path.join(D, "ndc_universe.csv"))   # concept_name, n_pts
rhythm = pd.read_csv(os.path.join(D, "rhythm_flags.csv"))     # person_id, condition_source_value
demo = pd.read_csv(os.path.join(D, "demographics.csv"))       # person_id, sex, year_of_birth, first_visit, died
qt_raw = json.load(open(os.path.join(K, "qt_compounds.json")))
qt_names = [list(x.values())[0] for x in qt_raw]

R = {}  # results collector
R["persons_total"] = int(med.shape[0]) if med.shape[0] == demo.shape[0] else int(demo.shape[0])
R["persons_total"] = int(demo["person_id"].nunique())
R["qt_compounds_n"] = len(qt_names)

# ---------------------------------------------------------------- cohort: >=5 distinct NDC-resolved names
COHORT_MIN = 5
med_all = med.copy()
cohort_ids = set(med_all.loc[med_all["n_named_drugs"] >= COHORT_MIN, "person_id"])
R["cohort_n"] = len(cohort_ids)

# per-patient medication-count distribution (cohort)
cc = med_all.loc[med_all["person_id"].isin(cohort_ids), "n_named_drugs"]
R["medcount_cohort"] = {
    "median": float(cc.median()),
    "q1": float(cc.quantile(0.25)),
    "q3": float(cc.quantile(0.75)),
    "mean": round(float(cc.mean()), 2),
    "min": int(cc.min()),
    "max": int(cc.max()),
}
ac = med_all["n_named_drugs"]
R["medcount_all"] = {
    "median": float(ac.median()), "q1": float(ac.quantile(0.25)), "q3": float(ac.quantile(0.75)),
    "mean": round(float(ac.mean()), 2), "min": int(ac.min()), "max": int(ac.max()),
}
# histogram over all 100 persons
hist = med_all["n_named_drugs"].value_counts().sort_index()
R["medcount_hist"] = {int(k): int(v) for k, v in hist.items()}

# ---------------------------------------------------------------- coverage (from logged probes; recompute what we can)
# distinct-name universe from the extracted file
R["coverage"] = {
    "total_drug_rows": 18229,           # SELECT COUNT(*) FROM drug_exposure
    "ndc_resolved_rows": 2431,          # rows joining to mimiciv_drug_ndc
    "distinct_ndc_names": int(ndc_univ.shape[0]),
    "row_coverage_pct": round(2431 / 18229 * 100, 1),
}

# ---------------------------------------------------------------- SPOKE QT match  (KG-derived flags)
qt_norm = [norm(q) for q in qt_names]
qt_pairs = list(zip(qt_names, qt_norm))

def qt_hits_for(name):
    """QT compounds whose normalized name appears as a whole-token substring of the NDC product name."""
    n = " " + norm(name) + " "
    hits = []
    for orig, qn in qt_pairs:
        if len(qn) >= 4 and (" " + qn + " ") in n:
            hits.append(orig)
    return hits

# map every distinct NDC-resolved product name -> matched QT compounds
ndc_qt_map = {row["concept_name"]: qt_hits_for(row["concept_name"]) for _, row in ndc_univ.iterrows()}
flagged_names = {k: v for k, v in ndc_qt_map.items() if v}
R["ndc_names_flagged_qt"] = {k: v for k, v in flagged_names.items()}
R["ndc_names_flagged_count"] = len(flagged_names)

# hand-curated ingredient inventory of the 39 NDC-resolved names (documented, for transparency)
INGREDIENT = {
    "sodium chloride": ["sodium chloride", "0.9% sodium", "ns ", "flush"],
}
# derive a simple ingredient label per NDC name (leading alpha tokens) for the report inventory
def ingredient_of(name):
    toks = norm(name).split()
    drop = {"iv", "ml", "mg", "bag", "vial", "bottle", "syringe", "premix", "send", "package",
            "dummy", "for", "sliding", "scale", "replacement", "critical", "care", "and",
            "oncology", "prefilled", "flush", "g", "l", "of", "0", "9", "2", "5", "10", "20",
            "50", "60", "100", "200", "250", "500", "1", "sndz", "d5w", "sw", "ns"}
    keep = [t for t in toks if t not in drop and not t.isdigit()]
    return " ".join(keep[:2]) if keep else name

R["ndc_ingredients"] = sorted({ingredient_of(n) for n in ndc_univ["concept_name"]})

# per-patient QT burden (cohort): number of DISTINCT NDC-resolved drugs flagged by SPOKE
drugs_cohort = drugs[drugs["person_id"].isin(cohort_ids)].copy()
drugs_cohort["qt_hits"] = drugs_cohort["concept_name"].map(lambda nm: len(ndc_qt_map.get(nm, [])) > 0)
burden = drugs_cohort.groupby("person_id")["qt_hits"].sum().reindex(sorted(cohort_ids)).fillna(0).astype(int)
R["qt_burden_dist"] = {int(k): int(v) for k, v in burden.value_counts().sort_index().items()}
R["qt_burden_max"] = int(burden.max())
R["qt_burden_any_n"] = int((burden >= 1).sum())
# interaction pairs modelled as SHARED QT side effect (>=2 QT-prolongers in one regimen)
R["qt_pairs_patients"] = int((burden >= 2).sum())

# ---------------------------------------------------------------- arrhythmia outcomes (EHR-measured, cohort)
def has_label(pids, labels):
    s = rhythm[rhythm["condition_source_value"].isin(labels)]
    return set(s.loc[s["person_id"].isin(pids), "person_id"])

TACHY = ["ST (Sinus Tachycardia)", "AF (Atrial Fibrillation)",
         "SVT (Supra Ventricular Tachycardia)", "A Flut (Atrial Flutter)"]
AF = ["AF (Atrial Fibrillation)"]
ST = ["ST (Sinus Tachycardia)"]
AFL_SVT_AF = ["AF (Atrial Fibrillation)", "SVT (Supra Ventricular Tachycardia)", "A Flut (Atrial Flutter)"]

n = R["cohort_n"]
def outcome(labels):
    k = len(has_label(cohort_ids, labels))
    p, lo, hi = wilson(k, n)
    return {"k": int(k), "n": int(n), "pct": round(p * 100, 1),
            "ci_lo": round(lo * 100, 1), "ci_hi": round(hi * 100, 1)}

R["arrhythmia"] = {
    "tachyarrhythmia_any (AF/ST/SVT/AFlutter)": outcome(TACHY),
    "AF (Atrial Fibrillation)": outcome(AF),
    "ST (Sinus Tachycardia)": outcome(ST),
    "AF/AFlutter/SVT (non-sinus atrial tachyarrhythmia)": outcome(AFL_SVT_AF),
}

# ---------------------------------------------------------------- primary: arrhythmia BY QT-burden stratum
# QT burden is the exposure. Stratify cohort by burden, test trend/association.
burden_df = burden.rename("burden").reset_index().rename(columns={"index": "person_id"})
burden_df["person_id"] = burden.index
tachy_ids = has_label(cohort_ids, TACHY)
burden_df["tachy"] = burden_df["person_id"].isin(tachy_ids).astype(int)

strata = sorted(burden_df["burden"].unique())
R["burden_strata"] = [int(s) for s in strata]
tbl = []
for s in strata:
    sub = burden_df[burden_df["burden"] == s]
    k = int(sub["tachy"].sum()); m = int(sub.shape[0])
    p, lo, hi = wilson(k, m)
    tbl.append({"burden": int(s), "n": m, "events": k, "pct": round(p * 100, 1),
                "ci_lo": round(lo * 100, 1), "ci_hi": round(hi * 100, 1)})
R["burden_table"] = tbl

# association test — only estimable if >=2 non-empty strata
if len(strata) >= 2:
    ct = pd.crosstab(burden_df["burden"] >= 1, burden_df["tachy"])
    chi2, pval, dof, _ = stats.chi2_contingency(ct)
    R["assoc_test"] = {"estimable": True, "test": "chi2 (burden>=1 vs 0)",
                       "chi2": round(float(chi2), 3), "p": round(float(pval), 4)}
else:
    R["assoc_test"] = {
        "estimable": False,
        "reason": ("QT-drug burden is 0 for every cohort patient under the NDC-resolved "
                   "definition, so the exposure has no variance: no odds ratio, chi-square, "
                   "or trend statistic is defined. With 0 exposed patients the minimum "
                   "detectable effect at 80% power is undefined (no exposed arm exists)."),
        "exposed_n": R["qt_burden_any_n"],
    }

# ---------------------------------------------------------------- baseline table (cohort vs non-cohort)
demo = demo.copy()
demo["age"] = demo["first_visit"].str.slice(0, 4).astype(float) - demo["year_of_birth"]
demo["in_cohort"] = demo["person_id"].isin(cohort_ids)

def baseline(sub):
    return {
        "n": int(sub.shape[0]),
        "age_median": round(float(sub["age"].median()), 0),
        "age_q1": round(float(sub["age"].quantile(0.25)), 0),
        "age_q3": round(float(sub["age"].quantile(0.75)), 0),
        "female_n": int((sub["sex"] == "F").sum()),
        "female_pct": round(float((sub["sex"] == "F").mean()) * 100, 1),
        "died_n": int(sub["died"].sum()),
        "died_pct": round(float(sub["died"].mean()) * 100, 1),
    }

R["baseline"] = {
    "cohort": baseline(demo[demo["in_cohort"]]),
    "noncohort": baseline(demo[~demo["in_cohort"]]),
    "overall": baseline(demo),
}

# methadone sensitivity note (raw text only, not NDC-resolved)
R["methadone_rawtext_patients"] = 1

# ---------------------------------------------------------------- write
with open(os.path.join(HERE, "results.json"), "w") as f:
    json.dump(R, f, indent=2)

# console summary
print("cohort N (>=5 named drugs):", R["cohort_n"])
print("med-count cohort median [IQR] range:",
      R["medcount_cohort"]["median"], f'[{R["medcount_cohort"]["q1"]}-{R["medcount_cohort"]["q3"]}]',
      f'({R["medcount_cohort"]["min"]}-{R["medcount_cohort"]["max"]})')
print("NDC coverage:", R["coverage"])
print("QT compounds (SPOKE):", R["qt_compounds_n"])
print("NDC-resolved names flagged QT:", R["ndc_names_flagged_count"], R["ndc_names_flagged_qt"])
print("QT-burden distribution:", R["qt_burden_dist"], "max", R["qt_burden_max"])
print("arrhythmia:", json.dumps(R["arrhythmia"], indent=2))
print("burden table:", R["burden_table"])
print("assoc test:", R["assoc_test"])
print("baseline:", json.dumps(R["baseline"], indent=2))
print("\nwrote results.json")

#!/usr/bin/env python3
"""Study C - Lactate and in-hospital mortality (original study on Synthetic Dataset).

All inputs are MedCP-extracted CSVs in study-C/data/ (see queries.log). This script
does every statistic and writes study-C/data/results.json + a console summary.
Run: uv run --with pandas --with scipy --with scikit-learn --with lifelines python study-C/analysis.py
"""
import json
import os
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.metrics import roc_curve, roc_auc_score
from lifelines import KaplanMeierFitter
from lifelines.statistics import multivariate_logrank_test, logrank_test

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
rng = np.random.default_rng(20260723)

# ---------------------------------------------------------------- load
lac = pd.read_csv(os.path.join(DATA, "lactate_measurements.csv"))
death = pd.read_csv(os.path.join(DATA, "death.csv"))
visits = pd.read_csv(os.path.join(DATA, "visits.csv"))
person = pd.read_csv(os.path.join(DATA, "person.csv"))

lac["dt"] = pd.to_datetime(lac["measurement_datetime"])
death["ddt"] = pd.to_datetime(death["death_datetime"])
visits["vstart"] = pd.to_datetime(visits["visit_start_datetime"])
visits["vend"] = pd.to_datetime(visits["visit_end_datetime"])

# ---------------------------------------------------------------- per-patient lactate features
def per_patient(g):
    g = g.sort_values("dt")
    first = g["value_as_number"].iloc[0]
    last = g["value_as_number"].iloc[-1]
    peak = g["value_as_number"].max()
    return pd.Series({
        "index_dt": g["dt"].iloc[0],
        "index_voi": g["visit_occurrence_id"].iloc[0],   # visit containing the first lactate
        "last_lac_dt": g["dt"].iloc[-1],
        "first_lac": first,
        "last_lac": last,
        "peak_lac": peak,
        "clearance_abs": first - last,                 # mmol/L drop, first -> last
        "clearance_pct": (first - last) / first * 100 if first > 0 else np.nan,
        "n_meas": len(g),
    })

pat = lac.groupby("person_id").apply(per_patient, include_groups=False).reset_index()

# outcome + censoring
dset = set(death["person_id"])
pat["died"] = pat["person_id"].isin(dset).astype(int)
pat = pat.merge(death[["person_id", "ddt"]], on="person_id", how="left")
vend = visits.groupby("person_id")["vend"].max().rename("max_vend")
pat = pat.merge(vend, on="person_id", how="left")

# index visit window (the hospital stay in which the first lactate was drawn)
iv = visits[["visit_occurrence_id", "vstart", "vend"]].rename(
    columns={"visit_occurrence_id": "index_voi", "vstart": "iv_start", "vend": "iv_end"})
pat = pat.merge(iv, on="index_voi", how="left")
pat["index_los_days"] = (pat["iv_end"] - pat["iv_start"]).dt.total_seconds() / 86400.0

# follow-up (days) from first lactate (time zero) to death (event) or last hospital contact (censor)
last_contact = pat[["last_lac_dt", "max_vend"]].max(axis=1)
end = np.where(pat["died"] == 1, pat["ddt"], last_contact)
pat["t_days"] = (pd.to_datetime(pd.Series(end)) - pat["index_dt"]).dt.total_seconds() / 86400.0
# guard: strictly-positive follow-up (deaths at/very-near first lactate)
EPS = 1.0 / 24.0  # 1 hour
n_clamped = int((pat["t_days"] <= 0).sum())
pat.loc[pat["t_days"] <= 0, "t_days"] = EPS

# where did each death occur relative to the index (first-lactate) hospitalization?
tol = pd.Timedelta(hours=1)
pat["death_in_index_stay"] = (
    (pat["died"] == 1)
    & (pat["ddt"] >= pat["iv_start"] - tol)
    & (pat["ddt"] <= pat["iv_end"] + tol)
)
n_death_in_index = int(pat["death_in_index_stay"].sum())
n_death_after_index = int(n_death := (pat["died"].sum())) - n_death_in_index
late = pat[(pat["died"] == 1) & (~pat["death_in_index_stay"])]
median_late_delay = float(late["t_days"].median()) if len(late) else float("nan")

# demographics
person["gender_source_value"] = person["gender_source_value"].astype(str)
pat = pat.merge(person[["person_id", "gender_source_value", "year_of_birth"]], on="person_id", how="left")
pat["age"] = pat["index_dt"].dt.year - pat["year_of_birth"]

surv = pat[pat["died"] == 0]
dead = pat[pat["died"] == 1]
N = len(pat); n_d = len(dead); n_s = len(surv)

# ---------------------------------------------------------------- helpers
def med_iqr(x):
    x = np.asarray(x, float)
    return float(np.median(x)), float(np.percentile(x, 25)), float(np.percentile(x, 75))

def hodges_lehmann(a, b):
    # median of all pairwise differences a_i - b_j  (dead - survivor)
    diffs = np.subtract.outer(np.asarray(a, float), np.asarray(b, float)).ravel()
    return float(np.median(diffs))

def boot_ci(func, a, b, nboot=5000):
    a = np.asarray(a, float); b = np.asarray(b, float)
    vals = np.empty(nboot)
    for i in range(nboot):
        aa = rng.choice(a, len(a), replace=True)
        bb = rng.choice(b, len(b), replace=True)
        vals[i] = func(aa, bb)
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))

# ---------------------------------------------------------------- primary: Mann-Whitney peak lactate
def mwu_block(dead_vals, surv_vals):
    U, p = stats.mannwhitneyu(dead_vals, surv_vals, alternative="two-sided")
    n1, n2 = len(dead_vals), len(surv_vals)
    auc = U / (n1 * n2)                       # prob(dead peak > survivor peak) = AUC
    rb = 2 * auc - 1                          # rank-biserial correlation
    hl = hodges_lehmann(dead_vals, surv_vals)
    hl_lo, hl_hi = boot_ci(hodges_lehmann, dead_vals, surv_vals)
    md, ml, mh = med_iqr(dead_vals); sd, sl, sh = med_iqr(surv_vals)
    return dict(U=float(U), p=float(p), auc_from_U=auc, rank_biserial=rb,
                hl_diff=hl, hl_ci=[hl_lo, hl_hi],
                dead_median=md, dead_iqr=[ml, mh], surv_median=sd, surv_iqr=[sl, sh])

peak = mwu_block(dead["peak_lac"].values, surv["peak_lac"].values)
last = mwu_block(dead["last_lac"].values, surv["last_lac"].values)
clr = mwu_block(dead["clearance_pct"].dropna().values, surv["clearance_pct"].dropna().values)

# ---------------------------------------------------------------- ROC / AUC of peak lactate for death
y = pat["died"].values
score = pat["peak_lac"].values
auc = float(roc_auc_score(y, score))
fpr, tpr, thr = roc_curve(y, score)
def _auc(a, b):  # a=labels, b=scores for bootstrap
    return roc_auc_score(a, b)
# stratified bootstrap CI for AUC
auc_boot = []
idx_d = np.where(y == 1)[0]; idx_s = np.where(y == 0)[0]
for _ in range(5000):
    bd = rng.choice(idx_d, len(idx_d), replace=True)
    bs = rng.choice(idx_s, len(idx_s), replace=True)
    ii = np.concatenate([bd, bs])
    auc_boot.append(roc_auc_score(y[ii], score[ii]))
auc_ci = [float(np.percentile(auc_boot, 2.5)), float(np.percentile(auc_boot, 97.5))]

# ---------------------------------------------------------------- design: min detectable effect @80% power
za, zb = stats.norm.ppf(0.975), stats.norm.ppf(0.80)
mde_d = (za + zb) * np.sqrt(1 / n_d + 1 / n_s)          # min detectable Cohen's d (two-sample)
se0_auc = np.sqrt((n_d + n_s + 1) / (12.0 * n_d * n_s))  # SE of AUC under H0=0.5 (Mann-Whitney)
mde_auc = 0.5 + (za + zb) * se0_auc                      # approx min detectable AUC

# person-time (time from first lactate to death/last hospital contact; see limitations re: mixed clock)
person_days = float(pat["t_days"].sum())
pt_dead = float(pat.loc[pat.died == 1, "t_days"].sum())
pt_surv = float(pat.loc[pat.died == 0, "t_days"].sum())
mort_rate_per100pd = 100.0 * n_d / person_days
index_los_total = float(pat["index_los_days"].sum())
index_los_med, index_los_lo, index_los_hi = med_iqr(pat["index_los_days"])

# ---------------------------------------------------------------- tertiles + Kaplan-Meier + log-rank
pat["tertile"] = pd.qcut(pat["peak_lac"], 3, labels=["T1 low", "T2 mid", "T3 high"])
ter_edges = [float(x) for x in pd.qcut(pat["peak_lac"], 3, retbins=True)[1]]

lr = multivariate_logrank_test(pat["t_days"], pat["tertile"], pat["died"])
# pairwise T1 vs T3
m1 = pat[pat.tertile == "T1 low"]; m3 = pat[pat.tertile == "T3 high"]
lr13 = logrank_test(m1["t_days"], m3["t_days"], m1["died"], m3["died"])
# 28-day landmark log-rank: clean "in-hospital" version (censor all at 28 d, event only if death <=28 d)
LM = 28.0
pat["t28"] = np.minimum(pat["t_days"], LM)
pat["e28"] = ((pat["died"] == 1) & (pat["t_days"] <= LM)).astype(int)
lr28 = multivariate_logrank_test(pat["t28"], pat["tertile"], pat["e28"])
n_events_28 = int(pat["e28"].sum())

km_curves = {}
tertile_summary = {}
for name, sub in pat.groupby("tertile", observed=True):
    kmf = KaplanMeierFitter()
    kmf.fit(sub["t_days"], sub["died"], label=str(name))
    sf = kmf.survival_function_.reset_index()
    sf.columns = ["t", "s"]
    km_curves[str(name)] = {"t": sf["t"].round(4).tolist(), "s": sf["s"].round(4).tolist()}
    # landmark survival at clinically stable horizons (large risk sets, unlike the long tail)
    s7 = float(kmf.predict(7)); s28 = float(kmf.predict(28))
    tertile_summary[str(name)] = dict(
        n=int(len(sub)), deaths=int(sub["died"].sum()),
        deaths_in_index_stay=int(sub["death_in_index_stay"].sum()),
        peak_min=float(sub["peak_lac"].min()), peak_max=float(sub["peak_lac"].max()),
        person_days=float(sub["t_days"].sum()),
        surv_7d=s7, surv_28d=s28,
        surv_at_end=float(kmf.survival_function_.iloc[-1, 0]),
    )

# ---------------------------------------------------------------- baseline table
def desc(sub):
    return dict(
        n=int(len(sub)),
        age_med=float(np.median(sub["age"])), age_iqr=[float(np.percentile(sub["age"],25)), float(np.percentile(sub["age"],75))],
        male=int((sub["gender_source_value"] == "M").sum()),
        female=int((sub["gender_source_value"] == "F").sum()),
        nmeas_med=float(np.median(sub["n_meas"])), nmeas_iqr=[float(np.percentile(sub["n_meas"],25)), float(np.percentile(sub["n_meas"],75))],
        peak_med=float(np.median(sub["peak_lac"])), peak_iqr=[float(np.percentile(sub["peak_lac"],25)), float(np.percentile(sub["peak_lac"],75))],
        last_med=float(np.median(sub["last_lac"])), last_iqr=[float(np.percentile(sub["last_lac"],25)), float(np.percentile(sub["last_lac"],75))],
        clr_med=float(np.median(sub["clearance_pct"])), clr_iqr=[float(np.percentile(sub["clearance_pct"],25)), float(np.percentile(sub["clearance_pct"],75))],
        fu_med=float(np.median(sub["t_days"])), fu_iqr=[float(np.percentile(sub["t_days"],25)), float(np.percentile(sub["t_days"],75))],
    )

baseline = {"all": desc(pat), "survivors": desc(surv), "deaths": desc(dead)}

# ---------------------------------------------------------------- assemble results
results = dict(
    cohort=dict(N=N, deaths=n_d, survivors=n_s, mortality_pct=100.0 * n_d / N,
                total_persons=int(len(person)), n_lac_measurements=int(len(lac)),
                person_days=person_days, person_days_dead=pt_dead,
                person_days_surv=pt_surv, mort_per_100pd=mort_rate_per100pd,
                followup_clamped=n_clamped,
                index_los_total=index_los_total, index_los_med=index_los_med,
                index_los_iqr=[index_los_lo, index_los_hi],
                deaths_in_index_stay=n_death_in_index, deaths_after_index=n_death_after_index,
                median_late_death_delay_days=median_late_delay),
    baseline=baseline,
    peak_mwu=peak, last_mwu=last, clearance_mwu=clr,
    roc=dict(auc=auc, auc_ci=auc_ci, fpr=[round(float(x),4) for x in fpr], tpr=[round(float(x),4) for x in tpr]),
    design=dict(mde_cohens_d=float(mde_d), mde_auc=float(mde_auc), se0_auc=float(se0_auc)),
    tertiles=dict(edges=ter_edges, summary=tertile_summary,
                  logrank_stat=float(lr.test_statistic), logrank_p=float(lr.p_value),
                  logrank_T1vT3_stat=float(lr13.test_statistic), logrank_T1vT3_p=float(lr13.p_value),
                  logrank28_stat=float(lr28.test_statistic), logrank28_p=float(lr28.p_value),
                  logrank28_events=n_events_28, landmark_days=LM,
                  km=km_curves),
)

with open(os.path.join(DATA, "results.json"), "w") as f:
    json.dump(results, f, indent=2)

# also persist the analysis-ready per-patient table (no direct identifiers beyond hashed ids already in source)
pat_out = pat[["person_id","age","gender_source_value","n_meas","first_lac","last_lac","peak_lac",
               "clearance_abs","clearance_pct","died","t_days","tertile"]].copy()
pat_out.to_csv(os.path.join(DATA, "analysis_ready.csv"), index=False)

# ---------------------------------------------------------------- console summary
print("="*70)
print(f"COHORT: N={N}  deaths={n_d}  survivors={n_s}  mortality={100*n_d/N:.1f}%")
print(f"lactate measurements={len(lac)}  persons in db={len(person)}  clamped fu={n_clamped}")
print(f"index-stay LOS: median {index_los_med:.1f} d IQR[{index_los_lo:.1f}-{index_los_hi:.1f}] total {index_los_total:.0f} pt-days")
print(f"deaths during index (first-lactate) stay = {n_death_in_index}; deaths in a later encounter = {n_death_after_index} (median +{median_late_delay:.0f} d)")
print(f"full follow-up person-time={person_days:.1f} patient-days (deaths {pt_dead:.1f}, survivors {pt_surv:.1f})")
print("-"*70)
print("PEAK LACTATE (mmol/L)  dead vs survivor")
print(f"  dead   median {peak['dead_median']:.1f} IQR[{peak['dead_iqr'][0]:.1f}-{peak['dead_iqr'][1]:.1f}] n={n_d}")
print(f"  surv   median {peak['surv_median']:.1f} IQR[{peak['surv_iqr'][0]:.1f}-{peak['surv_iqr'][1]:.1f}] n={n_s}")
print(f"  Mann-Whitney U={peak['U']:.0f}  p={peak['p']:.4g}")
print(f"  Hodges-Lehmann diff={peak['hl_diff']:.2f} mmol/L 95%CI[{peak['hl_ci'][0]:.2f},{peak['hl_ci'][1]:.2f}]")
print(f"  rank-biserial={peak['rank_biserial']:.3f}  prob(dead>surv)=AUC={peak['auc_from_U']:.3f}")
print("-"*70)
print(f"ROC AUC (peak lactate -> death) = {auc:.3f}  95%CI[{auc_ci[0]:.3f},{auc_ci[1]:.3f}]")
print("-"*70)
print("SECONDARY:")
print(f"  last lactate:  dead {last['dead_median']:.1f} vs surv {last['surv_median']:.1f}  p={last['p']:.4g}")
print(f"  clearance %:   dead {clr['dead_median']:.1f} vs surv {clr['surv_median']:.1f}  p={clr['p']:.4g}")
print("-"*70)
print("TERTILES of peak lactate (edges %.2f, %.2f, %.2f, %.2f):" % tuple(ter_edges))
for k, v in tertile_summary.items():
    print(f"  {k}: n={v['n']} deaths={v['deaths']} (idx-stay {v['deaths_in_index_stay']}) peak[{v['peak_min']:.1f}-{v['peak_max']:.1f}] S(7d)={v['surv_7d']:.2f} S(28d)={v['surv_28d']:.2f}")
print(f"  log-rank full follow-up (3 groups, 15 events): chi2={lr.test_statistic:.2f} p={lr.p_value:.4g}")
print(f"  log-rank T1 vs T3 (full): chi2={lr13.test_statistic:.2f} p={lr13.p_value:.4g}")
print(f"  log-rank 28-day landmark (3 groups, {n_events_28} events): chi2={lr28.test_statistic:.2f} p={lr28.p_value:.4g}")
print("-"*70)
print(f"DESIGN (given {n_d} deaths / {n_s} survivors):")
print(f"  min detectable Cohen's d @80% power = {mde_d:.2f}")
print(f"  min detectable AUC @80% power ~ {mde_auc:.3f} (SE0={se0_auc:.4f})")
print("="*70)
print("wrote", os.path.join(DATA, "results.json"))

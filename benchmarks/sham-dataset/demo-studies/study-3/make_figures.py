#!/usr/bin/env python3
"""Study 3 — publication-ready static figures (polypharmacy & QT-prolonging drug burden).

Reuses the saved analysis outputs ONLY (results.json + data/*.csv + kg/qt_compounds.json);
does not re-run any MedCP query or recompute study numbers. Emits PNG (report) + PDF + SVG
(manuscript) into study-3/figures/ via the shared Nature-style harness.

Run:
  uv run --with matplotlib --with numpy --with pandas python study-3/make_figures.py
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, "/Users/j/repos/MedCP/benchmarks/sham-dataset/studies/_harness")
from figstyle import *  # noqa: E402,F403  (apply, C, panel_label, save_pub, mm, W_DOUBLE, plt, np)

apply()

R = json.load(open(os.path.join(HERE, "results.json")))
FIGDIR = "study-3/figures"

# ---- pull the saved numbers (no recomputation) ------------------------------
hist = {int(k): int(v) for k, v in R["medcount_hist"].items()}
cohort_n = R["cohort_n"]                       # 77
excluded_n = R["persons_total"] - cohort_n     # 23
mc = R["medcount_cohort"]                       # median 9, IQR 6-11, max 17

cov = R["coverage"]
total_rows = cov["total_drug_rows"]             # 18229
res_rows = cov["ndc_resolved_rows"]             # 2431
unres_rows = total_rows - res_rows              # 15798
res_pct = cov["row_coverage_pct"]               # 13.3
unres_pct = round(100 - res_pct, 1)             # 86.7
n_ndc_names = cov["distinct_ndc_names"]         # 39

qt_ref_n = R["qt_compounds_n"]                  # 83 SPOKE QT-prolongers
qt_matched = R["ndc_names_flagged_count"]       # 0 matched in resolvable cohort drugs

arr = R["arrhythmia"]
def pull(key):
    d = arr[key]
    return d["pct"], d["ci_lo"], d["ci_hi"], d["k"], d["n"]

INK = PALETTE["ink"]


# ============================================================================
# Figure 1 — fig_coverage: (a) medication-count distribution  (b) NDC coverage
# ============================================================================
fig = plt.figure(figsize=(mm(W_DOUBLE), mm(74)))
gs = fig.add_gridspec(1, 2, width_ratios=[1.25, 1.0], wspace=0.32)
axA = fig.add_subplot(gs[0, 0])
axB = fig.add_subplot(gs[0, 1])

# ---- (a) per-patient distinct-named-medication count -----------------------
ks = sorted(hist)
vals = [hist[k] for k in ks]
cols = [C["ehr"] if k >= 5 else C["neutral"] for k in ks]
axA.bar(ks, vals, width=0.86, color=cols, edgecolor="white", linewidth=0.4, zorder=3)
axA.axvline(4.5, color=INK, lw=0.9, ls=(0, (3, 2)), zorder=4)

ymax = max(vals)
# direct group labels (no legend)
axA.text(2.5, ymax * 0.98, f"Excluded  <5\nn = {excluded_n}", ha="center", va="top",
         color=PALETTE["grey"], fontsize=6.6, linespacing=1.25)
axA.text(11.6, ymax * 1.10, f"Polypharmacy cohort  ≥5\nn = {cohort_n}", ha="center", va="top",
         color=C["ehr"], fontsize=6.6, fontweight="bold", linespacing=1.25)
axA.text(0.5, -0.30,
         f"Cohort median {mc['median']:.0f} (IQR {mc['q1']:.0f}–{mc['q3']:.0f}), "
         f"range {mc['min']}–{mc['max']}   ·   counts are a coverage-limited floor",
         transform=axA.transAxes, ha="center", va="top", fontsize=6.2, color=PALETTE["grey"])

axA.set_xlabel("Distinct NDC-resolved medications per patient")
axA.set_ylabel("Patients (n)")
axA.set_xticks(range(1, 18, 2))
axA.set_xlim(0.3, 17.7)
axA.set_ylim(0, ymax * 1.18)
axA.set_title(f"Medications per patient (n = {R['persons_total']})", pad=6)
panel_label(axA, "a")

# ---- (b) NDC name-resolution coverage: 13.3% vs 86.7% of drug rows ---------
y = 0
h = 0.5
axB.barh(y, res_pct, height=h, left=0, color=C["neutral"], edgecolor="white",
         linewidth=0.6, zorder=3)
axB.barh(y, unres_pct, height=h, left=res_pct, color=C["signal"], edgecolor="white",
         linewidth=0.6, zorder=3)

# in-/above-segment direct labels
axB.text(res_pct / 2, y - h * 0.5 - 0.06, f"resolved\n{res_pct}%\n{res_rows:,} rows",
         ha="center", va="top", fontsize=6.4, color=PALETTE["grey"], linespacing=1.3)
axB.text(res_pct + unres_pct / 2, y, f"unresolved raw NDC codes\n{unres_pct}%   ({unres_rows:,} rows)",
         ha="center", va="center", fontsize=7.0, color="white", fontweight="bold",
         linespacing=1.35)

# annotate that the QT-relevant agents hide in the unresolved 86.7%
axB.annotate(
    "QT-relevant ICU agents\n(amiodarone, ondansetron, haloperidol,\nlevofloxacin, sotalol…) "
    "live in this stratum",
    xy=(res_pct + unres_pct * 0.60, y + h * 0.5),
    xytext=(res_pct + unres_pct * 0.52, y + h * 0.5 + 0.62),
    ha="center", va="bottom", fontsize=6.3, color=C["signal"], fontweight="bold",
    linespacing=1.3,
    arrowprops=dict(arrowstyle="-|>", lw=0.8, color=C["signal"]))

axB.set_xlim(0, 100)
axB.set_ylim(-0.62, 1.15)
axB.set_yticks([])
axB.spines["left"].set_visible(False)
axB.set_xlabel("Share of drug_exposure rows (%)")
axB.set_title("NDC name-resolution coverage", pad=6)
axB.text(0.5, -0.30,
         f"n = {total_rows:,} drug rows   ·   {n_ndc_names} distinct resolved names",
         transform=axB.transAxes, ha="center", va="top", fontsize=6.2, color=PALETTE["grey"])
panel_label(axB, "b", x=-0.06)

save_pub(fig, f"{FIGDIR}/fig_coverage")


# ============================================================================
# Figure 2 — fig_qt: (a) SPOKE QT reference vs cohort match  (b) arrhythmia prev
# ============================================================================
fig = plt.figure(figsize=(mm(W_DOUBLE), mm(76)))
gs = fig.add_gridspec(1, 2, width_ratios=[0.82, 1.18], wspace=0.42)
axA = fig.add_subplot(gs[0, 0])
axB = fig.add_subplot(gs[0, 1])

# ---- (a) QT-prolongers in SPOKE (83) vs matched in resolvable drugs (0) -----
xpos = [0, 1]
bars = axA.bar(xpos, [qt_ref_n, qt_matched], width=0.62,
               color=[C["kg"], C["ehr"]], edgecolor="white", linewidth=0.5, zorder=3)
axA.text(0, qt_ref_n + 2.2, f"{qt_ref_n}", ha="center", va="bottom",
         fontsize=8.5, fontweight="bold", color=C["kg"])
# the 0 bar: explicit "0 — not estimable" marker
axA.plot([1 - 0.31, 1 + 0.31], [0, 0], color=C["ehr"], lw=2.0, zorder=4)
axA.annotate("0\nQT-burden ≡ 0\n(not estimable)", xy=(1, 0), xytext=(1, qt_ref_n * 0.42),
             ha="center", va="bottom", fontsize=6.8, fontweight="bold", color=C["signal"],
             linespacing=1.35,
             arrowprops=dict(arrowstyle="-|>", lw=0.9, color=C["signal"]))

axA.set_xticks(xpos)
axA.set_xticklabels(["SPOKE\nQT reference", f"Matched in\nresolvable\ncohort drugs\n(of {n_ndc_names})"],
                    fontsize=6.6)
axA.set_ylabel("QT-prolonging compounds (n)")
axA.set_ylim(0, qt_ref_n * 1.16)
axA.set_xlim(-0.7, 1.7)
axA.set_title("SPOKE QT-prolongers vs cohort", pad=6)
axA.text(0.5, -0.34,
         "0 of 39 NDC-resolved names is a SPOKE\nQT-prolonger → a data-coverage null, not biology",
         transform=axA.transAxes, ha="center", va="top", fontsize=6.2, color=PALETTE["grey"],
         linespacing=1.3)
panel_label(axA, "a")

# ---- (b) descriptive arrhythmia prevalence with Wilson 95% CI --------------
rows = [
    ("Any tachyarrhythmia\n(AF / ST / SVT / AFl)", "tachyarrhythmia_any (AF/ST/SVT/AFlutter)"),
    ("Sinus tachycardia (ST)", "ST (Sinus Tachycardia)"),
    ("Atrial fibrillation (AF)", "AF (Atrial Fibrillation)"),
]
ys = np.arange(len(rows))[::-1]  # first row on top
for yy, (_, key) in zip(ys, rows):
    pct, lo, hi, k, n = pull(key)
    axB.errorbar(pct, yy, xerr=[[pct - lo], [hi - pct]], fmt="none",
                 ecolor=C["ehr"], elinewidth=1.3, capsize=3, capthick=1.1, zorder=3)
    axB.scatter(pct, yy, s=42, color=C["ehr"], zorder=4, linewidths=0)
    axB.text(hi + 2.2, yy, f"{pct:.1f}%  ({lo:.1f}–{hi:.1f})   {k}/{n}",
             va="center", ha="left", fontsize=6.6, color=INK)

axB.set_yticks(ys)
axB.set_yticklabels([lbl for lbl, _ in rows], fontsize=6.8)
axB.set_xlim(0, 100)
axB.set_ylim(-0.6, len(rows) - 0.4)
axB.set_xlabel("Prevalence, % of cohort (Wilson 95% CI)")
axB.set_title(f"Rhythm-annotation prevalence (cohort n = {cohort_n})", pad=6)
axB.text(0.5, -0.30,
         "Descriptive only — exposure (QT burden) is invariant at 0,\n"
         "so this prevalence cannot be attributed to QT-drug burden",
         transform=axB.transAxes, ha="center", va="top", fontsize=6.2,
         color=C["signal"], linespacing=1.3)
panel_label(axB, "b", x=-0.30)

save_pub(fig, f"{FIGDIR}/fig_qt")

print("wrote figures to", os.path.join(HERE, "figures"))
for f in sorted(os.listdir(os.path.join(HERE, "figures"))):
    print("  ", f)

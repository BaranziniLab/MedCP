#!/usr/bin/env python3
"""Study 2 - publication-ready static figures (lactate & in-hospital mortality).

Reuses the saved analysis outputs only (data/results.json, data/analysis_ready.csv,
kg/*.json). No MedCP queries are run and no numbers are changed. Kaplan-Meier curves
and the ROC are recomputed from the saved per-patient table with lifelines/sklearn,
which reproduces the values already in results.json.

Run from the studies/ dir:
  uv run --with matplotlib --with numpy --with pandas --with scikit-learn --with lifelines \
      python study-2/make_figures.py
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "/Users/j/repos/MedCP/benchmarks/sham-dataset/studies/_harness")
from figstyle import (  # noqa: E402
    apply, C, PALETTE, panel_label, box_with_points, sig_bracket, save_pub, mm,
    W_ONEHALF, W_DOUBLE,
)

from sklearn.metrics import roc_curve, roc_auc_score  # noqa: E402
from lifelines import KaplanMeierFitter  # noqa: E402
from lifelines.statistics import multivariate_logrank_test  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
KG = os.path.join(HERE, "kg")
FIGDIR = os.path.join(HERE, "figures")

# ---------------------------------------------------------------- load saved files
with open(os.path.join(DATA, "results.json")) as f:
    R = json.load(f)
df = pd.read_csv(os.path.join(DATA, "analysis_ready.csv"))

# 28-day in-hospital landmark exactly as analysis.py defines it
LM = float(R["tertiles"]["landmark_days"])            # 28.0
df["t28"] = np.minimum(df["t_days"], LM)
df["e28"] = ((df["died"] == 1) & (df["t_days"] <= LM)).astype(int)

apply()

TERT_ORDER = ["T1 low", "T2 mid", "T3 high"]
TERT_COLOR = {"T1 low": C["survivor"], "T2 mid": PALETTE["teal"], "T3 high": C["nonsurvivor"]}
TERT_RANGE = {"T1 low": "0.7-2.3", "T2 mid": "2.4-3.2", "T3 high": "3.5-13.2"}  # mmol/L (results edges)


# ================================================================ FIG MAIN (a/b/c)
def fig_main():
    fig, axes = plt.subplots(1, 3, figsize=(mm(W_DOUBLE), mm(66)))
    ax_a, ax_b, ax_c = axes

    # ---- (a) peak lactate: survivors vs non-survivors -----------------------
    surv = df.loc[df["died"] == 0, "peak_lac"].values
    dead = df.loc[df["died"] == 1, "peak_lac"].values
    n_s, n_d = len(surv), len(dead)
    med_s, med_d = float(np.median(surv)), float(np.median(dead))
    p_peak = R["peak_mwu"]["p"]

    box_with_points(
        ax_a,
        [surv, dead],
        [f"Survivors\n(n={n_s})", f"Non-survivors\n(n={n_d})"],
        [C["survivor"], C["nonsurvivor"]],
        ylabel="Peak lactate (mmol/L)",
        seed=7,
    )
    ax_a.set_xlim(0.4, 2.8)
    ax_a.set_ylim(0, 15.5)
    # median annotations beside each box (kept off the points/whiskers)
    ax_a.text(1.34, med_s, f"med {med_s:.1f}", ha="left", va="center",
              fontsize=6.6, color=C["survivor"], fontweight="bold")
    ax_a.text(2.34, med_d, f"med {med_d:.1f}", ha="left", va="center",
              fontsize=6.6, color=C["nonsurvivor"], fontweight="bold")
    sig_bracket(ax_a, 1, 2, 14.1, f"Mann-Whitney p = {p_peak:.3f}")
    ax_a.set_title("Peak lactate by outcome")
    panel_label(ax_a, "a")

    # ---- (b) ROC of peak lactate for death ----------------------------------
    y = df["died"].values
    score = df["peak_lac"].values
    fpr, tpr, _ = roc_curve(y, score)                       # reproduces saved roc
    auc = roc_auc_score(y, score)
    lo, hi = R["roc"]["auc_ci"]

    ax_b.plot([0, 1], [0, 1], ls="--", lw=0.9, color=PALETTE["grey"], zorder=1)
    ax_b.step(fpr, tpr, where="post", lw=1.6, color=C["ehr"], zorder=3)
    ax_b.fill_between(fpr, tpr, step="post", alpha=0.10, color=C["ehr"], zorder=2)
    ax_b.set_xlim(0, 1)
    ax_b.set_ylim(0, 1.02)
    ax_b.set_xlabel("False-positive rate (1 - specificity)")
    ax_b.set_ylabel("True-positive rate (sensitivity)")
    ax_b.set_aspect("equal", adjustable="box")
    ax_b.text(0.95, 0.10, f"AUC = {auc:.2f}\n(95% CI {lo:.2f}-{hi:.2f})",
              ha="right", va="bottom", fontsize=7, color=C["ehr"], fontweight="bold")
    ax_b.text(0.62, 0.50, "chance", rotation=45, ha="center", va="center",
              fontsize=6.4, color=PALETTE["grey"])
    ax_b.text(0.02, 0.02, f"{n_d} events / {n_s} non-events", ha="left", va="bottom",
              fontsize=6.2, color=PALETTE["grey"])
    ax_b.set_title("Discrimination of peak lactate")
    panel_label(ax_b, "b")

    # ---- (c) Kaplan-Meier by peak-lactate tertile (28-day landmark) ----------
    p_lr = R["tertiles"]["logrank28_p"]
    ends = {}
    for name in TERT_ORDER:
        sub = df[df["tertile"] == name]
        kmf = KaplanMeierFitter()
        kmf.fit(sub["t28"], sub["e28"], label=name)
        sf = kmf.survival_function_
        t = sf.index.values
        s = sf[name].values
        col = TERT_COLOR[name]
        ax_c.step(t, s, where="post", lw=1.6, color=col, zorder=3)
        if t[-1] < LM:  # extend flat to the landmark
            ax_c.plot([t[-1], LM], [s[-1], s[-1]], lw=1.6, color=col, zorder=3)
        ends[name] = (float(s[-1]), int(len(sub)), int(sub["e28"].sum()))
    # direct labels (nudged so the near-flat T1/T2 curves do not collide)
    label_y = {"T1 low": 0.905, "T2 mid": 0.985, "T3 high": ends["T3 high"][0]}
    for name in TERT_ORDER:
        _, n, ev = ends[name]
        ax_c.text(LM + 0.5, label_y[name], f"{name}  n={n}, {ev} d.",
                  color=TERT_COLOR[name], fontsize=6.3, va="center", ha="left",
                  fontweight="bold")
    ax_c.set_xlim(0, LM)
    ax_c.set_ylim(0, 1.02)
    ax_c.set_xlabel("Days from first lactate (28-day landmark)")
    ax_c.set_ylabel("In-hospital survival")
    ax_c.text(0.5, 0.06, f"Log-rank p = {p_lr:.2f}", transform=ax_c.transAxes,
              ha="center", va="bottom", fontsize=7, fontweight="bold", color=PALETTE["ink"])
    ax_c.set_title("Survival by peak-lactate tertile")
    panel_label(ax_c, "c")

    out = save_pub(fig, os.path.join(FIGDIR, "fig_main"))
    return out


# ================================================================ FIG SPOKE
# Functional buckets for the lactic-acidosis gene programme (SPOKE ASSOCIATES_DaG).
# Membership is explicit so counts are reproducible from the saved JSON.
PDH_PYRUVATE = {"PDHA1", "PDHB", "DLD", "DLAT", "PC", "MPC1"}
OXPHOS = {
    # ATP synthase (complex V)
    "ATP5F1A", "ATP5F1D", "ATP5F1E", "ATP5MK", "ATP6", "ATP8", "ATPAF1", "ATPAF2",
    # cytochrome c oxidase (complex IV) + assembly
    "COX1", "COX2", "COX3", "COX10", "COX15", "COX16", "COX6B1", "COX8A", "COXFA4",
    "COA6", "COA8",
    # complex III
    "BCS1L", "CYC1", "CYTB",
    # complex I / assembly
    "ACAD9", "FOXRED1",
    # coenzyme Q biosynthesis
    "COQ2", "COQ8A", "COQ9",
}


def fig_spoke():
    # ---- load kg counts (faithful to saved JSON) ---------------------------
    with open(os.path.join(KG, "lactic_acidosis_genes.json")) as f:
        genes = {g["gene"] for g in json.load(f)}
    with open(os.path.join(KG, "lactic_acidosis_markers.json")) as f:
        genes |= {g["marker_gene"] for g in json.load(f)}   # union with PDH markers
    with open(os.path.join(KG, "sepsis_drug_classes.json")) as f:
        classes = json.load(f)

    n_pdh = len(genes & PDH_PYRUVATE)
    n_oxphos = len(genes & OXPHOS)
    n_other = len(genes) - n_pdh - n_oxphos
    n_genes = len(genes)

    fig, (axL, axR) = plt.subplots(
        1, 2, figsize=(mm(W_DOUBLE), mm(88)),
        gridspec_kw={"width_ratios": [1.15, 1.0]},
    )

    # ---- (a) sepsis therapeutic classes ------------------------------------
    classes = sorted(classes, key=lambda d: d["n_compounds"])
    names = [c["drug_class"] for c in classes]
    vals = [c["n_compounds"] for c in classes]
    ypos = np.arange(len(names))
    axL.barh(ypos, vals, color=C["kg"], alpha=0.85, height=0.72)
    for yv, v in zip(ypos, vals):
        axL.text(v + 0.15, yv, str(v), va="center", ha="left", fontsize=6.2, color=PALETTE["ink"])
    axL.set_yticks(ypos)
    axL.set_yticklabels(names, fontsize=6.0)
    axL.set_xlim(0, max(vals) + 1.4)
    axL.set_xlabel("Compounds (TREATS_CtD)")
    axL.set_title("Bacterial-sepsis therapeutic classes")
    axL.text(0.98, 0.03,
             "42 unique compounds TREAT\nbacterial sepsis (DOID:0040085);\ncompounds may span >1 class",
             transform=axL.transAxes, ha="right", va="bottom", fontsize=5.8, color=PALETTE["grey"])
    panel_label(axL, "a", x=-0.42)

    # ---- (b) lactic-acidosis gene programme by function --------------------
    glabels = ["PDH complex /\npyruvate handling", "OXPHOS\n(resp. chain + CoQ)",
               "Other mitochondrial /\nmetabolic"]
    gvals = [n_pdh, n_oxphos, n_other]
    gcolors = [PALETTE["violet"], C["kg"], PALETTE["grey_light"]]
    ypos2 = np.arange(len(glabels))[::-1]
    axR.barh(ypos2, gvals, color=gcolors, alpha=0.9, height=0.6)
    for yv, v in zip(ypos2, gvals):
        axR.text(v + 0.4, yv, str(v), va="center", ha="left", fontsize=7.5,
                 fontweight="bold", color=PALETTE["ink"])
    axR.set_yticks(ypos2)
    axR.set_yticklabels(glabels, fontsize=6.6)
    axR.set_xlim(0, max(gvals) + 4)
    axR.set_xlabel("Genes")
    axR.set_title("Lactic-acidosis gene programme")
    axR.text(0.98, 0.88,
             f"{n_genes} genes retrieved for lactic\nacidosis (DOID:3650; subset of 188\nASSOCIATES_DaG); bacterial sepsis\nreturned only 1 gene",
             transform=axR.transAxes, ha="right", va="top", fontsize=5.8, color=PALETTE["grey"])
    panel_label(axR, "b", x=-0.30)

    fig.suptitle("SPOKE-derived biological & therapeutic context", fontsize=8.5,
                 fontweight="bold", color=C["kg"], y=1.0)

    out = save_pub(fig, os.path.join(FIGDIR, "fig_spoke"))
    return out, (n_pdh, n_oxphos, n_other, n_genes)


if __name__ == "__main__":
    m = fig_main()
    s, counts = fig_spoke()
    print("fig_main  ->", m)
    print("fig_spoke ->", s)
    print("gene buckets (PDH/pyruvate, OXPHOS, other, total):", counts)

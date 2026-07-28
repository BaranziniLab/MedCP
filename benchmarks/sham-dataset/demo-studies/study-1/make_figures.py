#!/usr/bin/env python3
"""Publication-ready static matplotlib figures for Study 1
(Atrial fibrillation & the anticoagulation gap).

Numbers are read verbatim from data/results.json + kg/*.json — nothing is
re-queried or recomputed. Figures are written (PNG 300 dpi + PDF + SVG) to
study-1/figures/ via the shared Nature-style harness figstyle.save_pub.

Run:
  uv run --with matplotlib --with numpy --with pandas python study-1/make_figures.py
"""
import json
import os
import sys

sys.path.insert(0, "/Users/j/repos/MedCP/benchmarks/sham-dataset/studies/_harness")
from figstyle import (apply, C, PALETTE, mm, panel_label, save_pub,
                      W_ONEHALF, W_DOUBLE)

import numpy as np
import matplotlib.pyplot as plt  # figstyle sets Agg + rcParams on import
from matplotlib.ticker import NullFormatter

HERE = os.path.dirname(os.path.abspath(__file__))
FIGDIR = os.path.join(HERE, "figures")
res = json.load(open(os.path.join(HERE, "data", "results.json")))


def tint(hexc, f):
    """Mix a hex colour toward white; f in [0,1] (0 = original, 1 = white)."""
    hexc = hexc.lstrip("#")
    r, g, b = (int(hexc[i:i + 2], 16) for i in (0, 2, 4))
    r, g, b = (int(v + (255 - v) * f) for v in (r, g, b))
    return f"#{r:02x}{g:02x}{b:02x}"


apply()
EHR = C["ehr"]
KG = C["kg"]
EHR_LIGHT = tint(EHR, 0.60)

# ============================================================================
# FIGURE 1 — the anticoagulation gap (a) + primary death OR forest plot (b)
# ============================================================================
d = res["death"]
n = res["n"]
totals = [n["heparin"], n["no_heparin"]]                 # 15, 8
deaths = [d["hep_deaths"], d["no_deaths"]]               # 6, 3
mort = [d["hep_pct"], d["no_pct"]]                       # 40.0, 37.5

fig = plt.figure(figsize=(mm(162), mm(74)))
gs = fig.add_gridspec(1, 2, width_ratios=[1.0, 1.18], wspace=0.34)
axA = fig.add_subplot(gs[0, 0])
axB = fig.add_subplot(gs[0, 1])

# ---- (a) gap bars with in-hospital death overlaid ----
x = np.array([0, 1])
w = 0.62
axA.bar(x, totals, width=w, color=EHR_LIGHT, edgecolor=EHR, linewidth=0.9,
        label="Cohort (survived + died)", zorder=2)
axA.bar(x, deaths, width=w, color=EHR, edgecolor="none",
        label="In-hospital death", zorder=3)
for xi, t, dd, m in zip(x, totals, deaths, mort):
    axA.text(xi, t + 0.35, f"n={t}\n{dd} died · {m:.1f}%",
             ha="center", va="bottom", fontsize=6.8, linespacing=1.25)
axA.set_xticks(x)
axA.set_xticklabels(["Heparin", "No\nanticoagulant"])
axA.set_ylabel("AF patients (n)")
axA.set_ylim(0, 19)
axA.set_yticks([0, 5, 10, 15])
axA.set_title("The anticoagulation gap", pad=14)
axA.text(1, 13.2, "8/23 (34.8%)\nanticoagulation gap", ha="center", va="center",
         fontsize=6.2, color=PALETTE["grey"], style="italic", linespacing=1.25)
axA.legend(loc="upper center", bbox_to_anchor=(0.5, 1.02), ncol=2,
           fontsize=6.0, handlelength=1.0, columnspacing=1.1,
           borderaxespad=0.0, labelspacing=0.3)
panel_label(axA, "a")

# ---- (b) forest plot: death odds ratio, heparin vs no anticoagulant ----
orr = d["odds_ratio"]                 # 1.075...
lo, hi = d["or_ci"]                   # 0.202, 5.716
fp = d["fisher_p"]                    # 1.0
mde = d["mde_abs"]                    # 53.9
power = d["observed_power"]           # 0.032

axB.set_xscale("log")
axB.set_xlim(0.12, 9.0)
axB.set_ylim(-1.25, 1.25)
axB.axvline(1.0, color=C["neutral"], ls="--", lw=1.0, zorder=1)
axB.errorbar([orr], [0], xerr=[[orr - lo], [hi - orr]], fmt="s",
             color=EHR, ecolor=EHR, elinewidth=1.5, capsize=3.5,
             markersize=6.5, zorder=3)
axB.text(orr, 0.22, f"OR {orr:.2f}  (95% CI {lo:.2f}–{hi:.2f})",
         ha="center", va="bottom", fontsize=7, fontweight="bold")
axB.text(1.0, -0.42, f"Fisher exact p = {fp:.2f}", ha="center", va="top",
         fontsize=6.8, color=PALETTE["ink"])
# direction cues (no arrow glyphs, for font safety)
axB.text(0.14, -0.98, "heparin: lower death odds", ha="left", va="bottom",
         fontsize=5.8, color=PALETTE["grey"], style="italic")
axB.text(8.4, -0.98, "higher death odds", ha="right", va="bottom",
         fontsize=5.8, color=PALETTE["grey"], style="italic")
# underpowered / null note in the empty upper band
axB.text(0.5, 0.90,
         f"Null and underpowered: min. detectable Δrisk ≈ {mde:.0f} pp\n"
         f"at 80% power (observed power {power:.2f})",
         transform=axB.transAxes, ha="center", va="top", fontsize=6.0,
         style="italic", color=PALETTE["grey"], linespacing=1.3)
axB.set_yticks([])
axB.spines["left"].set_visible(False)
axB.set_xticks([0.2, 0.5, 1, 2, 5])
axB.set_xticklabels(["0.2", "0.5", "1", "2", "5"])
axB.xaxis.set_minor_formatter(NullFormatter())
axB.tick_params(axis="x", which="minor", length=0)
axB.set_xlabel("Odds ratio (log scale)")
axB.set_title("Death OR: heparin vs no anticoagulant")
panel_label(axB, "b")

save_pub(fig, os.path.join(FIGDIR, "fig_main"))

# ============================================================================
# FIGURE 2 — SPOKE contribution:
#   (a) anticoagulant classes treating AF in SPOKE vs present in the EHR
#   (b) AF and ischaemic-stroke shared genes
# ============================================================================
sp = res["spoke"]
cls = sp["anticoag_classes"]
# order top -> bottom as in the report
order = ["Vitamin K antagonist (oral)",
         "Direct oral anticoagulant / Xa/IIa inhibitor (oral)",
         "Parenteral heparin / LMWH / pentasaccharide",
         "Factor XI inhibitor (investigational)"]
labels = ["Vitamin K antagonist\n(oral)",
          "DOAC / Xa–IIa inhibitor\n(oral)",
          "Parenteral heparin /\nLMWH / pentasaccharide",
          "Factor XI inhibitor\n(investigational)"]
spoke_ct = [len(cls[k]) for k in order]            # 3, 9, 5, 2
ehr_ct = [0, 0, 1, 0]                              # only IV UFH (parenteral class)

fig2 = plt.figure(figsize=(mm(W_DOUBLE), mm(76)))
gs2 = fig2.add_gridspec(1, 2, width_ratios=[1.28, 1.0], wspace=0.5)
axS = fig2.add_subplot(gs2[0, 0])
axG = fig2.add_subplot(gs2[0, 1])

# ---- (a) grouped horizontal bars: SPOKE vs EHR ----
y = np.arange(len(labels))[::-1]
h = 0.36
axS.barh(y + h / 2, spoke_ct, height=h, color=KG, label="SPOKE — treats AF",
         zorder=3)
axS.barh(y - h / 2, ehr_ct, height=h, color=EHR, label="Present in EHR",
         zorder=3)
for yi, c in zip(y, spoke_ct):
    axS.text(c + 0.15, yi + h / 2, str(c), va="center", ha="left",
             fontsize=6.6, color=KG, fontweight="bold")
for yi, c in zip(y, ehr_ct):
    txt = "1 (IV UFH)" if c else "0"
    xpos = c + 0.15 if c else 0.15
    axS.text(xpos, yi - h / 2, txt, va="center", ha="left", fontsize=6.4,
             color=EHR)
axS.set_yticks(y)
axS.set_yticklabels(labels, fontsize=6.6)
axS.set_xlim(0, 10.4)
axS.set_xlabel("Anticoagulant compounds (n)")
axS.set_title("Anticoagulant classes for AF: SPOKE vs EHR", pad=10)
axS.text(0.98, 0.03,
         "4 anticoagulant classes in SPOKE;\n"
         "oral anticoagulation (VKA + DOAC) in EHR: 0",
         transform=axS.transAxes, ha="right", va="bottom", fontsize=6.0,
         color=PALETTE["grey"], style="italic", linespacing=1.3)
axS.legend(loc="lower right", bbox_to_anchor=(0.99, 0.18), fontsize=6.2,
           handlelength=1.1, labelspacing=0.3)
panel_label(axS, "a")

# ---- (b) shared genes: 6 of 26 stroke-associated genes overlap AF ----
n_shared = sp["n_shared"]             # 6
n_stroke = sp["stroke_genes"]         # 26
n_other = n_stroke - n_shared         # 20
n_af = sp["af_genes"]                 # 613
genes = sp["shared_genes"]

axG.barh([0], [n_shared], height=0.55, color=KG, zorder=3)
axG.barh([0], [n_other], left=n_shared, height=0.55,
         color=PALETTE["grey_light"], zorder=3)
axG.text(n_shared / 2, 0, f"{n_shared} shared\n({sp['shared_pct_of_stroke']:.0f}%)",
         ha="center", va="center", fontsize=6.6, color="white",
         fontweight="bold", linespacing=1.1)
axG.text(n_shared + n_other / 2, 0, f"{n_other} stroke-only", ha="center",
         va="center", fontsize=6.6, color=PALETTE["ink"])
axG.set_xlim(0, n_stroke)
axG.set_ylim(-1.0, 1.0)
axG.set_yticks([])
axG.spines["left"].set_visible(False)
axG.set_xticks([0, n_shared, 13, 20, n_stroke])
axG.set_xlabel("Ischaemic-stroke–associated genes (n=26)")
axG.set_title("AF / stroke shared genes (SPOKE)", pad=10)
axG.text(0.0, 0.34, "Shared genes: " + " · ".join(genes[:-1]) + " · " + genes[-1]
         + "*", transform=axG.transAxes, ha="left", va="top", fontsize=6.3,
         color=PALETTE["ink"])
axG.text(0.0, 0.21, "*ZFHX3 — canonical AF / cardioembolic-stroke locus",
         transform=axG.transAxes, ha="left", va="top", fontsize=6.0,
         color=PALETTE["grey"], style="italic")
axG.text(0.0, 0.08,
         f"AF: {n_af} genes  ·  stroke: {n_stroke} genes  ·  "
         f"{n_shared} shared ({sp['shared_pct_of_stroke']:.0f}% of stroke)",
         transform=axG.transAxes, ha="left", va="top", fontsize=6.0,
         color=PALETTE["grey"])
panel_label(axG, "b", x=-0.08, y=1.05)

save_pub(fig2, os.path.join(FIGDIR, "fig_spoke"))

print("Wrote figures to", FIGDIR)
for fn in sorted(os.listdir(FIGDIR)):
    print("  ", fn)

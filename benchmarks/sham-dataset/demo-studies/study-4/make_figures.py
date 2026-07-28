#!/usr/bin/env python3
"""Study 4 — Opioid exposure and respiratory parameters: publication figures.

Static, publication-ready matplotlib figures built from the SAVED extractions
(data/*.csv, kg/*.json) and SAVED statistics (results.json). No MedCP queries are
re-run and no numbers are changed — the per-patient summaries are recomputed from
the same CSVs with the same plausibility filters as analysis.py so the figures are
byte-faithful to the report.

Honest framing: the low SpO2 nadir in exposed patients is largely a SURVEILLANCE
artefact — the running-minimum falls as the number of readings rises (Spearman
rho = -0.66). Panel (b) is the hero panel that shows this directly.

Run:
  uv run --with matplotlib --with numpy --with pandas --with scipy python study-4/make_figures.py
"""
import json
import os
import sys

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, "/Users/j/repos/MedCP/benchmarks/sham-dataset/studies/_harness")
from figstyle import (  # noqa: E402  (sets matplotlib Agg backend on import)
    apply, C, PALETTE, W_DOUBLE, W_ONEHALF, mm, panel_label, box_with_points, sig_bracket, save_pub,
)
import matplotlib.pyplot as plt          # noqa: E402  (backend fixed by figstyle)
import matplotlib.patches as mpatches     # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
FIGS = os.path.join(HERE, "figures")

# ── plausibility filters (identical to analysis.py) ───────────────────────────
RR_LO, RR_HI = 4.0, 60.0
SPO2_LO, SPO2_HI = 50.0, 100.0

cohort = pd.read_csv(os.path.join(DATA, "cohort.csv"))
rr = pd.read_csv(os.path.join(DATA, "rr.csv"))
spo2 = pd.read_csv(os.path.join(DATA, "spo2.csv"))

cohort["exposed"] = ((cohort.fentanyl == 1) | (cohort.hydromorphone == 1)).astype(int)

rr_f = rr[(rr.value_as_number >= RR_LO) & (rr.value_as_number <= RR_HI)]
spo2_f = spo2[(spo2.value_as_number >= SPO2_LO) & (spo2.value_as_number <= SPO2_HI)]

rr_pat = rr_f.groupby("person_id").value_as_number.agg(rr_mean="mean").reset_index()
spo2_pat = spo2_f.groupby("person_id").value_as_number.agg(
    spo2_min="min", spo2_n="count").reset_index()

df = cohort.merge(rr_pat, on="person_id", how="left").merge(spo2_pat, on="person_id", how="left")

exposed = df[df.exposed == 1]
unexposed = df[df.exposed == 0]
n_exp, n_unexp = len(exposed), len(unexposed)

# saved statistics (reuse; do NOT recompute the headline numbers) ──────────────
with open(os.path.join(HERE, "results.json")) as fh:
    R = json.load(fh)
p_spo2 = R["outcomes"]["spo2_min"]["p"]            # 1.12e-4
hl_spo2 = R["outcomes"]["spo2_min"]["hl_shift"]    # -4.0
p_rr = R["outcomes"]["rr_mean"]["p"]               # 0.587
rho = R["spo2_min_sensitivity"]["spearman_rho"]    # -0.655
read_exp = R["spo2_min_sensitivity"]["readings_exposed_median"]    # 178.5
read_unexp = R["spo2_min_sensitivity"]["readings_unexposed_median"]  # 44.0

# sanity check: recomputed data reproduces the saved effect ───────────────────
_rho_chk, _ = stats.spearmanr(df.spo2_n, df.spo2_min)
assert abs(_rho_chk - rho) < 1e-9, f"data drift: {_rho_chk} vs {rho}"
assert n_exp == R["n_exposed"] and n_unexp == R["n_unexposed"]

EXP_C, UNEXP_C = C["exposed"], C["unexposed"]


# ══════════════════════════════════════════════════════════════════════════════
# Figure 1 — main (a) nadir SpO2  (b) surveillance bias  (c) respiratory rate
# ══════════════════════════════════════════════════════════════════════════════
def fig_main():
    apply()
    fig, axes = plt.subplots(1, 3, figsize=(mm(W_DOUBLE), mm(68)))
    ax_a, ax_b, ax_c = axes

    # ── (a) minimum SpO2 — exposed vs unexposed ──────────────────────────────
    ge, gu = exposed.spo2_min.values, unexposed.spo2_min.values
    box_with_points(ax_a, [ge, gu],
                    [f"Exposed\n(n={n_exp})", f"Unexposed\n(n={n_unexp})"],
                    [EXP_C, UNEXP_C], ylabel="Minimum SpO$_2$ (%)")
    ax_a.set_ylim(48, 112)
    ax_a.set_yticks([50, 60, 70, 80, 90, 100])
    sig_bracket(ax_a, 1, 2, 103, "p < 0.001   (HL −4 pts)")
    ax_a.set_title("Oxygen-saturation nadir", pad=6)
    panel_label(ax_a, "a")

    # ── (b) HERO: nadir vs number of readings (surveillance bias) ────────────
    for g, col, lab in [(exposed, EXP_C, "Exposed"), (unexposed, UNEXP_C, "Unexposed")]:
        ax_b.scatter(g.spo2_n, g.spo2_min, s=14, color=col, alpha=0.8,
                     linewidths=0.4, edgecolors="white", zorder=3, label=lab)
    ax_b.set_xscale("log")
    # visual guide: monotone trend of nadir on log(reading count)
    lx = np.log10(df.spo2_n.values)
    b1, b0 = np.polyfit(lx, df.spo2_min.values, 1)
    xs = np.linspace(df.spo2_n.min(), df.spo2_n.max(), 100)
    ax_b.plot(xs, b0 + b1 * np.log10(xs), color=PALETTE["ink"], lw=1.0, ls="--",
              alpha=0.55, zorder=2)
    ax_b.set_xlabel("SpO$_2$ readings per patient (log scale)")
    ax_b.set_ylabel("Minimum SpO$_2$ (%)")
    ax_b.set_ylim(48, 104)
    ax_b.text(0.97, 0.96, f"Spearman ρ = {rho:.2f}\n(nadir falls as\nsampling rises)",
              transform=ax_b.transAxes, ha="right", va="top", fontsize=6.6,
              color=PALETTE["ink"],
              bbox=dict(boxstyle="round,pad=0.35", fc="white", ec=PALETTE["ink"], lw=0.6,
                        alpha=0.9))
    ax_b.legend(loc="lower left", handletextpad=0.3, borderaxespad=0.3,
                labelspacing=0.25)
    ax_b.set_title("Nadir is sampling-dependent", pad=6)
    panel_label(ax_b, "b")

    # ── (c) mean respiratory rate — exposed vs unexposed (null) ──────────────
    re, ru = exposed.rr_mean.values, unexposed.rr_mean.values
    box_with_points(ax_c, [re, ru],
                    [f"Exposed\n(n={n_exp})", f"Unexposed\n(n={n_unexp})"],
                    [EXP_C, UNEXP_C], ylabel="Mean respiratory rate\n(breaths/min)")
    top = max(re.max(), ru.max())
    ax_c.set_ylim(min(re.min(), ru.min()) - 2, top + 6)
    sig_bracket(ax_c, 1, 2, top + 1.5, f"p = {p_rr:.2f}  (n.s.)")
    ax_c.set_title("Respiratory rate", pad=6)
    panel_label(ax_c, "c")

    return save_pub(fig, os.path.join(FIGS, "fig_main"))


# ══════════════════════════════════════════════════════════════════════════════
# Figure 2 — SPOKE mechanism schematic (knowledge-graph provenance)
# ══════════════════════════════════════════════════════════════════════════════
def fig_spoke():
    apply()
    kg = {}
    for f in ["fentanyl_respdepression", "hydromorphone_respdepression",
              "respdepression_context", "oprm1"]:
        with open(os.path.join(HERE, "kg", f + ".json")) as fh:
            kg[f] = json.load(fh)
    # faithful to saved kg JSON
    assert kg["fentanyl_respdepression"][0]["side_effect"] == "Respiratory depression"
    assert kg["hydromorphone_respdepression"][0]["side_effect"] == "Respiratory depression"
    n_cmpd = kg["respdepression_context"][0]["n_compounds"]           # 89
    oprm = next(r for r in kg["oprm1"] if r["protein"] == "OPRM_HUMAN")
    uniprot = oprm["uniprot"]                                          # P35372

    KG = C["kg"]
    fig, ax = plt.subplots(figsize=(mm(W_ONEHALF), mm(78)))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")

    def node(x, y, lines, fc, ec, tc, w=2.5, h=1.35, fs=7.0, weights=None):
        box = mpatches.FancyBboxPatch(
            (x - w / 2, y - h / 2), w, h,
            boxstyle="round,pad=0.06,rounding_size=0.14",
            fc=fc, ec=ec, lw=1.1, zorder=3)
        ax.add_patch(box)
        n = len(lines)
        for i, ln in enumerate(lines):
            yy = y + (h / 2 - 0.30) - i * (h - 0.55) / max(n - 1, 1) if n > 1 else y
            wt = "bold" if (weights is None and i == 0) else (weights[i] if weights else "normal")
            ax.text(x, yy, ln, ha="center", va="center", color=tc,
                    fontsize=fs if i == 0 else fs - 1.3, fontweight=wt, zorder=4)

    # coordinates
    fen = (2.0, 7.55)
    hyd = (2.0, 3.85)
    prot = (5.6, 7.95)
    gene = (8.55, 7.95)
    rdep = (6.25, 2.35)

    def arrow(p0, p1, label, lx, ly, color=KG, rad=0.0, la=None, shrink=16):
        ax.annotate("", xy=p1, xytext=p0,
                    arrowprops=dict(arrowstyle="-|>", color=color, lw=1.2,
                                    shrinkA=shrink, shrinkB=shrink,
                                    connectionstyle=f"arc3,rad={rad}"), zorder=2)
        ax.text(lx, ly, label, ha="center", va="center", fontsize=5.6,
                color=color, fontstyle="italic", rotation=(la or 0),
                bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.85),
                zorder=5)

    # BINDS edges (compound -> protein)
    arrow(fen, prot, "BINDS_CbP", 3.65, 7.95, rad=0.05, la=5)
    arrow(hyd, prot, "BINDS_CbP", 3.95, 6.15, rad=-0.09, la=42)
    # ENCODES edge (gene -> protein); short edge -> smaller shrink so it stays visible
    arrow(gene, prot, "ENCODES_GeP", 7.28, 8.38, shrink=7)
    # CAUSES edges (compound -> side effect)
    arrow(fen, rdep, "CAUSES_CcSE", 3.55, 4.85, color=C["signal"], rad=-0.05, la=-50)
    arrow(hyd, rdep, "CAUSES_CcSE", 3.95, 2.95, color=C["signal"], rad=0.03, la=-16)

    # nodes
    node(*fen, ["Fentanyl", "Compound"], "white", KG, KG, w=2.4)
    node(*hyd, ["Hydromorphone", "Compound"], "white", KG, KG, w=2.4)
    node(*prot, ["OPRM_HUMAN", f"Protein · {uniprot}"], KG, KG, "white", w=2.5)
    node(*gene, ["OPRM1", "Gene"], "white", KG, KG, w=1.7)
    node(*rdep, ["Respiratory depression", "Side effect · C0235063",
                 f"(1 of {n_cmpd} compounds)"],
         PALETTE["red_soft"], C["signal"], PALETTE["ink"], w=3.3, h=1.7)

    # bracket tying protein+gene as the mu-opioid receptor
    ax.annotate("μ-opioid receptor", xy=(6.9, 9.12), ha="center", va="bottom",
                fontsize=6.4, fontweight="bold", color=KG)
    ax.plot([4.35, 4.35, 9.4, 9.4], [8.85, 9.0, 9.0, 8.85], color=KG, lw=0.8)

    ax.set_title("SPOKE mechanism: shared μ-opioid target and respiratory-depression class effect",
                 fontsize=7.6, pad=2)
    ax.text(0.0, -0.02, "SPOKE-derived (knowledge graph) · faithful to kg/*.json",
            transform=ax.transAxes, ha="left", va="top", fontsize=6.0,
            color=KG, fontweight="bold")
    panel_label(ax, "", x=0.0, y=1.0)  # no letter (single panel)

    return save_pub(fig, os.path.join(FIGS, "fig_spoke"))


if __name__ == "__main__":
    out1 = fig_main()
    out2 = fig_spoke()
    for o in (out1, out2):
        for fmt, path in o.items():
            print(f"  wrote {path}")
    print("\nDone. Figures under study-4/figures/.")

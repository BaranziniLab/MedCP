#!/usr/bin/env python3
"""Study 5 — publication-ready STATIC figures (matplotlib only).

Rebuilds the report's figures from the ALREADY-SAVED files (no MedCP queries,
no recomputation of study numbers): the SPOKE shared-gene edges
(kg/disease_gene_edges.json), the per-disease gene counts, and the cluster
assignments / hub totals recorded in analysis_results.json.

Figures:
  fig_network  — HERO disease-disease network (nodes=diseases coloured by
                 SPOKE-derived cluster, size = total shared genes, edges =
                 shared-gene overlap). Static networkx + matplotlib.
  fig_heatmap  — disease x disease shared-gene matrix (magma), ordered by
                 cluster so the four modules read as blocks.
  fig_hubs     — horizontal bar of top hub diseases by total shared genes.

Run:
  uv run --with matplotlib --with numpy --with pandas --with networkx \
         --with scipy python study-5/make_figures.py
"""
import sys, json, itertools
from collections import defaultdict
import numpy as np
import networkx as nx

sys.path.insert(0, "/Users/j/repos/MedCP/benchmarks/sham-dataset/studies/_harness")
from figstyle import apply, PALETTE, C, save_pub, mm, W_DOUBLE, W_SINGLE, SEQ_CMAP  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402
from matplotlib.colors import LogNorm  # noqa: E402

HERE = "/Users/j/repos/MedCP/benchmarks/sham-dataset/studies/study-5"

# ── Disease registry: doid -> (full name, short label) ───────────────────────
DIS = [
    ("DOID:10825",  "Essential hypertension",       "Hypertension"),
    ("DOID:1168",   "Hyperlipidemia (unspecified)", "Hyperlipidemia"),
    ("DOID:9352",   "Type 2 diabetes mellitus",     "T2DM"),
    ("DOID:3393",   "Coronary artery disease",      "CAD"),
    ("DOID:0060224","Atrial fibrillation",          "AF"),
    ("DOID:6000",   "Congestive heart failure",     "CHF"),
    ("DOID:784",    "Chronic kidney disease",       "CKD"),
    ("DOID:3021",   "Acute kidney failure",         "AKI"),
    ("DOID:1470",   "Major depressive disorder",    "MDD"),
    ("DOID:2030",   "Anxiety disorder",             "Anxiety"),
    ("DOID:9970",   "Obesity",                      "Obesity"),
    ("DOID:1459",   "Hypothyroidism",               "Hypothyroidism"),
    ("DOID:3083",   "COPD",                         "COPD"),
    ("DOID:2841",   "Asthma",                       "Asthma"),
    ("DOID:2355",   "Anemia",                       "Anemia"),
    ("DOID:1588",   "Thrombocytopenia",             "Thrombocytopenia"),
    ("DOID:8534",   "GERD",                         "GERD"),
    ("DOID:0080784","Urinary tract infection",      "UTI"),
    ("DOID:0050742","Tobacco/nicotine dependence",  "Nicotine dep."),
]
DOIDS  = [d[0] for d in DIS]
FULL   = {d[0]: d[1] for d in DIS}
SHORT  = {d[0]: d[2] for d in DIS}
NAME2DOID = {d[1]: d[0] for d in DIS}

# ── Cluster labels + colorblind-safe PALETTE colours (blue/gold/teal/violet) ──
CLUSTERS = [
    ("cardio-renal-vascular", PALETTE["blue"]),    # community 0
    ("metabolic-endocrine",   PALETTE["gold"]),    # community 1
    ("hematologic",           PALETTE["teal"]),    # community 2
    ("neuropsychiatric",      PALETTE["violet"]),  # community 3
]
res = json.load(open(f"{HERE}/analysis_results.json"))
communities = res["network"]["communities"]           # order fixed by analysis.py
doid2cl = {}
for ci, members in enumerate(communities):
    for nm in members:
        doid2cl[NAME2DOID[nm]] = ci
CL_COLOR = {d: CLUSTERS[doid2cl[d]][1] for d in DOIDS}

# ── SPOKE shared-gene overlaps (recomputed from the SAVED edge file only) ─────
edges = json.load(open(f"{HERE}/kg/disease_gene_edges.json"))
genes = defaultdict(set)
for r in edges:
    genes[r["doid"]].add(r["gid"])

shared = {}   # frozenset(pair) -> shared gene count
jac = {}
for a, b in itertools.combinations(DOIDS, 2):
    ga, gb = genes[a], genes[b]
    s = len(ga & gb)
    u = len(ga | gb)
    shared[(a, b)] = s
    jac[(a, b)] = s / u if u else 0.0

# weighted degree = total shared genes across neighbours (== hub totals in report)
wdeg = {d: 0 for d in DOIDS}
for (a, b), s in shared.items():
    wdeg[a] += s
    wdeg[b] += s
# sanity vs recorded hub totals (T2DM 1578, obesity 1397, hypothyroidism 1148)
assert wdeg["DOID:9352"] == 1578 and wdeg["DOID:9970"] == 1397 and wdeg["DOID:1459"] == 1148

apply()

# =============================================================================
# FIG 1 — HERO disease-disease network
# =============================================================================
def fig_network():
    G = nx.Graph()
    for d in DOIDS:
        G.add_node(d)
    for (a, b), s in shared.items():
        if s > 0:
            G.add_edge(a, b, shared=s, jaccard=jac[(a, b)])

    # Cluster-seeded spring layout -> clean, reproducible module separation.
    ncl = len(CLUSTERS)
    cl_center = {ci: (np.cos(2*np.pi*ci/ncl), np.sin(2*np.pi*ci/ncl)) for ci in range(ncl)}
    rng = np.random.default_rng(7)
    init = {}
    for d in DOIDS:
        cx, cy = cl_center[doid2cl[d]]
        init[d] = (cx + rng.uniform(-0.18, 0.18), cy + rng.uniform(-0.18, 0.18))
    # layout weighted by Jaccard (normalised overlap defines the modules)
    pos = nx.spring_layout(G, pos=init, weight="jaccard", k=0.55, iterations=400, seed=7)

    fig, ax = plt.subplots(figsize=(mm(W_DOUBLE), mm(W_DOUBLE) * 0.92))

    # --- edges: two tiers to cut clutter yet anchor sparse nodes -------------
    #   faint hairline for weak overlaps (1..<20); weighted line for >=20,
    #   with width & alpha growing with the shared-gene count.
    E_THR = 20                      # "meaningful overlap" cutoff for the backbone
    ew = [(a, b, dd["shared"]) for a, b, dd in G.edges(data=True) if dd["shared"] >= E_THR]
    faint = [(a, b, dd["shared"]) for a, b, dd in G.edges(data=True) if 0 < dd["shared"] < E_THR]
    smax = max(s for *_, s in ew)
    for a, b, s in faint:           # background: keeps peripheral nodes tethered
        ax.plot([pos[a][0], pos[b][0]], [pos[a][1], pos[b][1]],
                color=PALETTE["grey_light"], lw=0.35, alpha=0.28, zorder=0)
    for a, b, s in sorted(ew, key=lambda x: x[2]):     # weak first, strong on top
        f = s / smax
        ax.plot([pos[a][0], pos[b][0]], [pos[a][1], pos[b][1]],
                color=PALETTE["grey"], lw=0.5 + 3.6 * f, alpha=0.20 + 0.55 * f,
                zorder=1, solid_capstyle="round")

    # --- nodes: size ∝ total shared genes (hubs largest) ---------------------
    wmax = max(wdeg.values())
    for d in DOIDS:
        s = 90 + 1750 * (wdeg[d] / wmax)
        ax.scatter(*pos[d], s=s, c=CL_COLOR[d], edgecolors="white",
                   linewidths=0.9, zorder=3, alpha=0.96)

    # --- direct labels: offset radially outward from graph centroid ----------
    cx0 = np.mean([p[0] for p in pos.values()])
    cy0 = np.mean([p[1] for p in pos.values()])
    for d in DOIDS:
        x, y = pos[d]
        vx, vy = x - cx0, y - cy0
        n = np.hypot(vx, vy) or 1.0
        off = 0.055 + 0.020 * (wdeg[d] / wmax)
        lx, ly = x + off * vx / n, y + off * vy / n
        ha = "left" if lx >= x else "right"
        ax.annotate(SHORT[d], (x, y), (lx, ly), fontsize=6.6, fontweight="bold",
                    ha=ha, va="center", color=PALETTE["ink"], zorder=4,
                    bbox=dict(boxstyle="round,pad=0.14", fc="white", ec="none", alpha=0.78))

    # --- cluster legend ------------------------------------------------------
    handles = [Line2D([0], [0], marker="o", linestyle="", markersize=8,
                      markerfacecolor=col, markeredgecolor="white",
                      markeredgewidth=0.6, label=lab)
               for lab, col in CLUSTERS]
    leg = ax.legend(handles=handles, title="SPOKE comorbidity cluster",
                    loc="upper left", bbox_to_anchor=(-0.02, 1.02),
                    fontsize=6.6, title_fontsize=7, handletextpad=0.4,
                    borderpad=0.5, labelspacing=0.5)
    leg.get_title().set_fontweight("bold")

    # --- size / edge reference note ------------------------------------------
    ax.text(0.995, 0.015,
            "node size = total shared genes   ·   edge width = shared genes "
            "(bold >=20, hairline <20)",
            transform=ax.transAxes, ha="right", va="bottom",
            fontsize=6, color=PALETTE["grey"])

    ax.set_axis_off()
    ax.margins(0.13)
    ax.set_facecolor("white")
    fig.patch.set_facecolor("white")
    return save_pub(fig, f"{HERE}/figures/fig_network")


# =============================================================================
# FIG 2 — disease x disease shared-gene heatmap (ordered by cluster)
# =============================================================================
def fig_heatmap():
    # order: cluster block, then by hub strength (total shared) within cluster
    order = sorted(DOIDS, key=lambda d: (doid2cl[d], -wdeg[d]))
    n = len(order)
    M = np.full((n, n), np.nan)
    for i, a in enumerate(order):
        for j, b in enumerate(order):
            if i == j:
                continue
            key = (a, b) if (a, b) in shared else (b, a)
            M[i, j] = shared[key]

    fig, ax = plt.subplots(figsize=(mm(W_DOUBLE) * 0.82, mm(W_DOUBLE) * 0.74))
    vmax = np.nanmax(M)
    im = ax.imshow(M, cmap=SEQ_CMAP, norm=LogNorm(vmin=1, vmax=vmax),
                   interpolation="nearest")
    ax.set_xticks(range(n)); ax.set_yticks(range(n))
    labels = [SHORT[d] for d in order]
    ax.set_xticklabels(labels, rotation=90, fontsize=6.2)
    ax.set_yticklabels(labels, fontsize=6.2)
    # colour tick labels by cluster to reinforce the blocks
    for tl, d in zip(ax.get_xticklabels(), order):
        tl.set_color(CL_COLOR[d]); tl.set_fontweight("bold")
    for tl, d in zip(ax.get_yticklabels(), order):
        tl.set_color(CL_COLOR[d]); tl.set_fontweight("bold")

    # cluster block separators
    bounds = []
    acc = 0
    for ci in range(len(CLUSTERS)):
        acc += sum(1 for d in order if doid2cl[d] == ci)
        bounds.append(acc)
    for b in bounds[:-1]:
        ax.axhline(b - 0.5, color="white", lw=1.4)
        ax.axvline(b - 0.5, color="white", lw=1.4)

    # annotate the two headline links
    def mark(a_name, b_name, val):
        a, b = NAME2DOID[a_name], NAME2DOID[b_name]
        i, j = order.index(a), order.index(b)
        for (r, c) in ((i, j), (j, i)):
            ax.add_patch(Rectangle((c - 0.5, r - 0.5), 1, 1, fill=False,
                                   ec=PALETTE["red"], lw=1.4, zorder=5))
        ax.text(j, i, str(val), ha="center", va="center", fontsize=6.0,
                fontweight="bold", color="white", zorder=6)
    mark("Type 2 diabetes mellitus", "Obesity", 385)
    mark("Anemia", "Thrombocytopenia", 337)

    cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.02)
    cb.set_label("shared genes (SPOKE, log scale)", fontsize=7)
    cb.ax.tick_params(labelsize=6)
    ax.set_title("Disease–disease shared-gene overlap", pad=8)
    fig.patch.set_facecolor("white")
    return save_pub(fig, f"{HERE}/figures/fig_heatmap")


# =============================================================================
# FIG 3 — hub diseases by total shared genes
# =============================================================================
def fig_hubs():
    hubs = res["network"]["hubs_by_total_shared_genes"]  # top 8, already ordered
    names = [h["name"] for h in hubs]
    vals = [h["total_shared"] for h in hubs]
    cols = [CL_COLOR[NAME2DOID[nm]] for nm in names]
    short = [SHORT[NAME2DOID[nm]] for nm in names]

    fig, ax = plt.subplots(figsize=(mm(W_SINGLE) * 1.25, mm(W_SINGLE) * 0.92))
    y = np.arange(len(names))[::-1]
    ax.barh(y, vals, color=cols, edgecolor="white", linewidth=0.5, height=0.72)
    for yi, v in zip(y, vals):
        ax.text(v + 0.01 * max(vals), yi, f"{v:,}", va="center", ha="left",
                fontsize=6.6, color=PALETTE["ink"])
    ax.set_yticks(y); ax.set_yticklabels(short, fontsize=7)
    ax.set_xlabel("total shared genes with other cohort diseases (SPOKE)")
    ax.set_xlim(0, max(vals) * 1.14)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)

    handles = [Line2D([0], [0], marker="s", linestyle="", markersize=7,
                      markerfacecolor=col, markeredgecolor="none", label=lab)
               for lab, col in CLUSTERS]
    ax.legend(handles=handles, fontsize=6.2, loc="lower right", handletextpad=0.4,
              borderpad=0.5, labelspacing=0.35)
    fig.patch.set_facecolor("white")
    return save_pub(fig, f"{HERE}/figures/fig_hubs")


if __name__ == "__main__":
    out = {}
    out["network"] = fig_network()
    out["heatmap"] = fig_heatmap()
    out["hubs"] = fig_hubs()
    print("Wrote figures:")
    for k, v in out.items():
        print(f"  {k:8s} -> {v['png']}")

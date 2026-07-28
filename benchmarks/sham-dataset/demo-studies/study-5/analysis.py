#!/usr/bin/env python3
"""Study M — Comorbidity resolved into a disease network (SPOKE).

Loads ONLY from files extracted through MedCP (data/*.csv clinical, kg/*.json SPOKE):
  1. Ranks ICD codes, describes per-patient comorbidity burden (EHR).
  2. Decodes the most frequent ICD codes -> disease names (knowledge-based proxy, documented).
  3. Uses SPOKE gene associations to build a disease-disease network via SHARED GENES (networkx).
  4. Reports resolution coverage, network size, hubs, and communities.
  5. Adds an EHR observed co-occurrence layer for contrast.

Run: uv run --with pandas --with networkx python study-M/analysis.py
"""
import json, itertools, csv
from collections import defaultdict
import pandas as pd
import networkx as nx

HERE = "study-M"

# ---------------------------------------------------------------------------
# Knowledge-based ICD decode map (skill 2D proxy). code -> disease key.
# These ICD codes carry NO human-readable name in this dataset (concept table
# holds only local mimiciv_* vocabularies; no ICD9CM/ICD10CM), so decoding is a
# documented knowledge-based mapping. ICD-9 and ICD-10 codes for the same clinical
# entity are collapsed to one disease. Each disease key was resolved to a SPOKE
# Disease node (DOID) via resolve_entity.
DISEASE = {  # key -> (display name, DOID, resolution status)
    "hypertension":   ("Essential hypertension",            "DOID:10825",  "exact"),
    "hyperlipidemia": ("Hyperlipidemia (unspecified)",      "DOID:1168",   "approximate"),
    "t2dm":           ("Type 2 diabetes mellitus",          "DOID:9352",   "exact"),
    "cad":            ("Coronary artery disease",            "DOID:3393",   "exact"),
    "af":             ("Atrial fibrillation",                "DOID:0060224","exact"),
    "chf":            ("Congestive heart failure",           "DOID:6000",   "exact"),
    "ckd":            ("Chronic kidney disease",             "DOID:784",    "exact"),
    "aki":            ("Acute kidney failure",               "DOID:3021",   "exact"),
    "mdd":            ("Major depressive disorder",          "DOID:1470",   "exact"),
    "anxiety":        ("Anxiety disorder",                   "DOID:2030",   "exact"),
    "obesity":        ("Obesity",                            "DOID:9970",   "exact"),
    "hypothyroid":    ("Hypothyroidism",                     "DOID:1459",   "exact"),
    "copd":           ("COPD",                               "DOID:3083",   "exact"),
    "asthma":         ("Asthma",                             "DOID:2841",   "exact"),
    "anemia":         ("Anemia",                             "DOID:2355",   "exact"),
    "thrombocytop":   ("Thrombocytopenia",                   "DOID:1588",   "exact"),
    "gerd":           ("GERD",                               "DOID:8534",   "exact"),
    "uti":            ("Urinary tract infection",            "DOID:0080784","exact"),
    "nicotine":       ("Tobacco/nicotine dependence",        "DOID:0050742","exact"),
}

# ICD code -> disease key (knowledge-based). ICD-9 (numeric) + ICD-10 (alpha) both mapped.
CODE2DIS = {
    # hypertension
    "4019":"hypertension", "I10":"hypertension",
    # hyperlipidemia / hypercholesterolemia
    "2724":"hyperlipidemia","E785":"hyperlipidemia","2720":"hyperlipidemia",
    "E780":"hyperlipidemia","E7800":"hyperlipidemia","E7801":"hyperlipidemia","E782":"hyperlipidemia",
    # type 2 diabetes (250.xx w/o T1 5th digit, E11.x)
    "25000":"t2dm","25002":"t2dm","E119":"t2dm","E1122":"t2dm","E1165":"t2dm","E1142":"t2dm",
    "E1152":"t2dm","E11621":"t2dm","E11649":"t2dm","E1140":"t2dm","E1121":"t2dm","E1136":"t2dm",
    "E11628":"t2dm","E11622":"t2dm","E1169":"t2dm","E1151":"t2dm","E1140x":"t2dm",
    # coronary artery disease
    "41401":"cad","41400":"cad","41402":"cad","412":"cad","I2510":"cad","I252":"cad","I2582":"cad",
    "I25110":"cad","I25118":"cad","I25119":"cad","4149":"cad","41519":"cad","4150":"cad",
    # atrial fibrillation
    "42731":"af","I4891":"af","I480":"af","I482":"af","I481":"af",
    # congestive heart failure
    "4280":"chf","42823":"chf","42833":"chf","42832":"chf","42843":"chf","42822":"chf","42821":"chf",
    "I5032":"chf","I5033":"chf","I5023":"chf","I5022":"chf","I509":"chf","I5043":"chf","I5042":"chf",
    "I5031":"chf","I5021":"chf","42830":"chf","4241":"chf",
    # chronic kidney disease (incl hypertensive CKD renal component)
    "5859":"ckd","5853":"ckd","5856":"ckd","N183":"ckd","N189":"ckd","N186":"ckd","N184":"ckd",
    "40390":"ckd","40391":"ckd","I129":"ckd","I120":"ckd","I130":"ckd","I110":"ckd","N170":"ckd",
    # acute kidney failure
    "5849":"aki","5845":"aki","N179":"aki","N170x":"aki",
    # depression / MDD
    "311":"mdd","F329":"mdd","F323":"mdd","F339":"mdd","F39":"mdd","F328":"mdd","F332":"mdd",
    # anxiety disorder
    "F419":"anxiety","30000":"anxiety","30001":"anxiety","F411":"anxiety","F410":"anxiety",
    # obesity
    "27800":"obesity","27801":"obesity","E669":"obesity","E6601":"obesity","E6609":"obesity",
    # hypothyroidism
    "E039":"hypothyroid","2449":"hypothyroid","E038":"hypothyroid","2448":"hypothyroid",
    # COPD
    "J449":"copd","496":"copd","J441":"copd","J440":"copd",
    # asthma
    "49390":"asthma","J45909":"asthma","49392":"asthma","J45901":"asthma","J45998":"asthma",
    # anemia
    "2859":"anemia","D649":"anemia","D62":"anemia","2851":"anemia","28529":"anemia","2809":"anemia",
    "2800":"anemia","28419":"anemia","2819":"anemia","2810":"anemia",
    # thrombocytopenia
    "2875":"thrombocytop","D696":"thrombocytop","D6959":"thrombocytop","28749":"thrombocytop",
    # GERD
    "53081":"gerd","K219":"gerd","K210":"gerd",
    # urinary tract infection
    "5990":"uti","N390":"uti",
    # tobacco / nicotine dependence
    "3051":"nicotine","F17210":"nicotine","F17200":"nicotine","F17211":"nicotine",
}

# ---------------------------------------------------------------------------
# 1. EHR: ICD ranking, burden, coverage
# ---------------------------------------------------------------------------
allc = pd.read_csv(f"{HERE}/data/icd_all_codes.csv", dtype={"code":str})
allc["code"] = allc["code"].str.strip()
n_distinct = len(allc)
tot_occ = int(allc["n_occ"].sum())
tot_pairs = int(allc["n_patients"].sum())  # patient-code pairs
icd9 = allc[allc["vocab"]=="ICD9"]; icd10 = allc[allc["vocab"]=="ICD10"]

burden = pd.read_csv(f"{HERE}/data/patient_burden.csv")
b = burden["n_codes"]
burden_stats = dict(n=len(b), mn=int(b.min()), q1=float(b.quantile(.25)),
                    med=float(b.median()), q3=float(b.quantile(.75)),
                    mx=int(b.max()), mean=round(float(b.mean()),1))

# coverage: which distinct codes are decoded, and what share of occ / patient-pairs
allc["disease"] = allc["code"].map(CODE2DIS)
decoded = allc[allc["disease"].notna()]
cov = dict(
    codes_decoded = int(decoded["code"].nunique()),
    codes_total = n_distinct,
    occ_decoded = int(decoded["n_occ"].sum()),
    occ_total = tot_occ,
    pairs_decoded = int(decoded["n_patients"].sum()),
    pairs_total = tot_pairs,
)
cov["occ_pct"] = round(100*cov["occ_decoded"]/cov["occ_total"],1)
cov["pairs_pct"] = round(100*cov["pairs_decoded"]/cov["pairs_total"],1)
cov["codes_pct"] = round(100*cov["codes_decoded"]/cov["codes_total"],1)

# per-disease patient prevalence (union of its codes across patients)
pcp = pd.read_csv(f"{HERE}/data/patient_code_pairs.csv", dtype={"code":str})
pcp["code"] = pcp["code"].str.strip()
pcp["disease"] = pcp["code"].map(CODE2DIS)
pcp_dec = pcp.dropna(subset=["disease"])
# patient set per disease
pat_by_dis = pcp_dec.groupby("disease")["person_id"].apply(lambda s: set(s.astype(str)))
dis_prev = {k: len(v) for k,v in pat_by_dis.items()}

# top raw codes table (with decode)
top = allc.head(20).copy()
top["disease_name"] = top["disease"].map(lambda k: DISEASE[k][0] if k in DISEASE else "(not decoded)")

# ---------------------------------------------------------------------------
# 2. SPOKE: build disease-disease network via shared genes
# ---------------------------------------------------------------------------
edges = json.load(open(f"{HERE}/kg/disease_gene_edges.json"))
genes = defaultdict(set)
for r in edges:
    genes[r["doid"]].add(r["gid"])
gene_counts = {r["doid"]: r["n_genes"] for r in json.load(open(f"{HERE}/kg/disease_gene_counts.json"))}

# doid -> disease key + name
doid2key = {v[1]:k for k,v in DISEASE.items()}
name = {v[1]:v[0] for v in DISEASE.values()}
doids = [v[1] for v in DISEASE.values()]

# pairwise shared genes / jaccard over all C(19,2) pairs
pairs = []
for a,c in itertools.combinations(doids, 2):
    ga, gc = genes[a], genes[c]
    shared = len(ga & gc)
    union = len(ga | gc)
    jac = shared/union if union else 0.0
    pairs.append(dict(a=a, b=c, an=name[a], bn=name[c], shared=shared,
                      jaccard=round(jac,4)))
pairs_df = pd.DataFrame(pairs)
n_possible = len(pairs)
n_shared1 = int((pairs_df["shared"]>=1).sum())

# Full weighted graph (weight = shared genes); hubs by total shared genes (weighted degree)
G = nx.Graph()
for d in doids: G.add_node(d, name=name[d], ngenes=gene_counts.get(d,0))
for p in pairs:
    if p["shared"]>0:
        G.add_edge(p["a"], p["b"], shared=p["shared"], jaccard=p["jaccard"])

wdeg = {d: sum(G[d][n]["shared"] for n in G[d]) for d in G.nodes}  # total shared genes
hub_rank = sorted(wdeg.items(), key=lambda x:-x[1])

# Thresholded structural network: Jaccard-based (normalizes for gene-set size).
# data-driven cut at the median non-zero Jaccard.
nz_j = pairs_df.loc[pairs_df["jaccard"]>0,"jaccard"]
J_THR = round(float(nz_j.median()),4)
Gj = nx.Graph()
for d in doids: Gj.add_node(d, name=name[d])
for p in pairs:
    if p["jaccard"]>=J_THR:
        Gj.add_edge(p["a"], p["b"], weight=p["jaccard"], shared=p["shared"])
deg_j = dict(Gj.degree())
hub_j = sorted(deg_j.items(), key=lambda x:-x[1])

# communities on Jaccard-thresholded graph
comms = list(nx.community.greedy_modularity_communities(Gj, weight="weight")) if Gj.number_of_edges() else []
communities = [sorted(name[d] for d in cset) for cset in comms]
try:
    modularity = round(nx.community.modularity(Gj, comms, weight="weight"),3) if comms else None
except Exception:
    modularity = None

# strongest biological links (top shared-gene pairs and top jaccard pairs)
top_shared = pairs_df.sort_values("shared", ascending=False).head(10)
top_jac = pairs_df.sort_values("jaccard", ascending=False).head(10)

# ---------------------------------------------------------------------------
# 3. EHR observed co-occurrence among resolved diseases (contrast layer)
# ---------------------------------------------------------------------------
co = []
for a,c in itertools.combinations(sorted(dis_prev, key=lambda k:-dis_prev[k]), 2):
    pa, pc = pat_by_dis[a], pat_by_dis[c]
    both = len(pa & pc)
    if both>0:
        co.append(dict(a=DISEASE[a][0], b=DISEASE[c][0], both=both,
                       jaccard=round(both/len(pa|pc),3)))
co_df = pd.DataFrame(co).sort_values("both", ascending=False) if co else pd.DataFrame()

# ---------------------------------------------------------------------------
# OUTPUT
# ---------------------------------------------------------------------------
res = dict(
    ehr=dict(
        n_condition_rows=16441, n_icd_rows=tot_occ, n_patients=100,
        n_distinct_codes=n_distinct, n_icd9_rows=int(icd9["n_occ"].sum()),
        n_icd10_rows=int(icd10["n_occ"].sum()),
        n_distinct_icd9=int(len(icd9)), n_distinct_icd10=int(len(icd10)),
        burden=burden_stats,
        top20=top[["code","vocab","n_patients","n_occ","disease_name"]].to_dict("records"),
    ),
    coverage=cov,
    resolution=dict(
        n_diseases=len(DISEASE),
        n_exact=sum(1 for v in DISEASE.values() if v[2]=="exact"),
        n_approx=sum(1 for v in DISEASE.values() if v[2]=="approximate"),
        diseases=[dict(name=v[0], doid=v[1], status=v[2], n_genes=gene_counts.get(v[1],0),
                       ehr_prevalence=dis_prev.get(k,0)) for k,v in DISEASE.items()],
    ),
    network=dict(
        n_nodes=G.number_of_nodes(), n_edges_any_shared=G.number_of_edges(),
        n_possible_pairs=n_possible, pct_pairs_linked=round(100*n_shared1/n_possible,1),
        jaccard_threshold=J_THR, n_edges_thresholded=Gj.number_of_edges(),
        hubs_by_total_shared_genes=[dict(name=name[d], total_shared=int(w),
                                         n_genes=gene_counts.get(d,0)) for d,w in hub_rank[:8]],
        hubs_by_degree_jaccard=[dict(name=name[d], degree=int(g)) for d,g in hub_j[:8]],
        top_shared_pairs=top_shared[["an","bn","shared","jaccard"]].to_dict("records"),
        top_jaccard_pairs=top_jac[["an","bn","shared","jaccard"]].to_dict("records"),
        communities=communities, modularity=modularity,
        resembles_edges=len(json.load(open(f"{HERE}/kg/resembles_edges.json"))),
    ),
    ehr_cooccurrence=(co_df.head(12).to_dict("records") if len(co_df) else []),
)
json.dump(res, open(f"{HERE}/analysis_results.json","w"), indent=2)

# ---- console summary ----
def line(): print("-"*72)
print("STUDY M RESULTS"); line()
print(f"Cohort: {res['ehr']['n_patients']} patients | {res['ehr']['n_condition_rows']} condition rows")
print(f"ICD diagnoses: {tot_occ} rows, {n_distinct} distinct codes "
      f"(ICD9 {len(icd9)} codes/{int(icd9['n_occ'].sum())} rows; ICD10 {len(icd10)} codes/{int(icd10['n_occ'].sum())} rows)")
print(f"Burden/patient (distinct codes): median {burden_stats['med']:.0f} "
      f"[IQR {burden_stats['q1']:.0f}-{burden_stats['q3']:.0f}], range {burden_stats['mn']}-{burden_stats['mx']}, mean {burden_stats['mean']}")
line()
print(f"DECODE+RESOLVE COVERAGE:")
print(f"  distinct codes decoded->disease: {cov['codes_decoded']}/{cov['codes_total']} ({cov['codes_pct']}%)")
print(f"  ICD occurrences covered: {cov['occ_decoded']}/{cov['occ_total']} ({cov['occ_pct']}%)")
print(f"  patient-code pairs covered: {cov['pairs_decoded']}/{cov['pairs_total']} ({cov['pairs_pct']}%)")
print(f"  disease concepts resolved in SPOKE: {res['resolution']['n_exact']} exact + "
      f"{res['resolution']['n_approx']} approximate = {res['resolution']['n_diseases']}/{res['resolution']['n_diseases']}")
line()
print(f"SPOKE NETWORK: {res['network']['n_nodes']} nodes; "
      f"{res['network']['n_edges_any_shared']}/{n_possible} pairs share >=1 gene ({res['network']['pct_pairs_linked']}%)")
print(f"  RESEMBLES_DrD edges among set: {res['network']['resembles_edges']} (network built on shared genes only)")
print(f"  Jaccard-thresholded (>= {J_THR}) structural graph: {Gj.number_of_edges()} edges")
print("  Hubs by total shared genes:")
for h in res['network']['hubs_by_total_shared_genes'][:6]:
    print(f"    {h['name']:32s} total_shared={h['total_shared']:5d}  (own genes {h['n_genes']})")
print("  Top shared-gene pairs:")
for p in res['network']['top_shared_pairs'][:6]:
    print(f"    {p['an']:26s} -- {p['bn']:26s} shared={p['shared']:4d} J={p['jaccard']}")
print(f"  Communities (modularity {modularity}):")
for i,cm in enumerate(communities,1):
    print(f"    C{i}: {', '.join(cm)}")
line()
print("EHR observed co-occurrence (top pairs, same patients):")
for r0 in res['ehr_cooccurrence'][:6]:
    print(f"    {r0['a']:26s} + {r0['b']:26s} both={r0['both']}")
print("\nwrote study-M/analysis_results.json")

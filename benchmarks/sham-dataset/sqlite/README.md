# Sham Dataset — MIMIC-IV Demo (OMOP CDM) as SQLite

`sham_mimic_omop.sqlite` is a single self-contained SQLite database built from the
MIMIC-IV demo dataset (100-patient subset) in the OMOP Common Data Model, downloaded
from [PhysioNet](https://physionet.org/content/mimic-iv-demo-omop/0.9/). See
[SOURCE_README.md](SOURCE_README.md) for provenance and citations, and
[LICENSE.txt](LICENSE.txt) for the data license (ODC-By 1.0).

## Querying

```bash
sqlite3 benchmarks/sham-dataset/sqlite/sham_mimic_omop.sqlite
```

```python
import sqlite3
conn = sqlite3.connect("benchmarks/sham-dataset/sqlite/sham_mimic_omop.sqlite")
```

## Contents

32 OMOP CDM tables, 467,840 rows total. Non-empty tables:

| Table | Rows | | Table | Rows |
| --- | --- | --- | --- | --- |
| measurement | 338,550 | | condition_era | 3,771 |
| observation | 31,390 | | fact_relationship | 1,752 |
| procedure_occurrence | 18,447 | | visit_occurrence | 852 |
| drug_exposure | 18,229 | | specimen | 150 |
| condition_occurrence | 16,441 | | dose_era | 117 |
| visit_detail | 14,479 | | person / observation_period | 100 |
| drug_era | 7,931 | | care_site | 31 |
| concept_relationship | 7,716 | | vocabulary | 27 |
| device_exposure | 3,855 | | death | 15 |
| concept | 3,885 | | location / cdm_source | 1 |

Empty (schema only): attribute_definition, cohort, cohort_attribute,
cohort_definition, cost, metadata, note, note_nlp, payer_plan_period, provider.

## Schema notes for agents

- **Types are exact.** All `*_id` columns are 64-bit INTEGERs (many are large
  and/or negative — e.g. `person_id = -9066461348710750663`); dates/datetimes are
  TEXT in ISO format (`YYYY-MM-DD` / `YYYY-MM-DD HH:MM:SS`), comparable with
  string comparison and SQLite date functions.
- **The `concept` table is partial.** The PhysioNet demo ships only MIMIC-local
  concepts (`concept_id >= 2000000000`, vocabularies like `mimiciv_drug_ndc`,
  `mimiciv_meas_lab_loinc`). Standard vocabulary rows (SNOMED, RxNorm, LOINC) are
  **not included**, so joining a standard `*_concept_id` (e.g.
  `condition_concept_id = 4145513`) to `concept` returns nothing. To get
  human-readable names, join `*_source_concept_id` to `concept`, or use the
  `*_source_value` columns directly.
- **Indexes** (124) cover the common access paths: on every event table,
  `person_id`, `visit_occurrence_id`, the domain and source `*_concept_id`
  columns, and the primary date column; small lookup tables (`concept`,
  `concept_relationship`, `vocabulary`, …) are fully indexed on their key
  columns. `ANALYZE` has been run. Other columns are unindexed to keep the
  file under GitHub's 100 MB limit — full scans of the largest table
  (338K rows) take ~16 ms, so unindexed filters remain fast.
- Patient timelines are date-shifted (years like 2095/2113 are expected).

Example — most common conditions with readable names:

```sql
SELECT c.concept_name, COUNT(DISTINCT co.person_id) AS n_patients
FROM condition_occurrence co
JOIN concept c ON c.concept_id = co.condition_source_concept_id
GROUP BY c.concept_name
ORDER BY n_patients DESC
LIMIT 10;
```

## Rebuilding

The database was generated from the CSVs in
`medcp-manuscript/Sham Dataset/MIMIC/` by scanning every column to infer types
(INTEGER only when every value is a pure 64-bit integer, avoiding float
round-tripping of large IDs), loading all rows, then creating indexes and
running `ANALYZE`/`VACUUM`. Row counts were verified against the source CSVs.

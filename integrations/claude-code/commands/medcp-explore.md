---
description: Explore the connected MedCP clinical database — list tables and summarize patient demographics
---

Use the MedCP MCP tools to give me a quick orientation of the connected clinical
records database:

1. Call `list_clinical_tables` and show the available tables.
2. Using `query_clinical_records` (read-only SELECT only), report:
   - the number of patients in the `person` table,
   - the gender and (if available) race/ethnicity breakdown,
   - the number of rows in `visit_occurrence`, `condition_occurrence`, and
     `drug_exposure` if those tables exist.
3. Summarize what kind of analyses this dataset can support.

Only issue read-only `SELECT` / `WITH` queries. Do not attempt any write.

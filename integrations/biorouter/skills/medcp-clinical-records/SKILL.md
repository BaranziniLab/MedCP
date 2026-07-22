---
name: medcp-clinical-records
description: Query electronic health records (OMOP CDM) read-only through MedCP, across SQL Server, MySQL, or a local SQLite file. Use when the user asks to explore clinical tables, build cohorts, or summarize patient data.
---

# Querying clinical records with MedCP

MedCP exposes read-only tools over an electronic health record database. The
backend may be SQL Server, MySQL, or a local SQLite file, but the tools and the
workflow are identical.

## Tools

- `list_clinical_tables` — enumerate available tables (schema, name, type).
- `query_clinical_records` — run a single read-only `SELECT` / `WITH` query.
- `query_knowledge_graph` / `get_knowledge_graph_schema` — present only when a
  SPOKE knowledge graph is configured.

Tool names may carry the `MedCP-` namespace prefix (e.g.
`MedCP-query_clinical_records`).

## Rules

- **Read-only.** Only `SELECT` and `WITH` queries are accepted. Anything that
  writes (INSERT/UPDATE/DELETE/DROP/…) or stacks statements with `;` is rejected.
- **One statement per call.** Do not chain multiple statements.
- **Dialect.** The data usually follows the OMOP Common Data Model. Write portable
  SQL. Note SQLite lacks some SQL Server/MySQL functions — prefer `COUNT(*)`,
  `GROUP BY`, `JOIN`, and simple date functions.

## Recommended workflow

1. Call `list_clinical_tables` first to confirm the schema.
2. Inspect a table before aggregating, e.g.
   `SELECT * FROM person LIMIT 5`.
3. Build the analysis query incrementally; keep result sets small with `LIMIT`
   while iterating.
4. For OMOP, common joins are `person` → `visit_occurrence` →
   `condition_occurrence` / `drug_exposure` / `measurement`, and concept ids
   resolve via the `concept` table (`concept_id` → `concept_name`).

## Examples

Count patients:
```sql
SELECT COUNT(*) AS n_persons FROM person;
```

Gender breakdown with concept names:
```sql
SELECT c.concept_name AS gender, COUNT(*) AS n
FROM person p
JOIN concept c ON c.concept_id = p.gender_concept_id
GROUP BY c.concept_name
ORDER BY n DESC;
```

Top recorded conditions:
```sql
SELECT c.concept_name AS condition, COUNT(*) AS n
FROM condition_occurrence co
JOIN concept c ON c.concept_id = co.condition_concept_id
GROUP BY c.concept_name
ORDER BY n DESC
LIMIT 20;
```

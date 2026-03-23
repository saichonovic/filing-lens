# FilingLens Docs

The canonical architecture docs currently live at the project root:

- `FILINGLENS_BOOTSTRAP_PLAN_V1.md`
- `FILINGLENS_CORE_SCHEMA_V1.md`
- `FILINGLENS_ETL_FLOW_V1.md`
- `FILINGLENS_DOCETL_PLACEMENT_V1.md`
- `FILINGLENS_SIGNAL_LIBRARY_V1.md`

Keep those root documents as the implementation contract unless intentionally superseded.

Optional Stage 5 LLM enrichment:

- the intended LLM path is the existing BungeLens DocETL bootstrap using GPT-5.4
- the current deterministic pipeline does not require any LLM dependency
- wire DocETL/GPT-5.4 before enabling narrative enrichment in production

# FilingLens Docs

The canonical architecture docs currently live at the project root:

- `FILINGLENS_BOOTSTRAP_PLAN_V1.md`
- `FILINGLENS_CORE_SCHEMA_V1.md`
- `FILINGLENS_ETL_FLOW_V1.md`
- `FILINGLENS_DOCETL_PLACEMENT_V1.md`
- `FILINGLENS_SIGNAL_LIBRARY_V1.md`

Keep those root documents as the implementation contract unless intentionally superseded.

Optional Stage 5 LLM enrichment:

- `scripts/derive.py --with-llm` expects `ANTHROPIC_API_KEY`
- install `anthropic` into `.venv` only when enabling the narrative layer

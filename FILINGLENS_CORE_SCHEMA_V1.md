# FilingLens Core Schema v1
## Canonical Data Model for SEC Filing Intelligence
**Version:** 1.0  
**Status:** Schema baseline  
**Companion docs:** `FILINGLENS_BOOTSTRAP_PLAN_V1.md`, `FILINGLENS_ETL_FLOW_V1.md`, `FILINGLENS_DOCETL_PLACEMENT_V1.md`, `FILINGLENS_SIGNAL_LIBRARY_V1.md`

---

## Summary

FilingLens must separate three layers of truth:

1. canonical filing identity and extracted facts
2. candidate or ambiguous interpretations
3. derived investor intelligence

The system should preserve deterministic financial truth while allowing LLM-supported interpretation and synthesis where ambiguity or narrative analysis matters.

---

## Primary Unit of Intelligence

The primary intelligence grain is:

- `filing` for source truth
- `financial_fact` for numeric truth
- `detected_signal` for investor-risk intelligence

No single object is sufficient by itself. FilingLens intelligence emerges from the combination of:

- filing structure
- extracted facts
- section-level language
- prior-period comparisons
- multi-document sequences

---

## First-Class Object Inventory

### Source and identity layer

- `issuers`
- `issuer_aliases`
- `filings`
- `filing_documents`
- `filing_periods`

### Structured filing layer

- `filing_sections`
- `financial_facts`
- `policy_disclosures`
- `management_language_observations`

### Comparison and signal layer

- `filing_comparisons`
- `detected_signals`
- `signal_evidence`
- `signal_sequences`

### Governance and operations layer

- `analysis_runs`
- `review_queue`

### Product layer

- `watchlists`
- `watchlist_issuers`
- `alerts`
- `chat_chunks`

Phase 1 can defer some product-layer tables, but the schema should anticipate them.

---

## Canonical Table Roles

## 1. `issuers`

One row per company or reporting entity.

Suggested fields:

- `id`
- `issuer_key`
- `name`
- `ticker`
- `cik`
- `lei` nullable
- `exchange`
- `sector`
- `industry`
- `status`
- `created_at`
- `updated_at`

Rules:

- `cik` is the strongest deterministic external identifier when available
- `ticker` is useful but should not be treated as the sole canonical key

---

## 2. `issuer_aliases`

Alternative names or identifiers that assist matching.

Suggested fields:

- `id`
- `issuer_id`
- `alias_type`
- `alias_value`
- `source`
- `created_at`

Use cases:

- historical name changes
- alternate legal entity names
- ticker changes

---

## 3. `filings`

One row per canonical SEC filing submission.

Suggested fields:

- `id`
- `issuer_id`
- `accession_number`
- `form_type`
- `filing_date`
- `period_end_date`
- `fiscal_year`
- `fiscal_quarter` nullable
- `amendment_flag`
- `source_url`
- `ingestion_status`
- `content_hash`
- `created_at`
- `updated_at`

Rules:

- uniqueness should be anchored around `accession_number`
- amendments should remain distinct filings, not overwrite originals

---

## 4. `filing_documents`

Physical or logical artifacts associated with a filing.

Suggested fields:

- `id`
- `filing_id`
- `document_role`
- `source_format`
- `file_path`
- `source_url`
- `mime_type`
- `page_count` nullable
- `word_count` nullable
- `ocr_required`
- `extraction_status`
- `created_at`

Examples:

- filing HTML
- attached exhibit PDF
- inline XBRL artifact

---

## 5. `filing_periods`

Normalized reporting-period context.

Suggested fields:

- `id`
- `filing_id`
- `period_type`
- `start_date` nullable
- `end_date`
- `comparable_prior_filing_id` nullable
- `period_label`
- `created_at`

Use cases:

- year-over-year alignment
- trailing-quarter calculations
- event sequence windows

---

## 6. `filing_sections`

Canonical section segmentation for each filing.

Suggested fields:

- `id`
- `filing_id`
- `document_id`
- `section_code`
- `section_title`
- `section_order`
- `section_text`
- `section_hash`
- `parent_section_id` nullable
- `confidence`
- `created_at`

Examples:

- `ITEM_1A_RISK_FACTORS`
- `ITEM_7_MDA`
- `AUDITOR_REPORT`
- `FOOTNOTE_DEBT`

---

## 7. `financial_facts`

The numeric substrate of FilingLens.

Suggested fields:

- `id`
- `filing_id`
- `period_id`
- `fact_name`
- `fact_category`
- `fact_value_numeric`
- `fact_value_text` nullable
- `unit`
- `scale`
- `statement_type`
- `source_section_id` nullable
- `source_method`
- `confidence`
- `created_at`

Examples:

- revenue
- accounts_receivable
- inventory
- operating_cash_flow
- diluted_eps
- total_debt
- covenant_leverage_ratio

Rules:

- deterministic extraction should populate this table wherever possible
- LLMs may suggest facts only into candidate or review paths, not direct canonical writes

---

## 8. `policy_disclosures`

Normalized policy or disclosure statements extracted from sections and footnotes.

Suggested fields:

- `id`
- `filing_id`
- `section_id`
- `policy_type`
- `policy_text`
- `is_new_vs_prior` nullable
- `change_summary` nullable
- `confidence`
- `created_at`

Examples:

- revenue recognition policy
- bill-and-hold language
- capitalization policy
- liquidity assumptions

---

## 9. `management_language_observations`

Narrative observations derived from text analysis.

Suggested fields:

- `id`
- `filing_id`
- `section_id`
- `observation_type`
- `observation_text`
- `severity`
- `source_method`
- `created_at`

Examples:

- passive voice evasion
- hedged going-concern phrasing
- metric switching
- buried risk wording

These are derived, not canonical financial truth.

---

## 10. `filing_comparisons`

Structured comparison outputs between filings.

Suggested fields:

- `id`
- `current_filing_id`
- `comparison_filing_id`
- `comparison_type`
- `summary_json`
- `created_at`

Examples:

- current 10-K vs prior 10-K
- latest 10-Q vs prior quarter

---

## 11. `detected_signals`

One row per risk or intelligence signal produced by the system.

Suggested fields:

- `id`
- `issuer_id`
- `filing_id` nullable
- `signal_type`
- `signal_family`
- `severity`
- `score`
- `verdict`
- `status`
- `detection_method`
- `summary`
- `investor_question`
- `created_at`

Examples:

- channel stuffing
- accrual divergence
- covenant stress
- auditor change risk
- governance misalignment

Rules:

- this is a derived intelligence table
- deterministic and LLM-supported outputs can coexist, but provenance must be explicit

---

## 12. `signal_evidence`

Evidence spine for each signal.

Suggested fields:

- `id`
- `signal_id`
- `evidence_type`
- `section_id` nullable
- `fact_id` nullable
- `quoted_text` nullable
- `numeric_value` nullable
- `comparison_value` nullable
- `evidence_json` nullable
- `created_at`

Purpose:

- make signals auditable
- support citations in product UI
- separate verdict from supporting facts

---

## 13. `signal_sequences`

Multi-document and temporal pattern objects.

Suggested fields:

- `id`
- `issuer_id`
- `sequence_type`
- `start_filing_id`
- `end_filing_id`
- `sequence_summary`
- `severity`
- `confidence`
- `created_at`

Examples:

- going-concern pre-signal followed by auditor change
- risk-factor inflation followed by executive departure
- three-quarter accrual divergence trend

---

## 14. `analysis_runs`

Mandatory run-level observability.

Suggested fields:

- `id`
- `stage_name`
- `scope_type`
- `scope_id`
- `run_status`
- `records_written`
- `error_summary` nullable
- `started_at`
- `finished_at` nullable
- `config_snapshot` nullable

This is required from day one.

---

## 15. `review_queue`

Database-backed ambiguity handling.

Suggested fields:

- `id`
- `object_type`
- `object_id` nullable
- `issue_type`
- `confidence`
- `status`
- `source_run_id`
- `details_json`
- `created_at`
- `resolved_at` nullable

Examples:

- uncertain prior-filing match
- low-confidence policy change extraction
- ambiguous section mapping
- semantically inferred signal that lacks deterministic support

---

## 16. Product-Surface Tables

These can be Phase 2:

- `watchlists`
- `watchlist_issuers`
- `alerts`
- `chat_chunks`

These must read from canonical and derived layers, not invent truth independently.

---

## Deterministic vs Derived Boundary

### Canonical deterministic truth

These should be treated as canonical truth:

- issuer identity
- filing identity
- filing dates and periods
- section structure where deterministically parsed
- extracted numeric facts
- explicit policy text

### Derived intelligence

These should be treated as derived:

- severity ratings
- fraud-pattern interpretations
- management-tone observations
- comparative narratives
- investor questions
- plain-English summaries

### Review-needed candidate outputs

These should not write directly to canonical truth:

- LLM-inferred policy changes
- weak section alignments
- noisy cross-document linkages
- semantically inferred numeric claims

---

## Core Design Rule

FilingLens should be able to answer two different questions cleanly:

- "What exactly did the filing say and what numbers did it contain?"
- "What do those facts likely mean for an investor?"

If the schema mixes those answers into the same write path, the architecture is wrong.

---

*FilingLens Core Schema v1 - canonical data model for SEC filing intelligence*

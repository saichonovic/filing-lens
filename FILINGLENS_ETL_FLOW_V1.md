# FilingLens ETL Flow v1
## Canonical SEC Filing Intelligence Pipeline
**Version:** 1.0  
**Status:** Implementation baseline  
**Companion docs:** `FILINGLENS_CORE_SCHEMA_V1.md`, `FILINGLENS_DOCETL_PLACEMENT_V1.md`, `FILINGLENS_SIGNAL_LIBRARY_V1.md`

---

## Summary

FilingLens ETL is structured around six stages of truth:

1. **Acquire**
2. **Extract**
3. **Normalize**
4. **Resolve**
5. **Derive**
6. **Publish**

This flow is designed so that:

- raw SEC artifacts are preserved
- filing and issuer identity remain deterministic
- numeric truth is extracted before interpretation
- cross-period and cross-document alignment is reviewable
- DocETL is used only where semantic ambiguity or narrative synthesis matters
- product outputs read from canonical and derived layers only

---

## Locked Stage Names and Module Mapping

These names should be fixed and mirrored in implementation modules.

| Stage | Name | Suggested Module |
| :--- | :--- | :--- |
| 1 | Acquire | `pipeline/acquire.py` |
| 2 | Extract | `pipeline/extract.py` |
| 3 | Normalize | `pipeline/normalize.py` |
| 4 | Resolve | `pipeline/resolve.py` |
| 5 | Derive | `pipeline/derive.py` |
| 6 | Publish | `pipeline/publish.py` |

---

## Stage Model

## 1. Acquire

**Purpose:** register source artifacts unchanged.

**Inputs**

- SEC submission metadata
- filing HTML
- filing PDF when present
- XBRL or inline XBRL artifacts
- exhibit documents
- manual backfills if needed

**Outputs**

- raw files stored in local or object-compatible storage
- minimal canonical filing rows created

**Primary writes**

- `issuers`
- `filings`
- `filing_documents`

**Logic**

- register accession number and filing metadata
- compute content hash
- preserve raw source artifacts unchanged
- do not interpret content yet

**Deterministic or LLM?**

- deterministic only

---

## 2. Extract

**Purpose:** convert source artifacts into machine-readable text and shallow structure.

**Inputs**

- `filing_documents` from Acquire stage

**Outputs**

- extracted text
- parsed section candidates
- basic table candidates
- XBRL-derived fact candidates
- OCR metadata if required

**Primary writes**

- updates to `filing_documents`
- staging extracts or temp datasets

**Logic**

- HTML to structured text
- PDF text extraction or OCR when necessary
- conservative encoding normalization
- raw table capture
- candidate section boundary extraction

**Deterministic or LLM?**

- deterministic only

**Do not do here**

- no signal scoring
- no investor summaries
- no canonical narrative interpretation

---

## 3. Normalize

**Purpose:** turn extracted filing content into standardized canonical financial records using deterministic rules first.

**Inputs**

- extracted filing artifacts

**Outputs**

- normalized section map
- normalized reporting periods
- normalized financial facts
- explicit policy disclosures
- candidate observations for later resolution

**Primary writes**

- `filing_sections`
- `filing_periods`
- `financial_facts`
- `policy_disclosures`

**Optional staging writes**

- `section_candidates`
- `fact_candidates`
- `policy_candidates`
- `comparison_candidates`

**Deterministic or LLM?**

- deterministic by default

**Why this stage matters**

- it creates the numeric and structural substrate before interpretation
- it prevents speculative narratives from contaminating canonical financial truth

---

## 4. Resolve

**Purpose:** align normalized records across filings and periods into stable comparable structures.

**Inputs**

- normalized rows and candidate records from Stage 3

**Outputs**

- canonical issuer identity updates
- prior-period filing alignment
- section alignment across filings
- stronger mapping for policy change detection
- reviewable comparison candidates

**Primary writes**

- updates to `issuers`
- updates to `issuer_aliases`
- updates to `filing_periods`
- `filing_comparisons`
- `review_queue`

**Deterministic or LLM?**

- hybrid, but deterministic first

**Deterministic tasks**

- exact issuer matching by CIK
- filing accession validation
- obvious current-vs-prior 10-K or 10-Q alignment
- deterministic section code mapping

**DocETL or LLM tasks**

- aligning noisy section pairs where titles drift materially
- inferring likely policy change significance
- interpreting whether a phrase is functionally equivalent to prior-year language

**Review queue insertion points**

- multiple plausible prior filings
- uncertain section alignment
- possible but weak policy-change inference
- filing family ambiguity caused by amendments or restatements

---

## 5. Derive

**Purpose:** compute investor intelligence outputs and product-ready analytical views from canonical data.

**Inputs**

- canonical filing objects
- financial facts
- comparisons
- optionally narrative observations

**Outputs**

- red flags
- severity ratings
- investor summaries
- follow-up questions
- sequence-level risk narratives
- watchlist alert payloads
- chat-ready chunks

**Primary writes**

- `detected_signals`
- `signal_evidence`
- `signal_sequences`
- `management_language_observations`
- `alerts`
- `chat_chunks`

**Deterministic or LLM?**

- mixed
- deterministic first, LLM second

**Examples**

- DSO trend and revenue spike correlation
- accrual ratio calculation
- covenant headroom stress
- executive compensation vs performance mismatch
- auditor change follow-on risk
- going-concern hedge language analysis

---

## 6. Publish

**Purpose:** expose results to product surfaces.

**Outputs**

- APIs
- dashboards
- alerts
- exports
- ask-the-filing retrieval responses

**Rule**

- no new truth is invented here
- publish reads only from canonical and derived tables

---

## Idempotency Rules

Every stage must be safe to rerun.

| Stage | Idempotency Rule |
| :--- | :--- |
| Acquire | Skip or reconcile when `accession_number` and `content_hash` already exist |
| Extract | Skip if extraction status is already complete and artifact hash is unchanged |
| Normalize | Upsert facts and sections against deterministic uniqueness rules |
| Resolve | Never replace higher-confidence filing alignments with lower-confidence ones silently |
| Derive | Recompute replaceable derived outputs per filing, issuer, or period scope |
| Publish | Read-only; idempotency not applicable |

Additional rule:

- ambiguity discovered during rerun must go to `review_queue`, not silently fork canonical truth

---

## Deterministic vs DocETL Boundary

### Deterministic by default

Use deterministic logic for:

- filing registration
- issuer matching by strong IDs
- raw text extraction
- section segmentation where structurally explicit
- numeric fact extraction
- financial ratio calculations
- threshold checks
- prior-period alignment when exact
- canonical key generation
- review queue routing

### DocETL or LLM only where semantic ambiguity matters

Use DocETL for:

- management-language analysis
- buried-risk interpretation
- metric-switching narratives
- policy wording change significance
- multi-document sequence reasoning
- investor-facing summaries and questions

**Rule:** LLMs enrich and contextualize hard cases. They do not replace the deterministic financial backbone.

---

## Recommended Staging Objects

Recommended staging objects:

- `section_candidates`
- `fact_candidates`
- `policy_candidates`
- `comparison_candidates`
- `signal_candidates`
- `review_queue`

Ambiguous extraction should remain reviewable until validated.

---

## Source-by-Source ETL

## 1. 10-K Annual Reports

**Flow**

- Acquire
- Extract sections and tables
- Normalize annual facts and policy disclosures
- Resolve prior-year comparison mapping
- Derive annual red flags and investor summary

**Primary writes**

- `filings`
- `filing_sections`
- `financial_facts`
- `policy_disclosures`
- `detected_signals`

---

## 2. 10-Q Quarterly Reports

**Flow**

- Acquire
- Extract quarterly facts and narrative changes
- Normalize quarter-level periods and metrics
- Resolve quarter sequence context
- Derive cash runway, margin trend, guidance, and short-term warning signals

**Primary writes**

- `filings`
- `filing_periods`
- `financial_facts`
- `detected_signals`

---

## 3. 8-K Current Reports

**Flow**

- Acquire
- Extract event items and free-text disclosures
- Normalize event category and dates
- Resolve linkage to current filing context
- Derive urgency-ranked event signals

**Primary writes**

- `filings`
- `filing_sections`
- `detected_signals`
- `signal_sequences` when chained to other filings

---

## 4. DEF 14A Proxy Statements

**Flow**

- Acquire
- Extract compensation, governance, and related-party disclosures
- Normalize structured governance fields
- Resolve compensation vs performance comparisons
- Derive governance and alignment signals

**Primary writes**

- `filings`
- `filing_sections`
- `financial_facts`
- `policy_disclosures`
- `detected_signals`

---

## Async Boundaries

### Safe async jobs

- OCR
- long-footnote parsing
- management-language interpretation
- cross-document narrative synthesis
- investor summary generation
- watchlist alert fanout
- chat chunk generation

### Should remain synchronous or tightly controlled

- filing registration
- accession-number uniqueness
- canonical issuer matching by strong identifiers
- numeric fact writes
- deterministic ratio calculations
- threshold-based signal activation

---

## Review Queue Rules

Rows go to review when:

- confidence is low
- multiple prior filings are plausible comparisons
- LLM inference created a material interpretation
- policy-change significance is semantically inferred only
- numeric evidence conflicts across extraction methods
- sequence-level narrative depends on weak linkage

The review queue should be filterable by:

- object type
- issuer
- filing
- signal family
- confidence
- pipeline run

---

## ETL Success Criteria

The ETL is healthy when:

- source artifacts land in `filings` and `filing_documents`
- sections and key facts are extracted consistently
- prior filings align reliably
- detected signals have auditable evidence
- ambiguous rows route to review instead of becoming silent truth
- investor summaries read from stable derived outputs

---

## Recommended Next Step After This Document

Once this ETL flow is accepted:

1. map ETL stages to actual code modules
2. define migration order by phase
3. decide which steps remain deterministic and which require DocETL
4. implement the first issuer-based validation slice

---

*FilingLens ETL Flow v1 - implementation baseline for SEC filing processing*

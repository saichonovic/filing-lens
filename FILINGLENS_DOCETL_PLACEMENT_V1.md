# FilingLens DocETL Placement v1
## Where DocETL Fits in the Financial Filing Intelligence Pipeline
**Version:** 1.0  
**Status:** Implementation baseline  
**Companion docs:** `FILINGLENS_CORE_SCHEMA_V1.md`, `FILINGLENS_ETL_FLOW_V1.md`, `FILINGLENS_SIGNAL_LIBRARY_V1.md`

---

## Summary

This document defines where DocETL should and should not be used in FilingLens.

The key principle is:

> DocETL is used for semantic extraction, interpretation, decomposition, and synthesis of ambiguous filing language.  
> It does not replace deterministic filing ingestion, issuer identity, numeric fact extraction, ratio calculation, or canonical financial truth.

---

## Core Placement Rule

### Deterministic ETL owns:

- filing registration
- accession and issuer identity handling
- content hashing
- text extraction and OCR
- section boundary parsing where explicit
- XBRL and table-derived fact extraction
- ratio calculations
- threshold checks
- canonical key generation
- review queue routing

### DocETL owns:

- interpretation of hedge language
- buried-risk extraction from narrative sections
- significance analysis of policy wording changes
- metric-switching detection with explanation
- sequence-level reasoning across filings
- investor-facing summaries and questions

### Hard rule

DocETL outputs must write to:

- staging tables
- candidate tables
- review queues
- derived intelligence tables

DocETL outputs must not directly create canonical numeric or identity truth without deterministic checks or review logic.

---

## Why DocETL Is a Fit Here

FilingLens handles long, noisy, cross-referential texts:

- Risk Factors
- MD&A
- debt and covenant footnotes
- auditor language
- executive-compensation narratives
- 8-K event disclosures

These are poor candidates for single-shot prompting and often require decomposition:

1. split by section or subtopic
2. extract candidate observations
3. compare against prior text
4. aggregate into signal narratives

That is exactly where DocETL adds value.

---

## Operator Families Relevant to FilingLens

The operator families most relevant here are:

### LLM-powered operators

- `map`
- `parallel-map`
- `resolve`
- `reduce`
- `filter`
- `rank`
- `extract`
- `cluster`

### Auxiliary operators

- `split`
- `gather`
- `unnest`
- `sample`
- `topk`

---

## Processing Patterns To Reuse

## 1. Long-section decomposition pattern

Use:

- `split`
- `gather`
- `map`

Best for:

- Risk Factors
- MD&A
- long debt and tax footnotes

---

## 2. Structured semantic extraction pattern

Use:

- `map`
- `extract`
- `unnest`

Best for:

- management hedges
- policy changes
- related-party disclosures
- governance concerns

---

## 3. Cross-document comparison pattern

Use:

- `map`
- `resolve`
- `reduce`

Best for:

- prior-year wording change analysis
- metric-switching detection
- risk language density shifts

---

## 4. Sequence synthesis pattern

Use:

- `filter`
- `rank`
- `reduce`

Best for:

- 10-K pre-distress wording followed by 8-K auditor change
- risk-factor inflation followed by management departure
- repeated quarter-level deterioration narratives

---

## 5. Validation or gleaning pattern

Use only on high-value ambiguous outputs.

Best for:

- buried-risk extraction when language is indirect
- subtle going-concern hedges
- weakly signaled fraud-pattern narratives

Do not use gleaning indiscriminately because it is expensive.

---

## Source-by-Source DocETL Placement

## 1. 10-K

### Deterministic first

Keep deterministic:

- filing metadata
- section segmentation
- annual financial facts
- explicit debt covenant fields
- explicit auditor metadata

### DocETL use

Use DocETL for:

- risk-language interpretation
- metric-switching explanation
- buried-risk extraction
- policy-change significance
- investor summary generation

### Recommended operators

- `split`
- `map`
- `extract`
- `reduce`

---

## 2. 10-Q

### Deterministic first

Keep deterministic:

- quarterly financial facts
- trend calculations
- runway calculations
- DSO and margin changes

### DocETL use

Use DocETL for:

- management credibility analysis
- explanation-quality analysis
- short-horizon warning synthesis

### Recommended operators

- `map`
- `extract`
- `reduce`

---

## 3. 8-K

### Deterministic first

Keep deterministic:

- event item classification
- filing date
- explicit item numbering

### DocETL use

Use DocETL for:

- why a contract terminated
- severity interpretation of executive departures
- auditor-disagreement narrative extraction
- regulation FD narrative interpretation

### Recommended operators

- `map`
- `extract`
- `rank`

---

## 4. DEF 14A

### Deterministic first

Keep deterministic:

- compensation values
- board composition counts
- explicit related-party transaction fields

### DocETL use

Use DocETL for:

- pay-for-performance misalignment interpretation
- governance risk framing
- compensation-structure shift narratives

### Recommended operators

- `map`
- `extract`
- `reduce`

---

## Operator Placement by ETL Stage

## Stage 1: Acquire

DocETL use:

- none

## Stage 2: Extract

DocETL use:

- generally none

Possible exception:

- future image-heavy exhibit interpretation, but not in core v1

## Stage 3: Normalize

DocETL use:

- limited
- only for candidate extraction from noisy narrative text after deterministic parsing has already done the obvious work

Good operators here:

- `extract`
- `map`
- `unnest`

## Stage 4: Resolve

DocETL use:

- medium

Good operators here:

- `resolve`
- `filter`
- `rank`

This is where ambiguous section or narrative equivalence can be handled.

## Stage 5: Derive

DocETL use:

- high

Good operators here:

- `reduce`
- `rank`
- `cluster`
- `filter`

This is the main synthesis layer for investor intelligence.

## Stage 6: Publish

DocETL use:

- none

Publishing should read from canonical and derived stores only.

---

## Where Optimization Should Be Used

Use optimization only for high-value complex semantic tasks:

- going-concern hedge extraction
- channel-stuffing narrative interpretation after deterministic gating
- policy language change significance
- multi-filing sequence synthesis

Do not use optimization for:

- fact extraction
- canonical ID generation
- ratio calculations
- threshold checks
- simple field classification

---

## Recommended Validation Policy

Validation or gleaning should be treated as a premium tool.

### Use gleaning for

- high-value ambiguous MD&A language
- debt-footnote covenant interpretation
- subtle pre-distress wording

### Avoid gleaning for

- filing dates
- accession numbers
- revenue values
- DSO calculations
- inventory balances
- explicit section labels

This keeps cost and latency under control.

---

## Staging vs Canonical Write Policy

DocETL outputs should normally land in:

- candidate tables
- review queue
- derived intelligence tables

DocETL outputs may update canonical tables only when:

- deterministic validation passes, or
- human review confirms the result

Examples:

- new policy-change observation -> staging first
- management-language hedge -> derived observation
- severity rating for channel stuffing -> derived signal
- semantically inferred numeric claim -> review queue first

---

## Recommended First DocETL Pipelines

Implement in this order:

### 1. Management hedge and buried-risk extraction

Goal:

- detect soft warning language
- identify non-committal or deflective phrasing

Operators:

- `split`
- `map`
- `extract`
- `reduce`

### 2. Policy-change significance detection

Goal:

- compare current and prior-year policy wording
- identify whether the change is substantive

Operators:

- `map`
- `resolve`
- `reduce`

### 3. Sequence narrative synthesis

Goal:

- convert multi-filing signals into investor-understandable risk narratives

Operators:

- `filter`
- `rank`
- `reduce`

### 4. Investor summary generation

Goal:

- transform canonical facts and derived signals into concise plain-English outputs

Operators:

- `filter`
- `reduce`

---

## Recommended Deferred DocETL Pipelines

Defer until core data is stable:

- broad thematic clustering across the entire SEC corpus
- generalized semantic screening across thousands of issuers
- agentic forensic investigations over all footnotes
- open-ended peer-comparison narratives

These depend on mature canonical data and cost controls first.

---

## Final Placement Decision

### Use DocETL heavily for:

- narrative filing sections
- policy wording changes
- buried-risk extraction
- investor-facing summaries
- sequence-level reasoning

### Use DocETL lightly for:

- 8-K event interpretation
- proxy governance summaries
- section equivalence resolution

### Do not use DocETL as the backbone for:

- acquisition
- deterministic normalization
- issuer identity
- numeric fact extraction
- ratio calculations
- threshold-based signal gating

---

## Go-Forward Rule

Before any DocETL pipeline is approved, it must answer:

- what deterministic work happens first?
- what evidence activates the LLM step?
- where does the output write?
- what validates the output before it affects users?
- is the semantic step worth the latency and cost?

If those answers are missing, the pipeline is underspecified.

---

*FilingLens DocETL Placement v1 - operator-aware semantic processing architecture*

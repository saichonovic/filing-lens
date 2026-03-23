# FilingLens Signal Library v1
## Risk Signals, Detection Rules, and Evidence Contracts
**Version:** 1.0  
**Status:** Detection baseline  
**Companion docs:** `FILINGLENS_CORE_SCHEMA_V1.md`, `FILINGLENS_ETL_FLOW_V1.md`, `FILINGLENS_DOCETL_PLACEMENT_V1.md`

---

## Summary

This document defines the first FilingLens signal families, the deterministic evidence they require, and where LLM interpretation should be applied.

Core rule:

> A signal should activate from deterministic evidence when possible.  
> LLM analysis should explain, contextualize, rank, or refine severity, not substitute for missing numeric substrate.

---

## Signal Family Design

Each signal definition should specify:

- purpose
- required inputs
- deterministic trigger logic
- optional LLM interpretation step
- severity model
- minimum evidence contract
- review conditions

---

## Signal Family 1: Revenue Quality

Focus:

- premature revenue recognition
- channel stuffing
- bill-and-hold arrangements
- round-trip transactions

### 1.1 Channel Stuffing

**Purpose**

Detect likely quarter-end channel loading that inflates revenue temporarily.

**Required inputs**

- quarterly revenue
- accounts receivable
- DSO trend
- inventory trend
- management explanation text

**Deterministic trigger logic**

- revenue spike materially above recent baseline
- DSO rising across multiple quarters
- inventory-to-revenue ratio rising or elevated

**Optional LLM step**

- analyze whether management credibly explains the combination
- identify deflection, omission, or policy change language

**Severity model**

- low: one weak signal
- medium: two signals
- high: all three present or two plus suspicious narrative language

**Minimum evidence contract**

- at least two numeric evidence rows in `signal_evidence`
- one section citation if LLM interpretation fires

**Review conditions**

- inventory proxy quality is weak
- seasonal business model may explain spike
- extracted quarterly facts are incomplete

---

### 1.2 Premature Revenue Recognition

**Purpose**

Detect revenue booked earlier than the underlying economics support.

**Required inputs**

- revenue recognition policy text
- DSO trend
- AR growth vs revenue growth
- shipment or delivery language where disclosed

**Deterministic trigger logic**

- AR growth materially outpaces revenue growth
- DSO deteriorates while policy suggests delivery-based recognition

**Optional LLM step**

- compare policy language and trend pattern
- assess whether disclosed recognition language increases pre-delivery risk

**Severity**

- medium to high depending on policy inconsistency and persistence

---

### 1.3 Bill-and-Hold

**Purpose**

Detect recognition of revenue on undelivered goods.

**Required inputs**

- policy disclosures
- inventory levels
- shipment-related narrative text

**Deterministic trigger logic**

- explicit bill-and-hold or customer-requested holding language
- inventory not declining in line with recognized revenue

**Optional LLM step**

- identify whether policy language is new or newly expanded

**Severity**

- high when both language and inventory inconsistency exist

---

### 1.4 Round-Trip Transactions

**Purpose**

Detect reciprocal transactions that inflate revenue without real economic gain.

**Required inputs**

- related-party transaction disclosures
- counterparty mentions
- mirrored revenue and expense patterns if extractable

**Deterministic trigger logic**

- same counterparty appears as both buyer and seller relationship

**Optional LLM step**

- determine whether disclosure implies economic circularity

**Severity**

- high by default if evidence is credible

---

## Signal Family 2: Earnings Quality

Focus:

- accrual manipulation
- cookie jar reserves
- expense capitalization
- tax manipulation

### 2.1 Accrual Divergence

**Purpose**

Detect divergence between reported earnings and cash reality.

**Required inputs**

- net income
- operating cash flow
- total assets

**Deterministic trigger logic**

- calculate accrual ratio
- compare to predefined thresholds

**Optional LLM step**

- contextualize why the divergence matters
- identify whether management explains the gap credibly

**Severity**

- watch: `0.05-0.10`
- high: `>0.10`

**Minimum evidence contract**

- exact accrual ratio
- source facts for numerator and denominator

---

### 2.2 Cookie Jar Reserves

**Purpose**

Detect reserve releases used to smooth or round earnings.

**Required inputs**

- reserve balances over time
- EPS
- near-miss or beat context

**Deterministic trigger logic**

- reserve reduction coincides with narrow EPS beat or rounded threshold crossing

**Optional LLM step**

- assess whether management explanation is circular or unsupported

**Severity**

- medium to high depending on precision and recurrence

---

### 2.3 Expense Capitalization

**Purpose**

Detect operating expenses being shifted into capital assets.

**Required inputs**

- CapEx
- depreciation
- revenue
- capitalization policy language

**Deterministic trigger logic**

- sustained CapEx/depreciation imbalance
- CapEx/revenue outlier vs internal history or peer set when available

**Optional LLM step**

- analyze whether policy language expanded quietly

**Severity**

- medium to high

---

### 2.4 Tax Manipulation

**Purpose**

Detect earnings support through anomalous tax-rate changes.

**Required inputs**

- effective tax rate
- EPS impact
- tax footnote language

**Deterministic trigger logic**

- sudden ETR decline without clear supporting disclosure

**Optional LLM step**

- evaluate tax footnote complexity and narrative sufficiency

**Severity**

- medium to high

---

## Signal Family 3: Liquidity and Distress

Focus:

- going-concern pre-signal
- covenant stress
- refinancing cliff
- cash runway deterioration

### 3.1 Going-Concern Pre-Signal

**Purpose**

Detect soft distress language before a formal going-concern opinion.

**Required inputs**

- liquidity disclosure text
- auditor report text
- cash runway facts

**Deterministic trigger logic**

- limited deterministic gating only
- presence of liquidity dependency phrases may trigger semantic review

**Optional LLM step**

- identify conditional hedge phrases such as financing assumptions
- determine whether language signals fragile viability

**Severity**

- medium when hedged
- high when hedged plus weak cash runway or auditor signal

**Review conditions**

- LLM-only interpretation without strong supporting facts

---

### 3.2 Covenant Stress

**Purpose**

Detect companies approaching debt covenant breach.

**Required inputs**

- covenant threshold
- actual leverage or coverage ratio
- EBITDA headroom

**Deterministic trigger logic**

- headroom below defined threshold
- deterioration trend toward breach

**Optional LLM step**

- translate covenant math into investor significance

**Severity**

- medium if headroom narrowing
- high if headroom minimal or one-quarter deterioration implies breach risk

---

### 3.3 Cash Runway Deterioration

**Purpose**

Estimate when cash may run out if burn persists.

**Required inputs**

- cash balance
- operating or free cash burn

**Deterministic trigger logic**

- runway months below configured threshold

**Optional LLM step**

- explain assumptions and management dependence on financing

**Severity**

- watch, medium, high based on runway duration

---

## Signal Family 4: Governance and Event Risk

Focus:

- auditor change
- executive departure
- compensation misalignment
- board independence weakness

### 4.1 Auditor Change

**Purpose**

Flag one of the strongest distress or fraud-adjacent signals.

**Required inputs**

- 8-K item classification
- auditor-related sections
- prior filing narrative context

**Deterministic trigger logic**

- `8-K Item 4.01` detected

**Optional LLM step**

- determine whether disagreements or warning signs were foreshadowed

**Severity**

- high by default

---

### 4.2 Executive Departure Risk

**Purpose**

Interpret unusual executive exits, especially when paired with other stress signals.

**Required inputs**

- `8-K Item 5.02`
- executive role
- recent filing signals

**Deterministic trigger logic**

- executive departure event exists

**Optional LLM step**

- sequence-level interpretation with other recent changes

**Severity**

- low standalone
- medium or high when chained with other warning signals

---

### 4.3 Compensation Misalignment

**Purpose**

Detect pay structure disconnected from company performance.

**Required inputs**

- proxy compensation values
- EPS or performance metrics
- board composition

**Deterministic trigger logic**

- CEO compensation increases while key performance metrics decline materially

**Optional LLM step**

- evaluate whether governance narrative justifies the mismatch

**Severity**

- medium by default

---

## Signal Family 5: Narrative and Disclosure Quality

Focus:

- buried risks
- passive voice evasion
- metric switching
- unexplained disclosure expansion

### 5.1 Buried Risk Language

**Purpose**

Identify risks technically disclosed but obscured through weak wording.

**Required inputs**

- risk-factor sections
- prior-year section comparisons

**Deterministic trigger logic**

- risk length or density shift can gate review

**Optional LLM step**

- assess whether language is non-committal, vague, or evasive

**Severity**

- medium unless combined with hard financial stress

---

### 5.2 Metric Switching

**Purpose**

Detect when management quietly pivots away from less favorable metrics.

**Required inputs**

- current and prior MD&A
- disclosed performance metrics

**Deterministic trigger logic**

- previously reported metric absent or de-emphasized
- alternate adjusted metric newly foregrounded

**Optional LLM step**

- explain why the switch may matter

**Severity**

- medium

---

## Sequence Signals

Some of the strongest FilingLens outputs are not single-document signals.

Examples:

- going-concern hedge in 10-K followed by auditor change 8-K
- revenue spike plus DSO rise plus inventory build
- risk-factor sentence inflation plus CFO departure
- three-quarter positive net income with negative operating cash flow

These should write to `signal_sequences`, not just `detected_signals`.

---

## Activation Policy

Recommended pipeline policy:

1. run deterministic signal engines first
2. gate semantic analysis on threshold or candidate activation
3. attach evidence before final verdict
4. route weak-confidence outputs to review

This is the main cost and quality control mechanism.

---

## Evidence Contract

Every material signal shown to users should have:

- numeric evidence where applicable
- source section citations
- explicit detection method
- severity and confidence
- generated investor follow-up question when useful

If a signal lacks evidence, it is not product-ready.

---

## Go-Forward Rule

A new FilingLens signal should not be added unless it answers:

- what deterministic substrate does it require?
- what exact evidence supports it?
- what makes it distinct from existing signals?
- what user decision does it improve?
- can it be explained clearly to a non-expert investor?

If those answers are weak, the signal definition is premature.

---

*FilingLens Signal Library v1 - first detection and evidence contract baseline*

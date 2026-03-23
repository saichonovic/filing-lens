# FilingLens Bootstrap Plan v1
## Standalone Project Bootstrap for Financial Filing Intelligence
**Version:** 1.0  
**Status:** Implementation bootstrap baseline  
**Companion docs:** `FILINGLENS_CORE_SCHEMA_V1.md`, `FILINGLENS_ETL_FLOW_V1.md`, `FILINGLENS_DOCETL_PLACEMENT_V1.md`, `FILINGLENS_SIGNAL_LIBRARY_V1.md`

---

## Goal

Start a clean standalone FilingLens project that can:

- ingest SEC filings and preserve raw source artifacts
- build canonical issuer, filing, section, and fact records
- detect high-value investor risk patterns using deterministic rules first
- layer LLM analysis only where interpretation or ambiguity matters
- later support hosted automation, alerts, and product surfaces

This bootstrap assumes FilingLens is built as a fresh project, not inherited from the parked BungeLens implementation.

---

## 1. Recommended Project Shape

Suggested root:

```text
filinglens/
  app/
  pipeline/
  parsers/
  extractors/
  resolvers/
  signals/
  derivations/
  review/
  models/
  migrations/
  scripts/
  docs/
  tests/
  storage/
    raw/
    extracted/
    processed/
    exports/
```

### Suggested responsibilities

- `app/`
  - config, DB setup, API layer later
- `pipeline/`
  - `acquire.py`
  - `extract.py`
  - `normalize.py`
  - `resolve.py`
  - `derive.py`
  - `publish.py`
- `parsers/`
  - SEC metadata and filing-structure parsers
- `extractors/`
  - deterministic financial table, section, and policy extraction
- `resolvers/`
  - issuer identity, period alignment, prior-filing matching
- `signals/`
  - deterministic rule engines for filing-risk patterns
- `derivations/`
  - investor summaries, alert payloads, watchlist outputs, chat artifacts
- `review/`
  - review queue and conflict handling for ambiguous outputs
- `models/`
  - schema and table contracts
- `scripts/`
  - CLI entrypoints, backfills, maintenance jobs
- `docs/`
  - local implementation contract docs

---

## 2. Phase 1 Stack Assumption

Use:

- Python
- Postgres
- local filesystem-backed document storage initially
- Python ETL runners
- run logging from day one
- deterministic extraction before DocETL
- virtual-environment-only dependency installation

Defer:

- polished frontend
- subscription billing implementation
- full auth and tenancy
- advanced deployment topology
- vector retrieval beyond product-necessary baseline

---

## 3. Canonical Docs To Include Immediately

Create or maintain these in the project root:

- `FILINGLENS_BOOTSTRAP_PLAN_V1.md`
- `FILINGLENS_CORE_SCHEMA_V1.md`
- `FILINGLENS_ETL_FLOW_V1.md`
- `FILINGLENS_DOCETL_PLACEMENT_V1.md`
- `FILINGLENS_SIGNAL_LIBRARY_V1.md`

These become the local implementation contract.

---

## 4. First Migrations To Create

Create Phase 1 tables first:

1. `issuers`
2. `filings`
3. `filing_documents`
4. `analysis_runs`
5. `filing_sections`
6. `filing_periods`
7. `financial_facts`
8. `policy_disclosures`
9. `review_queue`
10. `detected_signals`
11. `signal_evidence`

Do not create the entire long-term product schema immediately.

Reason:

- smaller migration surface
- earlier validation of filing ingestion design
- less schema churn before first successful multi-filing analysis

---

## 5. First Working Deliverable

The first meaningful milestone should be:

> ingest one issuer's latest 10-K, prior 10-K, latest 10-Q, and recent 8-K set, then produce:

- canonical issuer and filing records
- sectioned text and structured financial facts
- deterministic risk signal outputs
- one investor summary with citations
- one year-over-year comparison
- one cross-document sequence analysis

This validates the FilingLens core without requiring the entire product surface.

---

## 6. First Parsers To Implement

Implement in this order:

1. `parsers/sec_filing_index.py`
2. `parsers/filing_metadata.py`
3. `extractors/section_parser.py`
4. `extractors/financial_facts.py`
5. `extractors/policy_disclosures.py`
6. `resolvers/prior_filing_match.py`
7. `signals/channel_stuffing.py`
8. `signals/accrual_quality.py`
9. `signals/covenant_stress.py`
10. `signals/auditor_and_management_events.py`

Reason:

- issuer and filing identity must stabilize first
- section and fact extraction create the deterministic substrate
- signal engines should only run after comparable normalized data exists

---

## 7. First Pipeline Commands

Implement simple, narrow, idempotent commands such as:

```text
python -m scripts.acquire --issuer AAPL --form 10-K --limit 2
python -m scripts.extract --filing-id <id>
python -m scripts.normalize --filing-id <id>
python -m scripts.resolve --issuer-id <id>
python -m scripts.derive --issuer-id <id> --signals channel_stuffing,accrual_quality
```

Principles:

- per-stage
- per-filing or per-issuer scope
- safe to rerun
- easy to log in `analysis_runs`

---

## 8. Review Queue From Day One

Even before a UI exists, support:

- `review_queue` rows in the database
- internal CLI or export for inspection
- conflict logging

Do not postpone ambiguity handling.

Examples of review-worthy cases:

- prior-year filing match is uncertain
- section alignment confidence is weak
- LLM inferred a policy change not deterministically supported
- signal severity depends on a noisy footnote interpretation

---

## 9. DocETL Integration Point

Do not wire DocETL first.

Integrate DocETL only after:

- filings ingest cleanly
- section segmentation is stable
- financial facts are reliably extracted
- issuer identity and period alignment work
- baseline deterministic signals are implemented

Then add DocETL first for:

1. management-language analysis
2. buried-risk and hedge-language extraction
3. cross-document sequence narratives
4. investor-facing summary generation

---

## 10. Immediate Build Sequence

1. Create standalone repo/project structure
2. create the canonical docs
3. configure Postgres connection and settings
4. create Phase 1 migrations
5. implement `issuers`, `filings`, and `analysis_runs`
6. implement acquire/extract pipeline
7. implement filing metadata and section parsing
8. implement financial fact extraction
9. implement policy disclosure extraction
10. implement prior-filing matching
11. implement baseline deterministic signals
12. validate one issuer across multiple filing types
13. only then add DocETL semantic pipelines

---

## 11. What To Postpone Deliberately

Postpone:

- full watchlist product UX
- billing/subscriptions
- multi-tenant SaaS complexity
- generalized chat over the whole corpus
- API partnerships
- large-scale alert routing integrations
- peer benchmarking beyond a narrow initial slice

These should not shape the first working ingest.

---

## 12. Definition of Success For Bootstrap

Bootstrap is successful when the standalone project can:

- ingest a small SEC filing set for one issuer
- preserve source artifacts and extracted text
- create stable issuer and filing records
- parse sections and structured facts deterministically
- align current and prior filings safely
- detect high-value signals with evidence and severity
- rerun pipelines safely
- route ambiguity into review instead of silent canonical writes

At that point, FilingLens has a real deterministic backbone and DocETL can be added without destabilizing core truth.

---

## Go-Forward Rule

If a bootstrap task does not improve one of the following, it should probably wait:

- ingestion reliability
- canonical filing schema population
- fact extraction quality
- cross-filing comparability
- signal detection quality
- provenance
- idempotency
- reviewability

That is the correct filter for Phase 1.

---

*FilingLens Bootstrap Plan v1 - clean standalone implementation starting point*

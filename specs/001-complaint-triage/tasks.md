# Implementation Tasks: Complaint Triage and Insights

**Status:** Active implementation plan
**Source of truth:** SDD v1 documents and architecture.

## Milestone 1 — Project foundation

- [x] Create Python package, packaging metadata, quality-tool configuration, and CLI entry point.
- [x] Implement shared typed domain contracts for triage input, report date validation, action/status enums, and safe caller request IDs.
- [x] Add unit tests for the initial domain contracts.

## Milestone 2 — Data foundation and analytics

- [x] Implement CFPB schema adapter, deterministic row validation, and deduplication.
- [x] Implement snapshot manifest with acquisition, schema, quality, and checksum lineage.
- [x] Integrate local CSV ingestion into curated Parquet and manifest outputs.
- [x] Implement reviewed taxonomy/company mapping loaders with distinct mapped, unmapped, and ambiguous states.
- [x] Add mapping-quality outputs to the curated snapshot workflow.
- [x] Persist curated data as Parquet without narratives.
- [x] Query curated snapshots through read-only DuckDB metric templates.
- [x] Implement report-period, metric-denominator, zero-fill, and company-volume tests.

## Milestone 3 — Safety and audit foundation

- [x] Implement local structured-PII masking with typed placeholders and invariant tests.
- [x] Add a local NLP entity detector for person/location candidates and document measured limitations.
- [x] Implement SQLite application-level append-only hash-chained audit events and integrity verification.
- [x] Implement safe triage failure paths and masked-input audit integration.
- [x] Add safe metadata validation and adversarial prompt-injection fixtures.

## Milestone 4 — Model training and evaluation

- [x] Implement chronological month-level partitioning without split leakage.
- [x] Implement shared masked-text preprocessing for training and inference.
- [x] Train/evaluate TF-IDF plus Logistic Regression baseline with calibration and model card.
- [x] Train/evaluate one improved local candidate on the same locked holdout.
- [x] Implement cost-aware threshold selection with a selective-precision and class-support gate.
- [x] Implement calibration diagnostics, selective-risk metrics, and artifact compatibility checks.

## Milestone 5 — Workflows and reporting

- [x] Implement explicit triage and report workflow state machines.
- [x] Implement chart assets/tables and deterministic Markdown report rendering.
- [x] Implement bounded CFPB/news source retrieval and constrained Gemini commentary with fallback behavior.
- [x] Implement optional Jev benchmark/second-opinion adapter behind the documented safety boundary.

## Milestone 6 — Deliverable verification

- [ ] Complete live-data/provider evidence checks without committing data or keys.
- [x] Render and inspect the required architecture PDF.
- [x] Add reproducible setup/run instructions and final verification evidence.

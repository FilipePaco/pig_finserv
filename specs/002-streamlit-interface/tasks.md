# Implementation Tasks: Streamlit operations interface

**Status:** Pending SDD approval

## Milestone 1 — Foundations

- [x] Add an optional Streamlit dependency group and typed UI configuration.
- [x] Add pure presentation models and safety-focused unit tests.
- [x] Add a localhost-only app entry point with accessible navigation and persistent
  PoC/safety notice.

## Milestone 2 — Analyst workflows

- [x] Implement the Triage form through the existing workflow and clear raw input.
- [x] Implement the Insights form through the existing report workflow and safe tables.
- [x] Implement optional external-context controls and deterministic fallback display.

## Milestone 3 — Review and audit

- [x] Implement append-only review submission with canonical field validation.
- [x] Implement sanitized audit lookup and integrity display.

## Milestone 4 — Delivery verification

- [ ] Add Streamlit interaction/security regression tests.
- [x] Add a Docker Compose `ui` profile and README run instructions.
- [x] Complete a local manual accessibility and safety verification with ignored
  synthetic fixtures.

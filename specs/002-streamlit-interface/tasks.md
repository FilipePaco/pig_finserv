# Implementation Tasks: Streamlit operations interface

**Status:** Pending SDD approval

## Milestone 1 — Foundations

- [ ] Add an optional Streamlit dependency group and typed UI configuration.
- [ ] Add pure presentation models and safety-focused unit tests.
- [ ] Add a localhost-only app entry point with accessible navigation and persistent
  PoC/safety notice.

## Milestone 2 — Analyst workflows

- [ ] Implement the Triage form through the existing workflow and clear raw input.
- [ ] Implement the Insights form through the existing report workflow and safe tables.
- [ ] Implement optional external-context controls and deterministic fallback display.

## Milestone 3 — Review and audit

- [ ] Implement append-only review submission with canonical field validation.
- [ ] Implement sanitized audit lookup and integrity display.

## Milestone 4 — Delivery verification

- [ ] Add Streamlit interaction/security regression tests.
- [ ] Add a Docker Compose `ui` profile and README run instructions.
- [ ] Complete a local manual accessibility and safety verification with ignored
  synthetic fixtures.

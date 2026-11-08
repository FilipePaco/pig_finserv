# Test Strategy: Streamlit operations interface

## Test layers

| Layer | Scope | Key assertions |
| --- | --- | --- |
| Unit | Configuration and presentation adapters | Missing configuration is non-sensitive; view models have no raw narrative/path/key fields. |
| Service | UI-to-core adapters with fakes | Triage/report/review/audit calls use typed values and preserve core failure actions. |
| Streamlit interaction | Critical page forms | Controls are labelled, inputs validate, result state renders, narrative widget is cleared. |
| Regression/security | Triage and error paths | Raw PII/prompt-injection text does not appear in rendered elements, session state, logs, downloads, or exception text. |
| Manual | Local browser and Docker profile | Keyboard navigation, color-independent status, no sensitive UI output, localhost-only binding. |

## Required cases

- Valid triage displays a proposal and audit ID; low confidence displays human review.
- Masked email/phone/account/person values never appear after a submitted form.
- Missing/invalid model, salt, audit DB, Parquet, or output configuration produces a
  safe setup error with no path/secret disclosure.
- Product selection cannot become a SQL fragment; unknown dates/products are rejected
  before report execution.
- Report fallback still displays metrics/charts when optional provider context fails.
- Review creates a distinct correction event; invalid audit IDs do not call storage.
- Audit lookup and integrity views exclude narratives and fingerprints.
- No prohibited download includes narratives, audit rows, raw sources, or artifacts.
- The Compose `ui` profile starts from a clean image and listens only on localhost.

## Completion evidence

The feature is ready when lint/tests pass, the Streamlit interaction suite passes,
Docker Compose can launch the optional UI profile, and a manual local run confirms all
four pages using ignored synthetic fixtures. No fixture data, audit DB, artifacts,
screenshots containing sensitive content, or `.env` is committed.

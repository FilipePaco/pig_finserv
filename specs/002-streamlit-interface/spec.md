# Feature Specification: Streamlit operations interface

**Feature branch:** `012-streamlit-interface`
**Status:** SDD v1 — pending implementation approval
**Depends on:** `001-complaint-triage`

## Problem statement

The command-line workflows prove the PoC contracts but are not an effective
demonstration surface for an operations or insights analyst. Add a local Streamlit
interface that exposes the existing bounded triage, review, audit, and reporting
workflows without creating a second decision path or weakening privacy controls.

## Users and scope

| User | UI capability | Deliberate boundary |
| --- | --- | --- |
| Operations analyst | Submit one complaint, inspect a masked routing suggestion, and record a correction. | The UI never auto-sends a route or displays raw audit text. |
| Risk/insights analyst | Select a product and date, then inspect deterministic metrics, charts, limitations, and vetted citations. | Complaint counts are not population rates or institution ratings. |
| ML/data owner | Inspect a sanitized audit event and verify the local hash chain. | Training, ingestion, taxonomy editing, and artifact promotion remain CLI-only. |

The interface is a localhost PoC operator console. It has no authentication,
multi-user authorization, background jobs, data upload, model training, or external
ticketing capability; it must not be exposed on a public network.

## User stories and acceptance scenarios

### US-1 — Triage a complaint safely (P1)

As an operations analyst, I can enter a narrative and receive the existing proposed
route, confidence, action, masked summary, and audit ID in a readable format.

1. Given a configured valid model, salt, and audit store, submitting text invokes the
   existing `TriageWorkflow` directly and renders its typed result.
2. Given a low-confidence, guardrail, model, or audit failure, the UI renders the
   existing human-review/system-failure action; it never turns it into `AUTO_ROUTE`.
3. Given a narrative with PII or prompt-injection text, only the workflow's masked
   output may be rendered after submission. The UI does not log, cache, download, or
   intentionally retain the narrative in session state after the request completes.
4. The result clearly distinguishes a proposal from an executed customer outcome and
   provides the audit ID needed for subsequent review.

### US-2 — Record a human correction (P1)

As an operations analyst, I can submit a reviewed correction using an audit ID and
see the ID of the immutable correction event.

1. The form accepts only a syntactically valid audit ID, canonical product, permitted
   outcome, allowed reason code, and optional canonical issue.
2. The UI calls the existing `AuditStore.append_review` contract; it cannot mutate the
   original event.
3. A duplicate, missing, malformed, or failed review produces a safe error without
   revealing database paths or raw prior input.

### US-3 — Inspect a product report (P1)

As an insights analyst, I can choose a canonical product and as-of date and inspect
the existing deterministic report in a browser.

1. The product selector is populated from an approved canonical product list, never
   from free-form user text interpolated into a query.
2. The report shows the existing current/previous counts, denominator notes, response
   distribution, top issues/companies, daily/monthly chart images, and accessible
   tables from `ReportWorkflow` output.
3. External context is opt-in and visually labelled as optional commentary. Provider
   failure still renders deterministic facts with the existing limitation.
4. The UI renders vetted source title, publisher, date, and URL; it does not render
   fetched raw pages or claim that a source caused a trend.

### US-4 — Inspect sanitized audit health (P2)

As an ML/data owner, I can look up a sanitized event by audit ID and verify the audit
hash chain.

1. The event view uses the existing sanitizing read path and excludes raw narratives,
   fingerprints, caller identifiers, credentials, and hidden prompts.
2. Integrity verification reports only pass/fail and event count. It does not expose
   database locations or unredacted records.

## Functional requirements

- **FR-UI-001:** The Streamlit layer must call existing domain/workflow objects and
  typed contracts; it must not reproduce model, policy, SQL, PII, audit, or report
  logic in callbacks.
- **FR-UI-002:** Server configuration uses environment variables and fixed local
  paths. Browser inputs must never control filesystem paths, model artifact paths,
  SQL fragments, provider configuration, or shell commands.
- **FR-UI-003:** Triage submits through a form, displays only a typed sanitized
  result, clears the narrative widget after completion, and disables submission while
  work is running.
- **FR-UI-004:** The report view writes any required chart/report files under one
  ignored server-owned local directory with a generated request identifier. It never
  shows that directory path to the browser.
- **FR-UI-005:** The app has four primary pages: **Triage**, **Insights**, **Review**,
  and **Audit**. Navigation and state must be keyboard-accessible.
- **FR-UI-006:** The Insights page offers CSV download only for already-rendered
  deterministic, analytics-safe tables. It must not offer complaint narrative,
  audit-event, source-page, or model-artifact downloads.
- **FR-UI-007:** The app displays a persistent PoC/safety notice: human review is
  required where indicated; outputs are not customer decisions; external commentary
  is non-deterministic and cannot select routes.
- **FR-UI-008:** The Docker configuration provides a separate `ui` service/profile
  that listens on `127.0.0.1` by default, mounts only ignored local runtime files,
  and does not embed `.env`, datasets, audit databases, or model artifacts.

## Non-functional requirements

- **NFR-UI-001 Privacy:** No `st.write`, exception, callback, cache decorator,
  download control, or session-state key may retain or render raw complaint text after
  workflow submission. The browser is an untrusted display boundary.
- **NFR-UI-002 Reliability:** Startup configuration failures and dependency errors
  are actionable but non-sensitive. A reporting/provider issue degrades to the
  deterministic fallback already defined by the core workflow.
- **NFR-UI-003 Accessibility:** Use semantic headings, labels for every control,
  color-independent action status, chart tables, and concise error summaries.
- **NFR-UI-004 Reproducibility:** A clean clone can start the UI through an optional
  `uv` dependency group and Docker Compose profile using documented local fixtures.
- **NFR-UI-005 Testability:** UI orchestration and presentation adapters are
  separately testable from Streamlit widgets; browser-level tests cover critical
  forms and regression-prone safety behavior.

## Explicit non-goals

- Replacing the CLI, changing model training/evaluation, or permitting data upload.
- Adding authentication, multi-tenancy, production deployment, or public hosting.
- Streaming raw LLM output, a chat interface, or provider access to narratives.
- Adding a Jev control to the UI; Jev remains a disabled benchmark-only boundary.

## Resolved design decisions

| ID | Decision | Rationale |
| --- | --- | --- |
| UI-1 | Use Streamlit multipage navigation. | It is fast to demonstrate analyst workflows while keeping Python types and local execution. |
| UI-2 | Invoke the application layer, not Click/Typer commands or subprocesses. | Avoids shell/path injection and keeps one testable decision path. |
| UI-3 | Keep ingest/train/configuration in the CLI. | These are privileged data/ML-owner activities, not analyst interactions. |
| UI-4 | Persist only server-owned generated report assets under ignored `local/`. | Existing charts require files; the UI needs no user-selected paths or persistent raw input. |
| UI-5 | External context is an explicit report checkbox, off by default. | It makes provider use visible, preserves deterministic reporting by default, and contains cost. |
| UI-6 | Ship UI in a Compose profile bound to localhost. | The PoC has no authentication and must not accidentally become an internet-facing service. |

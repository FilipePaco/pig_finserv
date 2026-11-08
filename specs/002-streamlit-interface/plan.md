# Technical Design: Streamlit operations interface

**Status:** SDD v1 — pending implementation approval

## Architecture

```text
Local browser (localhost only)
             |
             v
      Streamlit presentation layer
  pages, form validation, safe status view
             |
             v
      UI application adapters (typed)
       /              |               \
      v               v                v
TriageWorkflow   ReportWorkflow    AuditStore
      |               |                |
      v               v                v
PII guard ->      DuckDB ->       hash-chained
local model ->    charts ->       local audit DB
routing policy    optional Gemini
      |               |
      +-- sanitized typed results --+
```

The browser never directly accesses DuckDB, artifacts, the audit database, a provider,
or a filesystem path. Streamlit is a presentation adapter; all routing, PII masking,
policy, report computation, and audit behavior remain owned by the existing core.

## Proposed module layout

```text
src/pig_finserv/ui/
  __init__.py
  app.py                 # Streamlit entry point and navigation only
  configuration.py       # Typed, environment-backed UI runtime configuration
  services.py            # Narrow adapters to existing workflows/stores
  presentation.py        # Pure result-to-view-model functions
  pages/
    triage.py
    insights.py
    review.py
    audit.py
```

`services.py` receives dependencies through small factories so unit tests can pass
fakes. Page modules only validate UI-level inputs and render view models. They may not
open files based on request values, execute shell commands, or import provider keys.

## Configuration contract

The UI reads server-owned configuration at startup:

| Variable | Purpose | Required for |
| --- | --- | --- |
| `PIG_FINSERV_MODEL_ARTIFACT_DIR` | Verified local model artifact directory. | Triage |
| `PIG_FINSERV_AUDIT_DATABASE` | Local SQLite audit database. | Triage, Review, Audit |
| `PIG_FINSERV_TAXONOMY_VERSION` | Expected artifact taxonomy version. | Triage |
| `PIG_FINSERV_ANALYTICS_PARQUET` | Curated narrative-free snapshot. | Insights |
| `PIG_FINSERV_UI_OUTPUT_DIR` | Ignored, server-owned report/chart output directory. | Insights |
| `PIG_FINSERV_FINGERPRINT_SALT` | Existing local audit secret. | Triage |

Gemini configuration is inherited only by the explicit optional report-context path.
The UI never displays whether a secret is set; it says that optional commentary is
unavailable when the core workflow cannot use it.

## Page behavior

### Triage

1. Read a narrative from a submitted form; do not echo it.
2. Call one service method that delegates to `TriageWorkflow`.
3. Immediately clear the widget/session value through a submit callback.
4. Render a status badge, product/issue proposal, calibrated confidence, masked
   summary, PII-mask state, model/taxonomy/policy versions, and audit ID.
5. Render a human-review instruction for every non-`AUTO_ROUTE` result.

### Insights

1. Read canonical products through a safe configuration/analytics helper and present
   a selector; no free-form query is accepted.
2. Create a server-generated output subdirectory and call `ReportWorkflow`.
3. Render metrics and charts from typed result paths held server-side, plus accessible
   tables and limited CSV downloads.
4. Render existing limitations, optional commentary, and vetted citation metadata.

### Review and Audit

The Review page calls the existing append-only correction contract. The Audit page
uses only sanitized read/integrity methods. Both validate an audit ID before lookup
and display generic errors for unavailable storage.

## Docker delivery

Add a `ui` optional dependency group and a Compose `ui` profile/service. It reuses the
application image, runs `streamlit run`, mounts `./local` at `/app/local`, and binds
`127.0.0.1:8501:8501`. The existing CLI service stays the default and remains usable
without Streamlit.

## Implementation sequence

1. Add the SDD, UI dependency group, typed configuration, and pure presentation tests.
2. Implement the Triage page and safety/regression tests first.
3. Implement Insights with deterministic report rendering and optional-context toggle.
4. Implement Review and Audit pages.
5. Add Docker profile, README instructions, Streamlit interaction tests, and manual
   accessibility/safety verification using only ignored local fixtures.

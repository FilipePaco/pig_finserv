# Agent, Tool, and Guardrail Contract

**Status:** SDD v1 draft
**Principle:** The system uses explicit workflows, not a general-purpose autonomous agent.

## 1. Orchestration model

LangGraph defines two named state machines. Nodes receive and emit typed state; transitions are fixed by application code. An LLM can transform only bounded, pre-assembled data and has no direct access to SQL, the filesystem, shell, network tools, credentials, or routing actions.

| Graph | Initial state | Terminal states |
| --- | --- | --- |
| `triage_graph` | New request ID and in-memory narrative | Auto-route suggestion with audit ID; human-review result with audit ID. |
| `report_graph` | Canonical product and as-of date | Structured report; metrics-only report; typed report failure. |

## 2. Triage graph contract

```text
validate request
  -> detect and mask PII locally
  -> load compatible model artifact
  -> predict and calibrate probabilities
  -> apply deterministic routing policy
  -> optionally create Gemini masked summary
  -> persist append-only audit event
  -> return action and safe response
```

### Node permissions

| Node | Reads | Writes | External access | Failure transition |
| --- | --- | --- | --- | --- |
| Validate request | Request schema | Validated state | None | `HUMAN_REVIEW_EMPTY_INPUT` or typed validation error. |
| PII guard | In-memory narrative | Masked narrative, entity-type counts, fingerprint | None | `HUMAN_REVIEW_GUARDRAIL_FAILURE`. |
| Model inference | Local artifact, normalized local text | Prediction distribution | None | `HUMAN_REVIEW_SYSTEM_FAILURE`. |
| Routing policy | Calibrated distribution, threshold policy | Action and rationale code | None | Review when ineligible. |
| Summary generator | Masked narrative, prediction, safe action | Bounded draft summary | Gemini only | Summary omitted; previous action remains valid. |
| Audit writer | Safe/minimized state | Immutable event | Local SQLite only | `HUMAN_REVIEW_SYSTEM_FAILURE` for any proposed auto-route. |

The Jev client, if enabled, is called after PII masking and before routing policy only in `benchmark` or `review_second_opinion` mode. It cannot change `AUTO_ROUTE` eligibility. Its result is stored as a separately identified optional signal.

## 3. Report graph contract

```text
validate canonical product and as-of date
  -> calculate deterministic metric tables with fixed queries
  -> build daily/monthly chart data
  -> retrieve bounded external source candidates
  -> validate sources and assemble evidence pack
  -> optionally request Gemini commentary
  -> validate structured commentary
  -> render structured report and record lineage
```

### Node permissions

| Node | Reads | Writes | External access | Failure transition |
| --- | --- | --- | --- | --- |
| Validate request | Canonical product catalog, date rules | Validated filters | None | Typed request error. |
| Metrics service | Fixed SQL templates, DuckDB | Metric tables and quality notes | Local read-only store | Typed report failure. |
| Chart service | Metric tables | Chart data and rendered assets | None | Typed report failure. |
| News retrieval | Bounded template, product, date window | Source candidates | CFPB and configured search adapter | Empty evidence pack. |
| Evidence validator | Source candidates | Vetted source records | Optional URL metadata fetch only through adapter | Drop invalid sources. |
| Commentary generator | Structured metrics, limitations, vetted sources | JSON commentary candidate | Gemini only | Commentary unavailable marker. |
| Report renderer | All structured result fields | Markdown/HTML report metadata | Local artifact store | Typed report failure. |

## 4. Tool contracts

### 4.1 `AnalyticsTool`

- Accepts only a `MetricQueryName` enum and typed parameters: canonical product ID, current-period end date, and project timezone.
- Maps the enum to a fixed SQL template using parameter binding.
- Returns typed tables with values, denominator, filters, query version, snapshot ID, and data-quality exclusions.
- Has no generic `execute_sql` method and is unavailable to Gemini/Jev.

### 4.2 `NewsRetrievalTool`

- Builds queries only from fixed templates and canonical product names; no complaint narrative is included.
- Default lookback is 90 days before the report as-of date; a result must have a publisher, URL, publication date, and title.
- Prefers CFPB newsroom/enforcement pages. Additional domains are allowlisted in configuration and must be recorded in report provenance.
- Limits result count to 10 candidates and accepted evidence to 5 sources, deduplicated by canonical URL/title.
- Returns metadata and a bounded excerpt/claim, not unrestricted page content.

### 4.3 `TextGenerationClient`

- Exposes only `generate_triage_summary(payload)` and `generate_report_commentary(payload)`.
- Uses a selected Gemini model configured by environment variable; model ID, API version, and prompt template version are recorded.
- Accepts a schema-validated payload with masked text, numeric values serialized from deterministic results, and evidence records.
- Does not receive raw input, database connection data, secrets, hidden system prompts, or tool handles.
- Validates response against JSON schema; invalid output is discarded or repaired with a bounded static retry that does not add untrusted text to instructions.

### 4.4 `JevDecisionClient` (optional)

- Is disabled by default.
- Accepts only masked, length-limited text and a static typed product-choice definition with label descriptions.
- Records endpoint/model/version, question-set version, response distribution, latency, and request fingerprint; never stores the provider key.
- Operates only in benchmark or review-second-opinion mode until a documented evaluation approves another use.
- Provider confidence is not trusted as a routing threshold without local evaluation.

## 5. PII and sensitive-data controls

The PII guard runs locally before any external call or normal audit write. It combines high-precision patterns for email, phone, SSN-like numbers, payment/account-like identifiers, and dates of birth with NLP entity recognition for person/location candidates. Replacements use typed placeholders such as `[EMAIL_1]`, `[PHONE_1]`, `[ACCOUNT_ID_1]`, and `[PERSON_1]`.

The guard returns only masked text, a salted SHA-256 input fingerprint, and entity counts/types to later nodes. The salt is loaded from local configuration and never emitted. The original narrative is held only in process memory for the permitted local model path and is discarded after the request.

Known limitations must be documented: entity recognition can miss or over-mask names; no de-identification claim is absolute. A detector error, an unhandled encoding failure, or a masking invariant failure stops external use and routes to human review.

## 6. Prompt-injection and content-isolation controls

Complaint narratives, retrieval snippets, page titles, and URLs are untrusted data. The application enforces:

- static task instructions and static output schemas stored separately from untrusted payloads;
- labelled JSON data fields for untrusted content, with explicit `UNTRUSTED_CONTENT` boundaries;
- maximum lengths per narrative, source excerpt, source count, and output field;
- no tool invocation by the LLM; tools run before the LLM and their results are passed as data;
- no LLM-selected SQL, URL, file path, product identifier, model version, or route action;
- deterministic validation that commentary contains only allowed fields and cited source IDs;
- adversarial fixtures that attempt instruction override, secret extraction, tool use, SQL injection, and defamatory claims.

## 7. Output contracts

### Triage response

| Field | Description |
| --- | --- |
| `audit_id` | Immutable event identifier. |
| `action` | One value from the fixed action vocabulary in `ml-design.md`. |
| `predicted_product` | Canonical label or `null` when unavailable. |
| `predicted_issue` | Optional canonical label or `null`. |
| `confidence` | Calibrated selected-product probability or `null`. |
| `summary` | Optional masked, explicitly labelled draft. |
| `model_version` | Artifact identifier. |
| `guardrail_status` | Pass, masked, or failure reason code. |

### Report commentary JSON

The model returns only `headline`, `observations`, `contextual_notes`, `limitations`, and `citation_ids`. Each observation must reference one supplied metric ID. Each contextual note must reference one supplied source ID and use neutral language such as “the source reported” or “may be relevant context”; causal wording is disallowed. The renderer independently includes all deterministic metrics, charts, denominators, and source URLs.

## 8. Provider configuration and resilience

Secrets are read from environment variables or a local ignored `.env`; names only appear in `.env.example`. Each provider client has finite timeouts, bounded retries for transient errors, and typed exceptions. The system records provider/model/version/latency without recording secrets or raw content.

| Dependency failure | Triage behavior | Reporting behavior |
| --- | --- | --- |
| Gemini unavailable | Return decision without summary. | Render metrics/charts with “commentary unavailable.” |
| Jev unavailable | Ignore optional result. | Not used. |
| News adapter unavailable | Not used. | Render metrics/charts with no external context. |
| DuckDB unavailable | Route to review; create health event if possible. | Return typed failure; do not invent numbers. |
| Model/artifact invalid | Route to review. | Not used. |
| Audit store unavailable | Do not auto-route. | Report may render with a lineage warning only if artifact persistence succeeds. |

## 9. Agent acceptance gates

1. Every graph transition is deterministic and covered by an automated test.
2. Mocked external clients prove raw PII never leaves the guard boundary.
3. Prompt-injection fixtures cannot alter route, SQL, tool permissions, or output schema.
4. Gemini/Jev outages result in defined degraded outcomes.
5. Every successful or failed triage attempt produces a safe audit result or is blocked from automatic routing.

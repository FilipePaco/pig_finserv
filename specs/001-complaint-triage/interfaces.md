# Interface and Artifact Contract

**Status:** SDD v1 draft
**Delivery decision:** The CLI is the required interface. A Streamlit interface is a post-MVP enhancement that must reuse these contracts.

## 1. CLI design principles

- Each command has typed arguments, deterministic exit codes, human-readable output, and optional JSON output for automation.
- Commands never print provider keys, raw narratives, or unrestricted audit payloads.
- Commands that modify local artifact/data stores require explicit output paths and refuse paths outside the configured project data/artifact roots.
- A command failure is actionable: it states the failed contract, safe remediation, and correlation/audit ID when available.
- The CLI is not a shell for free-form SQL, URL retrieval, or arbitrary provider prompts.

## 2. Command surface

| Command | Required inputs | Output | Mutates |
| --- | --- | --- | --- |
| `ingest` | Source mode/config, date window | Snapshot ID, manifest path, quality summary | Curated local data and manifest. |
| `train` | Snapshot ID, model config | Model ID, model card, evaluation paths | Local model artifact store. |
| `evaluate` | Model ID, snapshot ID | Evaluation report and comparison summary | Evaluation artifact only. |
| `triage` | Narrative via secure stdin/file, optional request ID | Triage response and audit ID | Local audit store; optional summary artifact. |
| `review` | Audit ID, corrected product, optional issue/reason | Correction event ID | Local audit store. |
| `report` | Canonical product, as-of date, output directory | Report ID, Markdown/HTML, chart assets, provenance | Local report artifact store. |
| `inspect-audit` | Audit ID | Sanitized event view | None. |
| `validate` | Snapshot/model/report target | Contract validation summary | None. |

The exact command framework is deferred; names and input/output behavior are fixed by this specification.

## 3. Triage request and response

### Request

```json
{
  "request_id": "optional-client-correlation-id",
  "narrative": "Consumer-provided complaint text"
}
```

`request_id`, when supplied, must be an opaque UUID-like identifier and is otherwise discarded rather than persisted. `narrative` must be non-empty after Unicode/whitespace normalization and no longer than the configured request limit. It is read from secure stdin or a local ignored file by default; it must not be provided as a shell argument, which could expose it to shell history/process listings.

### Response

```json
{
  "audit_id": "triage_...",
  "action": "AUTO_ROUTE",
  "predicted_product": "Credit card",
  "predicted_issue": null,
  "confidence": 0.93,
  "summary": {
    "status": "AVAILABLE",
    "text": "Draft summary generated from masked text only."
  },
  "model_version": "product-tfidf-lr-v1",
  "taxonomy_version": "2026.1",
  "guardrail_status": "MASKED",
  "review_reason": null
}
```

`summary.text` is always labelled as a draft. A human-review response may have `predicted_product` and `confidence` for operator assistance, but it is never represented as a final route.

## 4. Audit-event contract

Audit events use application-enforced append semantics, not a claim of tamper-proof storage. The application exposes no update/delete operation for original events. Each successful insert has a monotonically increasing sequence number, prior-event hash, and canonical event hash; an integrity command verifies the chain. Direct filesystem/database access remains outside the PoC threat model and is not represented as impossible.

| Field | Required | Notes |
| --- | --- | --- |
| `audit_id` | Yes | Generated immutable ID. |
| `occurred_at` | Yes | UTC timestamp. |
| `request_id` | No | Opaque UUID-like client correlation ID only; otherwise discarded. |
| `input_fingerprint` | Yes | Salted hash; never raw narrative. |
| `masking_status` and `masked_entity_counts` | Yes | No entity values. |
| `snapshot_id`, `model_version`, `taxonomy_version` | Conditional | Required when model inference runs. |
| `predicted_product`, `predicted_issue`, `probability_distribution` | Conditional | Canonical labels/scores only. |
| `threshold_policy_version`, `action`, `reason_code` | Yes | Decision lineage. |
| `provider_metadata` | No | Provider/model/version/latency only. |
| `summary_status` | Yes | Available, unavailable, skipped, or invalid. |
| `parent_audit_id` | No | Used by human correction events. |
| `event_sequence`, `previous_event_hash`, `event_hash` | Yes | Application-level tamper-evident chain metadata. |
| `review_correction` | No | Canonical product/issue, outcome enum, and allowlisted reason code only; no free text. |

Malformed requests create a minimal safe audit event with `REJECTED_INVALID_REQUEST`, no raw payload, and no caller-controlled metadata. A parsed empty narrative creates `HUMAN_REVIEW_EMPTY_INPUT`. If the audit store itself is unavailable, the application returns `HUMAN_REVIEW_SYSTEM_FAILURE` with a transient correlation ID and creates no auto-route; it emits only a non-sensitive operational health signal because an immutable event cannot be persisted. Audit exports default to aggregate/sanitized form. Access to any masked narrative stored for a short review session is not in scope for the public PoC and must not be committed.

## 5. Report request and structured result

### Request

```json
{
  "product": "Credit card",
  "as_of_date": "2026-10-31",
  "timezone": "America/New_York"
}
```

The product must resolve to exactly one canonical product. The as-of date may have zero complaints; it is valid when it is a completed date no later than the snapshot's latest completed date and the snapshot contains the required 12-month historical window. The CLI rejects dates after the available snapshot, dates without sufficient historical coverage, arbitrary filter text, raw SQL, and unrecognized timezone identifiers.

### Required structured result

| Section | Required contents |
| --- | --- |
| Metadata | Report ID, snapshot ID, request filters, period boundaries, timezone, query/prompt/source versions, generated timestamp. |
| Volume comparison | Current count, previous count, absolute change, percentage change or `N/A`, definition. |
| Timely response | Yes count, known-response denominator, rate, unknown/excluded count. |
| Company responses | Counts and shares by response category, known-response denominator, excluded count. |
| Top issues | Top five issues, count, selected-product share, unknown-issue treatment. |
| Top companies | Top five companies, count, selected-product share, alias status, company-size limitation. |
| Charts | Accessible daily 30-day table/chart and monthly 12-month table/chart. |
| External context | Vetted sources with URL, publisher, publication date, retrieval date, and source ID; may be empty. |
| Commentary | Validated optional generated text, clearly separated from deterministic facts. |
| Limitations | Dataset scope, representativeness, taxonomy, company-size, data quality, and retrieval caveats. |

## 6. Chart contract

Every chart has a PNG or SVG asset plus a CSV/Markdown table generated from the same query output.

| Chart | Granularity | Range | Required behavior |
| --- | --- | --- | --- |
| Daily complaints | Calendar day | 30 completed days | Include zero-count days, labelled axes, title, and selected product. |
| Monthly complaints | Calendar month | 12 completed months | Include zero-count months, whole-month labels, title, and selected product. |

Charts use color-independent labels and an accessible description. Visual styling must not obscure values or imply statistical significance not established by the data.

## 7. Report commentary constraints

The renderer accepts commentary only if it satisfies the schema in `agent-contract.md`. It must:

- use supplied metric IDs rather than restating unverified numbers;
- cite supplied source IDs for external statements;
- distinguish observation from external context;
- avoid causal, legal, or reputational claims about companies;
- include no instruction from untrusted content, provider metadata, raw text, or hidden prompt content.

The report always remains usable if commentary is absent.

## 8. Exit-code policy

| Exit class | Meaning |
| --- | --- |
| `0` | Command completed; triage may still have a valid human-review action. |
| `2` | Invalid user input or configuration. |
| `3` | Data/schema/lineage contract failure. |
| `4` | Model/artifact contract failure. |
| `5` | External provider/retrieval failure where no safe fallback exists. |
| `6` | Internal unexpected failure; safe error details only. |

## 9. Deferred Streamlit interface

If added, Streamlit provides two screens: a triage-review screen and a report-explorer screen. It must call the same application service contracts, display the same safe outputs/limitations, and add no direct provider or database access. Its addition requires accessibility, security, and end-to-end test cases before release.

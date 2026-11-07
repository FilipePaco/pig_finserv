# Feature Specification: Agentic consumer complaint triage and insights

**Feature branch:** `001-complaint-triage`
**Status:** SDD v1 draft — implementation blocked pending review
**Source:** Challenge brief in `../09-cfpb-complaint-triage-ml.md`

## Problem statement

Pig FinServ needs a PoC that (a) routes an incoming free-text consumer complaint to the appropriate product/issue team while escalating uncertain cases, and (b) gives an analyst a safe, evidence-based trend report for a selected product. CFPB data is historical and partly redacted; it is a proxy dataset, not evidence about an individual institution's current performance.

## Users

| User | Need | Boundary |
| --- | --- | --- |
| Operations analyst | See predicted routing, confidence, masked summary, and reason for review. | Must make final decision for escalated cases. |
| Risk/insights analyst | Request a product report and inspect figures, chart data, and citations. | Cannot infer causality or company quality from ranking alone. |
| ML/data owner | Reproduce dataset/model/report lineage and assess errors. | Does not receive raw production narratives through logs. |

## User stories and acceptance scenarios

### US-1 — Triage a complaint (P1)

As an operations analyst, I submit a complaint narrative and receive a proposed product route, optional issue route, calibrated confidence, action, and masked draft summary.

**Acceptance scenarios**

1. Given valid narrative text, when the prediction meets every approved routing-policy gate (calibrated threshold, cost eligibility, class-support rule, and healthy guard/audit dependencies), then the system returns `AUTO_ROUTE`, model/taxonomy versions, predicted product, confidence, and a summary generated only from masked text.
2. Given a prediction below threshold, an unseen/unsupported label, empty text, or failed masking step, then the system returns `HUMAN_REVIEW`; it does not auto-route.
3. Given text containing email, phone, account-like identifier, or a likely personal name, when any LLM or persisted audit record is produced, then the exposed text contains placeholders rather than the detected value.
4. Given a narrative that asks the system to ignore instructions, disclose secrets, or call a tool, then it is classified as data, no instruction/tool behavior changes, and the audit action follows confidence policy.

### US-2 — Audit a triage decision (P1)

As an ML/data owner, I can reconstruct why and when a routing action was suggested without recovering sensitive text from normal logs.

**Acceptance scenarios**

1. Every valid or safely rejected request creates an append-only, tamper-evident event containing event ID/time, salted input fingerprint when available, PII-mask status/counts, model/taxonomy version, scores, chosen action, threshold version, and outcome/reviewer correction when available. If audit storage is unavailable, automatic routing is blocked and a non-sensitive health signal records the persistence failure.
2. An audit export excludes raw input, LLM credentials, and hidden prompt content.
3. A model artifact can be traced to its data snapshot, schema/taxonomy mapping, split boundaries, hyperparameters, metrics, calibration method, and threshold decision.

### US-3 — Generate a product trend report (P1)

As an insights analyst, I select a canonical product and receive a report grounded in the complaint dataset and cited external context.

**Acceptance scenarios**

1. The report shows current-vs-previous complaint volume change, timely-response rate, company-response distribution, top five issues, and top five companies; all metrics state their denominator and null/unknown handling.
2. The report includes a daily complaint chart covering the last 30 completed calendar days and a monthly chart covering the last 12 completed calendar months, with accessible tabular data.
3. A company leaderboard shows count plus share of complaints in the selected product/period. It displays a limitation that this is not normalized by customer base unless an approved exposure dataset is added.
4. Commentary uses only returned metric values and dated, cited search/news evidence. It distinguishes observation from contextual correlation and contains no unsupported allegation.
5. If news retrieval fails or yields no reliable evidence, the report still emits deterministic metrics/charts and says that no external context was included.

### US-4 — Train and evaluate the classifier (P1)

As an ML/data owner, I can train an auditable product classifier and evaluate its ability to generalize to later complaints.

**Acceptance scenarios**

1. Training rows require a non-empty narrative and valid canonical target. Taxonomy mappings are versioned and keep the original category.
2. The split is chronological by `date_received`: training is older data, validation/calibration is a later slice of training history, and the untouched test set is most recent. No text or fitted preprocessing leaks across partitions.
3. The evaluation report includes macro-F1, per-class support/F1, confusion matrix, calibration diagnostic, coverage/auto-route rate, and review rate on the same chronological test set.
4. At least a TF-IDF + logistic-regression baseline is compared with one improved candidate. The selected model is justified by metrics and operational cost, not only aggregate accuracy.

## Functional requirements

- **FR-001:** Ingest CFPB bulk/API records into a versioned local snapshot, retaining only fields needed for analysis/training and recording query/download metadata.
- **FR-002:** Normalize product/issue taxonomy across historical CFPB changes using a documented, versioned mapping; unknown/ambiguous mappings are retained and excluded from supervised labels according to policy.
- **FR-003:** Detect and mask PII locally before externally processed text or durable audit text; fail closed to review if masking fails.
- **FR-004:** Train a product classifier and, if coverage/quality permits, a separate or hierarchical issue classifier. Product remains the required routing decision.
- **FR-005:** Calibrate confidence on a temporally later validation partition and select threshold(s) by a documented review-versus-misroute cost policy.
- **FR-006:** Write an append-only, hash-chained triage audit event for valid/safely rejected attempts and human corrections. Audit persistence failure blocks automatic routing and yields a safe system-failure response.
- **FR-007:** Offer only canonical product values for reporting; compute metrics through read-only parameterized queries against the analytical store.
- **FR-008:** Retrieve external context through a bounded news/CFPB-search tool, retain source provenance, and make a report without it when unavailable.
- **FR-009:** Generate two required charts directly from query outputs and a PDF architecture diagram documenting agent, classifier, LLM, database, and news tool interactions.
- **FR-010:** Keep all provider keys outside source control. Gemini is the initial constrained text-generation provider; Jev is an optional decision-model adapter behind a separate small interface.

## Non-functional requirements

- **NFR-001 Privacy:** Raw production-like narrative is never sent to an LLM or written to standard application/audit logs.
- **NFR-002 Reliability:** Triage defaults to human review on dependency, schema, model, or guardrail failure; reporting can degrade to metrics-only.
- **NFR-003 Performance (PoC target):** Triage completes within 5 seconds excluding an optional LLM summary; deterministic report metrics for one product complete within 30 seconds on the documented local snapshot.
- **NFR-004 Reproducibility:** A clean environment can regenerate a documented bounded data snapshot, model evaluation, report data, charts, and architecture PDF using pinned dependencies and commands.
- **NFR-005 Accessibility:** Charts have descriptive titles, labeled axes, color-independent encoding, and data tables/export.

## Canonical reporting definitions

| Measure | Proposed definition |
| --- | --- |
| Current period | 30 completed local calendar days ending at the requested as-of date, inclusive. The as-of date may have zero complaints. |
| Previous period | The immediately preceding 30 calendar days. |
| Volume change | `(current_count - previous_count) / previous_count`; show `N/A` when prior count is zero and show both counts. |
| Timely response rate | `timely_response = Yes` / records with a known Yes/No timely response in current period. |
| Response distribution | Count and share by `company_response_to_consumer`; denominator is records with a known response in current period. |
| Top issues | Top five canonical issues by current-period count; show share of all current-period selected-product complaints. |
| Top companies | Top five canonicalized company names by current-period count and selected-product share; not customer-base normalized. |
| Daily chart | Counts per received date over current 30-day period, including zero-count dates. |
| Monthly chart | Counts per calendar month for 12 completed months ending with the as-of date's completed month, including zero-count months. |

## Out of scope for this PoC

- Sending messages, decisions, or routing tickets to real institutions.
- Training directly on raw production customer data or performing online learning.
- Claiming root cause/correlation from complaint counts or rating companies.
- Building a general-purpose autonomous agent with arbitrary web, SQL, shell, or file-system access.
- Exposure/customer-base normalization without a validated denominator dataset and methodology.

## Resolved MVP decisions

| ID | Decision | SDD v1 resolution |
| --- | --- | --- |
| D-1 | Jev use | Optional masked-text zero-shot benchmark or review-only second opinion. It is not the trained classifier or routing decision owner. |
| D-2 | Delivery surface | CLI is required. Streamlit is deferred until the CLI path is complete and tested. |
| D-3 | Dataset scope | Use a reproducible rolling 36 completed-month snapshot; use deterministic smaller fixtures for development tests. |
| D-4 | Product categories | Preserve the full reviewed canonical taxonomy. Exclude unmapped/ambiguous targets; do not silently collapse classes for performance. |
| D-5 | Cost policy | Select the threshold using calibration data at a 1:10 review:misroute ratio, report 1:5 and 1:20 sensitivity, and enforce selective-precision/support safety floors. |

## Assumptions and risks

- CFPB schemas/taxonomies vary across snapshots; ingestion must inspect and validate rather than assume columns.
- Published narratives are not a promise of complete PII removal; masking applies to them as well.
- Complaint counts are not population rates; company rankings may reflect scale, reporting behavior, and dataset coverage.
- News results can be irrelevant, stale, or adversarial. They are evidence candidates, not facts until source/claim checks pass.
- A public GitHub repository cannot contain any API key, raw sensitive input, or unlicensed large data snapshot.

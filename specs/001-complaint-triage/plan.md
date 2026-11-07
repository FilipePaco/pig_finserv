# Technical Design: Agentic consumer complaint triage and insights

**Status:** SDD v1 draft — implementation blocked pending review
**Implementation:** Not started

## 1. Architecture at a glance

```text
                     ┌──────────────────────────────────────┐
CFPB bulk/API ──────►│ Ingestion + schema checks + taxonomy  │
                     │ mapping + snapshot manifest           │
                     └──────────────┬───────────────────────┘
                                    ▼
                             Parquet + DuckDB
                              (read-only query)
                                    │
        ┌───────────────────────────┼──────────────────────────┐
        ▼                           ▼                          ▼
 training/evaluation          Report metrics             product lookup
        │                           │                          │
 classifier registry       chart renderer             report orchestrator
        │                           │                    ┌─────┴─────┐
        ▼                           └───────────────────►│ news tool │
 triage orchestrator                                  │ (allowlist)│
        │                                               └─────┬─────┘
 raw narrative → local PII mask → classifier → policy          │
        │                   │                  │               ▼
        │                   │                  ▼     constrained LLM
        │                   │           append-only audit       │
        └───────────────────┴─────────────────────────────────┘
                            masked, bounded inputs only
```

The final PDF diagram will be derived from this approved architecture and verified as part of the implementation phase.

## 2. Proposed components and responsibilities

| Component | Responsibility | Trust boundary / failure behavior |
| --- | --- | --- |
| `ingest` | Fetch/download, validate schema, deduplicate, create Parquet snapshot and manifest. | No LLM. Reject invalid schema; preserve raw source externally/locally according to data policy. |
| `taxonomy` | Version mappings from source product/issue labels to canonical labels. | Deterministic; ambiguous input becomes `UNMAPPED`, never guessed. |
| `pii_guard` | Local recognizer + conservative regexes for email/phone/account/card/SSN/date/name candidates; replace with typed tokens. | Fail closed: triage to review, no LLM/log text. |
| `modeling` | Chronological split, vectorizer/model fitting, calibration, evaluation, artifact registry. | Fits every transform on training only. No provider dependency. |
| `triage_service` | Calls guard → model → policy → optional masked summary → audit writer. | No auto-route on model/guard/audit failure. |
| `analytics` | Parameterized DuckDB queries and chart-ready tables. | Read-only; product selected from canonical enum. |
| `news_retrieval` | Builds bounded product/topic queries, retrieves a small dated result set from CFPB and approved source provider. | URL/domain/recency limits; absence of results is valid. |
| `report_orchestrator` | Combines structured metrics, chart metadata and vetted sources into constrained LLM commentary. | LLM cannot query DB or web; metrics-only fallback. |
| `audit` | Append-only local event store and export sanitizer. | Stores fingerprint/masked minimal fields, never raw narrative/key. |

## 3. Data design and lineage

### 3.1 Minimum retained fields

`complaint_id`, `date_received`, `date_sent_to_company` (if present), `product`, `sub_product`, `issue`, `sub_issue`, `company`, `state`, `zip_code` (excluded from reports unless needed), `submitted_via`, `company_response_to_consumer`, `timely_response`, `consumer_disputed` (if present), `complaint_what_happened` (restricted training input), source row fingerprint, and snapshot ID.

The implementation will record an explicit field allowlist and data-retention rationale. Location and narrative are excluded from default reporting output.

### 3.2 Snapshot manifest

Each ingest writes a JSON manifest with source URL/API parameters, retrieval time, source file checksum, row counts before/after validation/deduplication, schema mapping, taxonomy version, date min/max, and output checksum. Trained artifacts and reports reference this immutable ID.

### 3.3 Company canonicalization

Use a deterministic alias table with a `company_canonicalization_version`; retain source name. Do not fuzzy-match automatically unless a mapping is reviewed and recorded. Leaderboards show canonical name plus source-name aggregation note.

## 4. ML design

### 4.1 Candidates

1. **Baseline:** word + character TF-IDF with multinomial logistic regression, class weighting, and canonical product target.
2. **Improved candidate:** evaluated after data profiling; candidate choices are TF-IDF with linear SVM plus probability calibration, or sentence embeddings with a regularized classifier. The candidate must be feasible locally and documented.
3. **Bonus issue model:** conditional issue classifier per predicted/known product only if each target has sufficient support and product error propagation is reported. It must never obscure the required product results.

### 4.2 Temporal evaluation protocol

Sort by `date_received`. Reserve the most recent period as a locked test set. Split the earlier data chronologically into fit and calibration/threshold-validation partitions. Fit text normalization, vectorizer, label mapping, and classifier exclusively on fit data; calibrate probabilities only on the later validation slice; select threshold only there; evaluate once on locked test. If dates tie at a partition boundary, keep the day in one partition to prevent leakage.

### 4.3 Confidence and routing policy

Use calibrated probability of the selected class. Let `C_review` be the cost of human review and `C_misroute` the incremental cost of an incorrect automatic route. Auto-route only when the validation-estimated expected error cost `(1 - p) × C_misroute` is no greater than `C_review`, subject to a minimum class support and optional per-class safety floor. The selected policy reports its cost ratio, threshold, test coverage, auto-route precision, review rate, and sensitivity analysis. Otherwise action is `HUMAN_REVIEW`.

Proposed status values: `AUTO_ROUTE`, `HUMAN_REVIEW_LOW_CONFIDENCE`, `HUMAN_REVIEW_EMPTY_INPUT`, `HUMAN_REVIEW_GUARDRAIL_FAILURE`, `HUMAN_REVIEW_SYSTEM_FAILURE`.

### 4.4 Evaluation artifacts

- Dataset/split manifest and taxonomy mapping version
- Macro-F1, weighted F1, per-class precision/recall/F1/support
- Confusion matrix (raw and normalized)
- Reliability diagram and Brier score/ECE if feasible
- Baseline-vs-candidate comparison and decision rationale
- Threshold/cost curve, selective accuracy, coverage, and review-rate results
- Error slice review for redaction density, time period, rare classes, and empty/short narratives

## 5. Guardrails and LLM contracts

### 5.1 PII pipeline

1. Receive narrative in process memory.
2. Detect entities using local tools/rules; replace values with tokens such as `[EMAIL]`, `[PHONE]`, `[ACCOUNT_ID]`, `[PERSON]`.
3. Classifier may use the original/locally normalized text only if the data policy approves it; every external call and standard audit uses masked text/fingerprint.
4. Require an invariant test that no detected raw value appears in LLM payload, audit payload, exception message, or report.

The masking implementation must document known limitations; it is risk reduction, not a claim of perfect de-identification.

### 5.2 Prompt-injection containment

- Static system/developer instructions define role, output schema, and constraints.
- Narrative/snippet payloads are serialized as labeled data fields, length-limited, and never interpolated into instruction positions.
- The LLM receives no tool credentials and has no direct tool access.
- Use structured output validation; reject/repair malformed output without passing original untrusted content back as instructions.
- Add adversarial test narratives/news snippets that attempt instruction override, exfiltration, SQL injection, and unsupported company claims.

### 5.3 Provider boundary

Define `TextGenerationClient.generate_structured(task, payload)` with provider implementation selected by environment configuration. Initial permitted tasks: triage draft summary and report commentary. The interface logs provider/model/version, latency, token counts if available, and a payload fingerprint—not prompt/raw input. Gemini is the selected text-generation provider. Jev is a separate optional decision-model adapter for benchmark/review-only use. Keys use `.env` locally plus `.env.example` containing names only; `.env` is ignored.

## 6. Reporting design

### 6.1 Query safety and metric flow

The product identifier is looked up in a canonical product table, then supplied as a query parameter. The SQL layer has fixed query templates; no LLM text is accepted as a SQL fragment. Query results contain counts, denominators, periods, and data-quality exclusions. Chart generation consumes these exact result tables.

### 6.2 Context retrieval

For a selected product and report end date, retrieve a bounded set of results using query templates such as `CFPB enforcement <product>` and `<product> consumer finance regulatory action`. Prefer CFPB newsroom/enforcement pages, then named reputable sources allowed by the configured search provider. Retain title, publisher, publication date, URL, retrieved time, and a short extracted claim. Discard undated, inaccessible, duplicate, or out-of-window results. The LLM may say only that an event was reported by the cited source; it cannot state the event caused a metric change.

### 6.3 Report schema

The stored report is structured first: metadata, filters, deterministic metrics, chart-data references, limitations, selected external sources, then LLM commentary. The rendered Markdown/HTML/PDF view is derived from this schema. Required citations link directly to source URLs.

## 7. Interfaces proposed for implementation

| Interface | Input | Output |
| --- | --- | --- |
| `triage` CLI/API | narrative, optional request ID | action, product/issue predictions, calibrated confidence, masked summary, audit ID, guardrail flags |
| `train` CLI | snapshot ID, taxonomy version, config | model artifact ID, metrics report, selected threshold |
| `report` CLI/API | canonical product, as-of date, optional period config | structured report ID, charts, Markdown/HTML report, source list, limitations |
| `review` CLI/UI | audit ID, corrected label/action/reason | immutable correction event linked to original audit ID |

Exact CLI-framework/API endpoint choices are implementation details deferred to task planning. The CLI is sufficient for all required capabilities.

## 8. Test strategy and quality gates

| Layer | Examples |
| --- | --- |
| Unit | taxonomy mappings; PII tokenization; zero prior-period handling; timely-response denominator; allowed product validation; company alias application |
| Data contract | known source schema fixture; missing/renamed column fails with actionable message; manifest checksum/row count |
| ML | dates do not overlap split; vectorizer not fit on test; calibration held out; threshold decision reproducible |
| Security | raw PII absent in mock LLM/audit payload; injection strings cannot alter structured task; secrets absent from logs/repo scan |
| Integration | triage low confidence routes to review; audit failure prevents auto-route; report emits metrics-only when search/LLM fails |
| Visual/manual | chart labels and zero dates/months; PDF diagram includes all required entities/flows; rendered report citations and disclaimers |

Completion gates: reproducible run instructions work from a clean clone; all automated tests pass; metrics/model card and sample report exist; architecture PDF is present; secret/data ignore rules are verified; and the requested public README documents choices/limitations.

## 9. Implementation sequence after SDD v1 approval

1. Create an implementation task breakdown from the approved SDD documents.
2. Scaffold project, dependency pinning, configuration/secrets handling, lint/test hooks, and data contract fixtures.
3. Build ingestion, taxonomy mapping, DuckDB analytics, and deterministic report metrics/charts with tests.
4. Build PII guard and append-only audit store with adversarial tests.
5. Train/evaluate baseline and candidate; choose calibrated threshold/model; publish model card.
6. Add constrained LLM summaries/commentary, optional Jev benchmark, and bounded news retrieval with fallback behavior.
7. Produce a sample report, architecture diagram PDF, final README, and end-to-end reproducibility check.

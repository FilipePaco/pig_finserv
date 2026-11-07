# Data Contract and Governance Design

**Status:** SDD v1 draft
**Owner:** ML and Data Owner
**Applies to:** CFPB ingestion, model training, analytics, reporting, and audit lineage.

## 1. Data principles

- Treat the CFPB source schema as an external contract: inspect and validate each acquired snapshot rather than assuming a fixed CSV layout.
- Preserve source labels and values needed for traceability; derive canonical values through explicit versioned mappings.
- Keep the minimum fields needed for the PoC. Do not include raw narratives in normal logs, reports, or Git.
- Make every model and report traceable to one immutable snapshot manifest.
- Separate public complaint data from production-like input: public availability does not remove the need for PII controls.

## 2. Dataset scope

The default training/reporting snapshot is a rolling **36 completed calendar months** ending at the most recent completed month available in the acquired CFPB snapshot. This provides a recent 12-month reporting window plus chronological training, calibration, and test periods while keeping the PoC locally feasible.

The data acquisition method may be CFPB bulk download or paginated API retrieval. The chosen method must create the same normalized snapshot contract. A smaller development fixture must be deterministic, documented, and representative enough to exercise all pipeline states; it is not used to claim final model performance.

## 3. Source-to-canonical field contract

| Canonical field | CFPB source field | Type | Required | Use |
| --- | --- | --- | --- | --- |
| `complaint_id` | `Complaint ID` | string | Yes | Deduplication, lineage; not included in public reports. |
| `date_received` | `Date received` | date | Yes | Temporal split, report periods, time series. |
| `product_source` | `Product` | string | Yes | Original target lineage. |
| `product_canonical` | Derived | string | Conditional | Product model target and report filter. |
| `sub_product_source` | `Sub-product` | string | No | Optional error analysis. |
| `issue_source` | `Issue` | string | No | Original bonus-target lineage. |
| `issue_canonical` | Derived | string | Conditional | Issue model target and issue ranking. |
| `sub_issue_source` | `Sub-issue` | string | No | Optional error analysis. |
| `company_source` | `Company` | string | No | Company canonicalization lineage. |
| `company_canonical` | Derived | string | No | Company ranking. |
| `company_response` | `Company response to consumer` | string | No | Response distribution. |
| `timely_response` | `Timely response?` | enum | No | Timely-response rate. |
| `date_sent_to_company` | `Date sent to company` | date | No | Data-quality analysis only. |
| `submitted_via` | `Submitted via` | string | No | Error slices only. |
| `narrative_restricted` | `Consumer complaint narrative` or equivalent | string | No | Restricted model input; never default report output. |
| `source_row_fingerprint` | Derived | SHA-256 | Yes | Dedupe/integrity without emitting sensitive content. |
| `snapshot_id` | Derived | string | Yes | Lineage. |

The ingestion layer owns source-column name resolution. It must fail with an actionable schema error if `Complaint ID`, `Date received`, or `Product` cannot be resolved. A missing narrative field is valid for reporting but prevents supervised text-model training.

## 4. Data zones and retention

| Zone | Contents | Storage | Git policy | Retention |
| --- | --- | --- | --- | --- |
| Raw restricted | Acquired source CSV/JSON, possibly including published narrative | Local ignored directory | Never commit | Delete/reacquire after the documented run unless retention is explicitly approved. |
| Curated analytics | Allowed normalized columns, Parquet, no narrative by default | Local ignored directory | Never commit | Retain for reproducible local analysis. |
| Restricted training | Narrative plus canonical labels and snapshot ID | Local ignored directory with least privilege | Never commit | Retain only while training/evaluation is reproducible. |
| Artifact metadata | Manifests, mapping versions, aggregate metrics, report metadata | Repository or artifact store | Commit only non-sensitive, reviewable metadata | Retain with deliverable. |
| Audit events | Fingerprint, masked/minimized fields, decisions and versions | Local SQLite ignored directory | Never commit | Retain for the PoC review period. |

## 5. Snapshot manifest

Every ingest creates `snapshot_id` as a deterministic identifier based on acquisition timestamp and source checksum. Its manifest must contain:

- acquisition method, source URL or API parameters, retrieval timestamp, and source checksum;
- source schema observed and canonical-column mapping used;
- date range, source row count, accepted row count, duplicate count, rejected count, and rejection reasons;
- taxonomy and company-alias mapping versions;
- output Parquet checksum and partition list;
- software/configuration version identifiers.

Manifests must not contain raw narrative text, provider keys, or personally identifying values.

## 6. Taxonomy mapping policy

CFPB preserves historical form values, while its product/issue taxonomy changes over time. Mapping therefore has two goals: stable analytical grouping and honest lineage.

### Product mapping

- Maintain a reviewed table keyed by `effective_date_range`, `source_product`, and optional source sub-product.
- Map to a canonical product label, mapping rationale, and mapping version.
- Preserve `product_source` even when mapped.
- Use `UNMAPPED` for no reviewed mapping and `AMBIGUOUS` for one-to-many/uncertain mappings.
- Exclude `UNMAPPED` and `AMBIGUOUS` from supervised targets by default; include their counts in the data-quality report.

### Issue mapping

- Maintain mappings scoped by canonical product because issue meaning depends on product.
- Preserve source issue and sub-issue.
- Do not collapse distinct issues merely to improve class balance; group only when a documented business-equivalent mapping exists.
- Train an issue model only for product/issue partitions that meet the minimum-support rule in `ml-design.md`.

Taxonomy mappings are manually reviewed configuration, never generated by an LLM at runtime.

## 7. Company canonicalization policy

Company names are normalized only through a reviewed alias table containing `company_source`, `company_canonical`, rationale, reviewer, date, and version. String cleanup may normalize whitespace/case before exact matching, but fuzzy matching is forbidden in the PoC. A non-matched company uses its source name as its displayed canonical value and receives an `UNREVIEWED` status.

Every leaderboard must state that complaint volume is not customer-base normalized and that aliases may remain incomplete.

## 8. Data-quality rules

| Check | Action |
| --- | --- |
| Missing/invalid complaint ID | Reject row; count in manifest. |
| Missing/invalid date received | Reject row; count in manifest. |
| Duplicate complaint ID | Keep one deterministic record; count duplicate and record rule. |
| Missing product | Keep for non-product aggregate quality counts only; exclude from product reports/model training. |
| Missing narrative | Keep for reports; exclude from text-model training. |
| Unknown timely-response value | Map to `UNKNOWN`; exclude from timely-rate denominator. |
| Missing company response | Map to `UNKNOWN`; exclude from response-distribution denominator. |
| Out-of-scope date | Exclude from default snapshot; report excluded count. |
| Taxonomy mapping failure | Keep source row with `UNMAPPED`; exclude from supervised target. |

## 9. Analytical metric definitions

All report calculations use canonical labels and the selected product unless a definition says otherwise.

| Metric | Numerator | Denominator | Missing-data rule |
| --- | --- | --- | --- |
| Complaint volume | Count of valid selected-product complaints in period | None | Exclude invalid/missing dates or product. |
| Volume change | `current_count - previous_count` | `previous_count` | Show `N/A` if previous count is zero; always display both counts. |
| Timely response rate | `timely_response = YES` | Known `YES` or `NO` values | Exclude `UNKNOWN`; display denominator. |
| Response distribution | Count by `company_response` | Known response values | Exclude `UNKNOWN`; display denominator. |
| Issue share | Issue count | All selected-product complaints in current period | Unknown issue remains in total but not named as a top issue. |
| Company share | Company count | All selected-product complaints in current period | Unreviewed aliases may be marked; no exposure normalization. |

The current period is the 30 completed calendar days ending at the report as-of date. The previous period is the immediately preceding 30 calendar days. The monthly chart comprises 12 completed calendar months ending at the as-of month. An as-of date may have zero complaints: it is valid when it is a completed date no later than the snapshot's latest completed date and the snapshot covers the required 12-month chart window. Dates after the snapshot's latest completed date or before its required historical coverage fail validation. All date arithmetic uses a documented project timezone, defaulting to `America/New_York` because the data source is US-focused; the report stores the timezone.

## 10. Data acceptance gates

Before any training or final report:

1. Schema validation and snapshot manifest succeed.
2. Date coverage contains the required model partitions and reporting months.
3. Canonical product mapping coverage and excluded counts are reviewed.
4. Narrative availability and class support are profiled.
5. No restricted data path is tracked by Git.
6. A synthetic fixture validates the contract independently of live CFPB availability.

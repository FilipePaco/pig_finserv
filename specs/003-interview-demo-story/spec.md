# Feature Specification: Interview demo scenario

**Feature branch:** `014-interview-demo-story`
**Status:** SDD v1 — approved for implementation
**Depends on:** `002-streamlit-interface`

## Purpose

Provide a reproducible, entirely synthetic scenario that lets an interviewer see both
the customer-protection and bank-operations value of Pig FinServ. The scenario must
demonstrate responsible triage, auditable human review, deterministic trend analysis,
and the limits of what complaint data can establish.

## Scenario

The fictional **Northstar Bank** receives an elevated volume of credit-card billing
complaints in the 30 days ending 2025-12-01. The demo dataset contains 120 current
period credit-card complaints compared with 40 in the preceding period. The leading
issue is `Duplicate charge`; the timely-response rate is 71.7% (86 of 120 known
responses). Northstar Bank accounts for 70 current-period complaints, but the UI and
walkthrough state that count is not normalized by customer base and does not establish
fault or causality.

Fictional peers are Harbor Financial and Summit Credit. The dataset contains no real
people, accounts, institutions, complaint text, or CFPB records.

## Demonstration narrative

1. **Customer protection:** An analyst submits a fictional duplicate-charge narrative
   containing an email-shaped value. The local guard masks it before the classifier,
   audit store, or optional provider boundary. The result is a proposal; human review
   remains mandatory whenever the policy says so.
2. **Operations signal:** The analyst selects Credit card and 2025-12-01. The report
   exposes the volume change, response denominator, issue/company concentration, daily
   trend, and monthly context.
3. **Responsible decision:** The analyst records an immutable correction if needed and
   recommends investigating the card-billing workflow, response capacity, and affected
   cohort. They do not conclude that Northstar caused the increase or that its customer
   experience is worse than peers without an approved denominator dataset.

## Acceptance criteria

- `scripts/generate_demo_data.py` deterministically creates the scenario from a clean
  ignored directory.
- The report for Credit card as of 2025-12-01 has current/previous counts of 120/40,
  timely counts of 86/120, and Northstar Bank as the top company with 70 complaints.
- The UI includes a concise Demo guide page with the safe walkthrough and limitations.
- The README tells a prospective user that all demo entities/data are fictional and
  gives the exact steps for regenerating them.
- Tests assert scenario metrics; no generated data or artifact is committed.

## Non-goals

- Mimicking real CFPB entities, claiming a real bank issue, or creating synthetic PII.
- Changing the routing policy/model threshold merely to force an attractive result.
- Presenting the scenario as a predictive or causal model of actual bank operations.

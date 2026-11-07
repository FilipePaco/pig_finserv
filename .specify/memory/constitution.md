# Pig FinServ Constitution

## Purpose

Build a demonstrable, reproducible PoC that routes CFPB-style complaints safely and produces data-grounded trend reports. This document overrides convenience decisions in subsequent specifications and code.

## Principles

### 1. Local, measurable classification is the decision engine

`product` (required) and `issue` (bonus) predictions must be produced by a versioned model trained on the project dataset. LLM output may summarize or explain an already-recorded decision, but it may not silently determine the routing label. Each model comparison uses the same chronological holdout and reports macro-F1, per-class metrics, calibration quality, and a confusion matrix.

### 2. Safety precedes LLMs and observability

Unredacted narrative text must be masked before it can reach an LLM, external search service, telemetry, or an audit log. Logs retain a salted input fingerprint plus masked/minimized text only when needed for review. Secrets are environment variables or local secret managers, never source control, documentation examples, or logs.

### 3. Humans own uncertainty and consequential outcomes

A calibrated, validation-selected threshold sends uncertain triage cases to human review. The service must not represent a draft as a final action, claim the complaint was resolved, or automate communications with a consumer/company. A reviewer can correct the label and reason; corrections form a future labeled feedback dataset, not automatic online training.

### 4. Metrics are deterministic and traceable

SQL/analytical queries calculate all numerical report values and charts. The LLM receives a compact, structured result; it must not calculate, invent, or alter metric values. Each report stores data snapshot ID, filters, query version, period boundaries, source URLs, retrieval timestamp, and model/prompt versions.

### 5. Untrusted text is data, never instructions

Complaint narratives, news pages, and retrieved snippets are untrusted content. They are isolated with clear delimiters and never control tool choice, system instructions, SQL, file paths, or secrets. Search has a bounded allowlist/query grammar; reporting uses read-only parameterized queries.

### 6. Company references require proportional evidence

Reports describe observed complaint records, not wrongdoing or causality. Company rankings show counts and share of the selected product/period, disclose that complaint volume is not customer-base-normalized without a valid exposure denominator, and use neutral wording. External events require source/date citation and are framed as context, not proof of cause.

### 7. Reproducibility and testability are deliverable features

Every data snapshot, taxonomy mapping, model artifact, threshold, report, and chart is versioned or fingerprinted. Tests cover the acceptance scenarios, leakage prevention, PII masking, injection resistance, query parameterization, and metric edge cases. The conceptual architecture diagram is rendered to PDF and checked into the repository.

## Quality gates

No implementation phase begins until the specification's open decisions are resolved or explicitly accepted as defaults. No model is promoted unless it beats or justifies not beating the baseline on the chronological holdout, its confidence is evaluated after calibration, and its human-review threshold is justified with validation costs. No report is emitted if its metric query or evidence metadata is incomplete.

## Change control

Requirement changes update `spec.md` first. Architectural changes update `plan.md` and affected contracts. Any exception to these principles must name the risk, scope, owner, and expiry in the relevant specification.

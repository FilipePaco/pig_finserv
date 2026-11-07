# Pig FinServ — complaint triage and insights

Specification-first solution for the CFPB Consumer Complaint Database challenge.

## Status

**Specification and design only.** No data ingestion, model training, API calls, or application code has been implemented yet. The next implementation step is deliberately gated on approval of the requirements and design.

## SDD workflow

This repository combines Kiro-style progressive specification with GitHub Spec Kit traceability:

1. [`constitution.md`](.specify/memory/constitution.md) fixes non-negotiable engineering, safety, and evaluation principles.
2. [`spec.md`](specs/001-complaint-triage/spec.md) describes the user-facing requirements, acceptance scenarios, and explicit open decisions.
3. [`plan.md`](specs/001-complaint-triage/plan.md) turns approved requirements into a technical design, data contracts, and test strategy.
4. [`research.md`](specs/001-complaint-triage/research.md) captures first-party data-contract facts and items that must be checked at implementation time.
5. Only after refinement will `data-model.md`, API/tool contracts, and an implementation task list be created. Code comes last.

## Challenge intent

The PoC has two bounded capabilities:

- **Triage:** classify a new complaint narrative into CFPB product and issue, measure calibrated confidence, route uncertain cases to human review, and produce a masked draft summary.
- **Insights:** compute transparent product-level complaint trends from a local analytical store, create two required charts, retrieve attributable regulatory/news context, and draft an evidence-bounded report.

The solution will use a locally trained classifier; an LLM does not replace the classifier or the metric calculations.

## Decisions that need owner confirmation

- What provider is meant by **“JEV”** (exact product/name and intended use)? Gemini can be treated as the default LLM provider, but no key will be read or stored in the repository.
- Is the deliverable expected to be a CLI, a small web UI, or both? The proposed default is a reproducible CLI plus an optional Streamlit review/report UI.
- What size/time range of CFPB data can the project download and retain locally? The design supports a reproducible bounded sample for development and a full snapshot for a final run.

See the specification documents for the detailed proposal.

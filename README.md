# Pig FinServ — complaint triage and insights

Specification-first solution for the CFPB Consumer Complaint Database challenge.

## Status

**SDD v1 draft; no implementation.** No data ingestion, model training, API calls, dependencies, or application code has been implemented yet. Implementation is deliberately gated on approval of the complete SDD package.

## SDD workflow

This repository combines Kiro-style progressive specification with GitHub Spec Kit traceability:

1. [`constitution.md`](.specify/memory/constitution.md) fixes non-negotiable engineering, safety, and evaluation principles.
2. [`spec.md`](specs/001-complaint-triage/spec.md) describes the user-facing requirements, acceptance scenarios, and resolved MVP decisions.
3. [`plan.md`](specs/001-complaint-triage/plan.md) turns approved requirements into a technical design, data contracts, and test strategy.
4. [`research.md`](specs/001-complaint-triage/research.md) captures first-party data-contract facts and implementation-time verification items.
5. [`data-model.md`](specs/001-complaint-triage/data-model.md), [`ml-design.md`](specs/001-complaint-triage/ml-design.md), [`agent-contract.md`](specs/001-complaint-triage/agent-contract.md), [`interfaces.md`](specs/001-complaint-triage/interfaces.md), and [`test-strategy.md`](specs/001-complaint-triage/test-strategy.md) define the detailed contracts.
6. [`architecture.md`](docs/architecture/architecture.md) is the canonical public architecture document. The required PDF will be rendered only after design approval.
7. Only after SDD v1 approval will an implementation task list be created. Code comes last.

## Challenge intent

The PoC has two bounded capabilities:

- **Triage:** classify a new complaint narrative into CFPB product and issue, measure calibrated confidence, route uncertain cases to human review, and produce a masked draft summary.
- **Insights:** compute transparent product-level complaint trends from a local analytical store, create two required charts, retrieve attributable regulatory/news context, and draft an evidence-bounded report.

The solution will use a locally trained classifier; an LLM does not replace the classifier or the metric calculations.

## MVP decisions

- The required delivery surface is a reproducible CLI. Streamlit is explicitly post-MVP.
- The default data scope is 36 completed calendar months ending at the latest completed month in the acquired CFPB snapshot.
- Gemini is used only for constrained masked summaries and report commentary.
- Jev is an optional masked-text zero-shot benchmark or review-only second opinion; it cannot replace the locally trained classifier.
- API keys are local environment configuration only and are never read, stored, or documented as values in the repository.

See the specification documents for the detailed proposal.

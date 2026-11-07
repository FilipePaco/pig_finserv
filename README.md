# Pig FinServ - complaint triage and insights

An auditable proof of concept for two bounded financial-services workflows using the
CFPB Consumer Complaint Database.

- **Triage:** locally mask a narrative, predict a canonical product with a calibrated
  local model, apply a cost-aware human-review policy, and append a minimized
  hash-chained audit event.
- **Insights:** create deterministic product-level complaint metrics, accessible
  daily/monthly charts, and a Markdown report from an analytics-safe Parquet snapshot.

This is not a production decision system. `AUTO_ROUTE` is an operator suggestion,
not an external action or final customer outcome.

## Architecture and specification

The SDD under [`specs/001-complaint-triage`](specs/001-complaint-triage) defines the
behavioral, ML, safety, interface, and test contracts. The architecture source is
[`docs/architecture/architecture.md`](docs/architecture/architecture.md); the
rendered C4 overview is
[`output/pdf/pig-finserv-architecture.pdf`](output/pdf/pig-finserv-architecture.pdf).

## Local setup

Python 3.11+ and [uv](https://docs.astral.sh/uv/) are required.

```bash
uv sync --all-groups
uv run ruff check .
uv run pytest
```

Create an ignored `.env` or export these variables before `train` or `triage`:

```bash
export PIG_FINSERV_FINGERPRINT_SALT="replace-with-a-local-secret"
# Optional Gemini commentary adapter.
export GEMINI_API_KEY="replace-with-your-key"
export GEMINI_MODEL="your-approved-model-id"
```

Never commit source complaint CSVs, audit databases, model artifacts, provider keys,
or populated `.env` files.

## Reproducible workflow

All paths are local examples. Product mappings and company aliases must be reviewed
CSV files that follow the mapping contract in the SDD.

```bash
# Analytics-safe Parquet plus manifest; narratives are omitted.
uv run pig-finserv ingest \
  local/cfpb.csv local/data local/product-mappings.csv local/company-aliases.csv \
  2026.1 2026.1

# Train from the restricted local CSV. Artifacts contain no raw narrative.
uv run pig-finserv train \
  local/cfpb.csv local/product-mappings.csv cfpb-example 2026.1 \
  local/artifacts/product-v1

uv run pig-finserv validate-model local/artifacts/product-v1 2026.1

# Sensitive narrative is read only from stdin, never a shell argument.
printf '%s' 'My card was charged twice.' | uv run pig-finserv triage \
  local/artifacts/product-v1 local/audit.sqlite 2026.1

uv run pig-finserv report \
  local/data/cfpb-example.parquet 'Credit card' 2026-10-31 local/reports/credit-card

# Optional: retrieve bounded CFPB context and request Gemini commentary when local
# Gemini credentials are configured. Provider failure still renders the report.
uv run pig-finserv report \
  local/data/cfpb-example.parquet 'Credit card' 2026-10-31 local/reports/credit-card \
  --external-context
```

Training requires at least 36 complete calendar months: the latest six are locked
test months and the preceding six calibrate probabilities and choose the threshold.
It compares TF-IDF Logistic Regression and a calibrated TF-IDF Linear SVM on the
same holdout. The SVM is selected only with a material macro-F1 gain.

## Safety boundaries

- PII and narrow local person/location candidates are masked before model features,
  audit fingerprints, or optional provider use.
- Curated Parquet excludes narratives; model artifacts verify checksums and taxonomy
  compatibility before inference.
- SQLite append semantics and a hash chain are tamper-evident, not tamper-proof
  against direct filesystem/database access.
- Gemini receives only an optional bounded payload and returns schema-validated
  commentary. It cannot select routes or access SQL, files, tools, or credentials.
- Jev is disabled by default and can only be a typed benchmark/second-opinion
  boundary; it cannot affect `AUTO_ROUTE` eligibility.

See [`docs/safety.md`](docs/safety.md) for de-identification limitations.

## Validation

```bash
uv run ruff check .
uv run pytest
```

Tests cover schema/mapping lineage, PII masking, audit integrity, chronological
partitions, calibration, verified artifacts, locked-holdout evaluation, report
denominators/zero-fill behavior, and optional integration boundaries.

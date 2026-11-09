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

## Docker

Docker Compose runs the CLI without baking source data, model artifacts, audit
databases, or credentials into the image. It reads the ignored local `.env`, mounts
the ignored `local/` directory at `/app/local`, and overrides optional Gemini
commentary to `gemini-3.5-flash-lite`, a cost-efficient text model.

```bash
docker compose build
docker compose run --rm pig-finserv --help
docker compose run --rm pig-finserv smoke-gemini
```

The first two commands require no data. `smoke-gemini` needs `GEMINI_API_KEY` in the
local `.env`; it sends only synthetic metrics.
The CFPB CSV and reviewed mappings belong in `local/` and stay out of Git:

```bash
docker compose run --rm pig-finserv ingest \
  /app/local/cfpb.csv /app/local/data /app/local/product-mappings.csv \
  /app/local/company-aliases.csv 2026.1 2026.1
```

For triage through standard input, disable pseudo-TTY allocation:

```bash
printf '%s' 'My card was charged twice.' | \
  docker compose run --rm -T pig-finserv triage \
  /app/local/artifacts/product-v1 /app/local/audit.sqlite 2026.1
```

### Streamlit demo

The optional UI runs only on localhost and is a presentation layer over the same
typed workflows as the CLI. Generate the ignored synthetic demo files once, then
start it with either `uv` or Docker Compose:

```bash
uv sync --all-groups
uv run python scripts/generate_demo_data.py local/demo
demo_snapshot=$(uv run pig-finserv ingest \
  local/demo/cfpb-demo.csv local/demo/data local/demo/product-mappings.csv \
  local/demo/company-aliases.csv 2026.1 2026.1)
PIG_FINSERV_FINGERPRINT_SALT=demo-local-salt uv run pig-finserv train \
  local/demo/cfpb-demo.csv local/demo/product-mappings.csv "$demo_snapshot" 2026.1 \
  local/demo/artifacts/product-v1 --minimum-class-support 2
```

For a local `uv` run, export the six `PIG_FINSERV_*` values documented in
[`specs/002-streamlit-interface/plan.md`](specs/002-streamlit-interface/plan.md)
with paths below `local/demo/`, then run:

```bash
uv run streamlit run src/pig_finserv/ui/app.py --server.address 127.0.0.1
```

The Docker profile supplies those container paths for the synthetic demo:

```bash
docker compose --profile ui up --build ui
```

Open `http://127.0.0.1:8501`. Use only synthetic examples such as `My card payment
was charged twice.`; do not enter personal or production complaint data.

Create an ignored `.env` or export these variables before `train` or `triage`:

```bash
export PIG_FINSERV_FINGERPRINT_SALT="replace-with-a-local-secret"
# Optional Gemini commentary adapter.
export GEMINI_API_KEY="replace-with-your-key"
export GEMINI_MODEL="your-approved-model-id"
```

Never commit source complaint CSVs, audit databases, model artifacts, provider keys,
or populated `.env` files.

After setting the optional Gemini variables, validate the provider using only
synthetic non-sensitive values:

```bash
uv run pig-finserv smoke-gemini
```

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

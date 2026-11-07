# MVP verification evidence

## Local verification

The repository was verified with:

```bash
uv run ruff check .
uv run pytest
```

The latest local verification completed with **70 passing tests**. The suite includes
`tests/test_e2e.py`, which uses only synthetic CFPB-shaped rows in a temporary
directory and proves the CLI sequence below without retaining raw data:

1. `ingest` writes a curated Parquet snapshot and manifest.
2. `train` creates a calibrated, checksum-verified local model artifact.
3. `triage` reads a narrative via stdin, masks PII, applies the policy, and appends
   a safe audit event.
4. `report` validates coverage and writes deterministic Markdown plus daily/monthly
   PNG charts.

The C4 PDF in `output/pdf/` was rendered to PNG and visually inspected before it
was committed.

## Deliberately external verification

The Gemini and Jev keys are not present in the development environment used for this
verification. No key, source complaint CSV, audit database, generated artifact, or
provider response is committed. The opt-in `report --external-context` path has unit
and workflow tests; a live provider smoke test must be run only after local
environment variables are configured.
